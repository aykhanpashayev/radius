# preflight.ps1 - Windows preflight check for Radius deployment.
#
# Usage (PowerShell):
#   .\scripts\preflight.ps1 [-Env dev] [-SkipAws]
#
# Run from the repository root. Fix every [FAIL] before deploying.

param(
    [string]$Env = "dev",
    [switch]$SkipAws
)

$Pass = 0
$Fail = 0
$Warn = 0

function Ok($msg)      { Write-Host "  [PASS] $msg" -ForegroundColor Green;  $script:Pass++ }
function Fail($msg)    { Write-Host "  [FAIL] $msg" -ForegroundColor Red;    $script:Fail++ }
function Warn($msg)    { Write-Host "  [WARN] $msg" -ForegroundColor Yellow; $script:Warn++ }
function Section($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }

# ---------------------------------------------------------------------------
# 1. Environment
# ---------------------------------------------------------------------------
Section "Environment"

Ok "OS: Windows $([System.Environment]::OSVersion.Version)"

$wslOut = wsl --status 2>$null
if ($LASTEXITCODE -eq 0) {
    Ok "WSL2 is available - shell scripts (.sh) can run inside WSL2"
} else {
    Warn "WSL2 not detected. Shell scripts require WSL2 or Git Bash. See docs/deployment.md#windows"
}

$gitBash = Get-Command "bash" -ErrorAction SilentlyContinue
if ($gitBash) {
    Ok "bash found at $($gitBash.Source)"
} else {
    Warn "bash not on PATH - install Git for Windows (https://git-scm.com) or WSL2 to run .sh scripts"
}

# ---------------------------------------------------------------------------
# 2. Required tools
# ---------------------------------------------------------------------------
Section "Required tools"

# Python 3.11+
$pyCmd = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $pyCmd) { $pyCmd = Get-Command "python3" -ErrorAction SilentlyContinue }

if ($pyCmd) {
    $pyVer = & $pyCmd.Name -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    $parts = $pyVer -split "\."
    if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 11) {
        Ok "Python $pyVer"
    } else {
        Fail "Python $pyVer found but need 3.11+. Download from https://python.org"
    }
} else {
    Fail "Python not found. Download from https://python.org"
}

# pip
$pipCmd = Get-Command "pip" -ErrorAction SilentlyContinue
if (-not $pipCmd) { $pipCmd = Get-Command "pip3" -ErrorAction SilentlyContinue }
if ($pipCmd) {
    $pipVer = (& $pipCmd.Name --version 2>$null) -replace "pip (\S+).*", '$1'
    Ok "pip $pipVer"
} else {
    Fail "pip not found - reinstall Python 3.11+ with pip included"
}

# Terraform
$tfCmd = Get-Command "terraform" -ErrorAction SilentlyContinue
if ($tfCmd) {
    $tfRaw = & terraform version 2>$null | Select-Object -First 1
    $tfVer = $tfRaw -replace "Terraform v", ""
    $tfParts = $tfVer -split "\."
    if ([int]$tfParts[0] -ge 1 -and [int]$tfParts[1] -ge 5) {
        Ok "Terraform $tfVer"
    } else {
        Fail "Terraform $tfVer found but need >= 1.5.0. Download from https://developer.hashicorp.com/terraform/downloads"
    }
} else {
    Fail "Terraform not found. Download from https://developer.hashicorp.com/terraform/downloads"
}

# AWS CLI
$awsCmd = Get-Command "aws" -ErrorAction SilentlyContinue
if ($awsCmd) {
    $awsRaw = & aws --version 2>&1
    $awsVer = $awsRaw -replace "aws-cli/(\S+).*", '$1'
    Ok "AWS CLI $awsVer"
} elseif (-not $SkipAws) {
    Fail "AWS CLI not found. Install from https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
} else {
    Warn "AWS CLI not found (skipped with -SkipAws)"
}

# ---------------------------------------------------------------------------
# 3. Python packages
# ---------------------------------------------------------------------------
Section "Python packages"

$pyExe = if (Get-Command "python" -ErrorAction SilentlyContinue) { "python" } else { "python3" }

foreach ($pkg in @("boto3", "moto", "pytest", "hypothesis")) {
    & $pyExe -c "import $pkg" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Ok "Python package: $pkg"
    } else {
        Fail "Python package '$pkg' not installed. Run: pip install -r backend\requirements-dev.txt"
    }
}

& $pyExe -c "import pytest_cov" 2>$null
if ($LASTEXITCODE -eq 0) {
    Ok "Python package: pytest-cov"
} else {
    Fail "Python package 'pytest-cov' not installed. Run: pip install -r backend\requirements-dev.txt"
}

# ---------------------------------------------------------------------------
# 4. AWS credentials
# ---------------------------------------------------------------------------
if (-not $SkipAws) {
    Section "AWS credentials"
    try {
        $identity = & aws sts get-caller-identity 2>$null | ConvertFrom-Json
        if ($identity -and $identity.Account) {
            Ok "AWS credentials valid"
            Ok "Account: $($identity.Account)"
            Ok "Identity: $($identity.Arn)"
        } else {
            Fail "AWS credentials not configured or expired. Run: aws configure"
        }
    } catch {
        Fail "AWS credentials check failed. Run: aws configure"
    }
}

# ---------------------------------------------------------------------------
# 5. Config files
# ---------------------------------------------------------------------------
Section "Config files [env=$Env]"

$envDir = "infra\envs\$Env"

if (Test-Path "$envDir\terraform.tfvars") {
    $content = Get-Content "$envDir\terraform.tfvars" -Raw
    if ($content -match "REPLACE") {
        Fail "$envDir\terraform.tfvars has unfilled placeholder values. Open the file and replace every <REPLACE: ...> with your actual values."
    } else {
        Ok "$envDir\terraform.tfvars"
    }
} else {
    Fail "$envDir\terraform.tfvars not found"
}

if (Test-Path "$envDir\backend.tfvars") {
    $content = Get-Content "$envDir\backend.tfvars" -Raw
    if ($content -match "REPLACE") {
        Fail "$envDir\backend.tfvars has unfilled placeholder values. Open the file and replace every <REPLACE: ...> with your actual values."
    } else {
        Ok "$envDir\backend.tfvars"
    }
} else {
    Fail "$envDir\backend.tfvars not found"
}

if (Test-Path "backend\requirements-dev.txt") {
    Ok "backend\requirements-dev.txt exists"
} else {
    Fail "backend\requirements-dev.txt not found"
}

if (Test-Path "pyproject.toml") {
    Ok "pyproject.toml exists"
} else {
    Warn "pyproject.toml not found - pytest pythonpath may not be configured"
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "Preflight summary: $Pass passed, $Warn warnings, $Fail failed" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan

if ($Fail -gt 0) {
    Write-Host ""
    Write-Host "Fix the [FAIL] items above before proceeding." -ForegroundColor Red
    Write-Host "See docs/deployment.md for detailed instructions."
    exit 1
} else {
    Write-Host ""
    Write-Host "All required checks passed." -ForegroundColor Green
    if ($Warn -gt 0) {
        Write-Host "Review the [WARN] items above - they may affect deployment."
    }
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. pip install -r backend\requirements-dev.txt"
    Write-Host "  2. python -m pytest backend\tests\ -q"
    Write-Host "  3. For .sh deployment scripts, use WSL2 or Git Bash"
    Write-Host "  See docs/deployment.md for the full deployment guide."
}
