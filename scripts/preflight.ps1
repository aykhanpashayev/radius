# preflight.ps1 — Windows preflight check for Radius deployment.
#
# Usage (PowerShell):
#   .\scripts\preflight.ps1 [-Env dev] [-SkipAws]
#
# This script checks all prerequisites on Windows before deploying Radius.
# Run it from the repository root.

param(
    [string]$Env = "dev",
    [switch]$SkipAws
)

$Pass = 0
$Fail = 0
$Warn = 0

function Ok($msg)   { Write-Host "  [PASS] $msg" -ForegroundColor Green;  $script:Pass++ }
function Fail($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red;    $script:Fail++ }
function Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow; $script:Warn++ }
function Section($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }

# ---------------------------------------------------------------------------
# 1. Windows environment
# ---------------------------------------------------------------------------
Section "Environment"

Ok "OS: Windows $([System.Environment]::OSVersion.Version)"

# Check for WSL2
$wslCheck = wsl --status 2>$null
if ($LASTEXITCODE -eq 0) {
    Ok "WSL2 is available — deployment shell scripts (build-lambdas.sh, deploy-infra.sh) can run in WSL2"
} else {
    Warn "WSL2 not detected. Shell scripts (.sh) require WSL2 or Git Bash. See docs/deployment.md#windows"
}

# Check for Git Bash
$gitBash = Get-Command "bash" -ErrorAction SilentlyContinue
if ($gitBash) {
    Ok "bash found at $($gitBash.Source) — shell scripts can run via Git Bash"
} else {
    Warn "bash not found on PATH — install Git for Windows (https://git-scm.com) or use WSL2"
}

# ---------------------------------------------------------------------------
# 2. Required tools
# ---------------------------------------------------------------------------
Section "Required tools"

# Python
$pyCmd = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $pyCmd) { $pyCmd = Get-Command "python3" -ErrorAction SilentlyContinue }

if ($pyCmd) {
    $pyVer = & $pyCmd.Name -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    $parts = $pyVer -split "\."
    if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 11) {
        Ok "Python $pyVer"
    } else {
        Fail "Python $pyVer — need 3.11+. Download from https://python.org"
    }
} else {
    Fail "Python not found — download from https://python.org"
}

# pip
$pipCmd = Get-Command "pip" -ErrorAction SilentlyContinue
if (-not $pipCmd) { $pipCmd = Get-Command "pip3" -ErrorAction SilentlyContinue }
if ($pipCmd) {
    $pipVer = & $pipCmd.Name --version 2>$null | Select-String -Pattern "pip (\S+)" | ForEach-Object { $_.Matches[0].Groups[1].Value }
    Ok "pip $pipVer"
} else {
    Fail "pip not found — reinstall Python 3.11+ with pip included"
}

# Terraform
$tfCmd = Get-Command "terraform" -ErrorAction SilentlyContinue
if ($tfCmd) {
    $tfVer = & terraform version -json 2>$null | python -c "import json,sys; d=json.load(sys.stdin); print(d['terraform_version'])" 2>$null
    if ($tfVer) {
        $tfParts = $tfVer -split "\."
        if ([int]$tfParts[0] -ge 1 -and [int]$tfParts[1] -ge 5) {
            Ok "Terraform $tfVer"
        } else {
            Fail "Terraform $tfVer — need >= 1.5.0. Download from https://developer.hashicorp.com/terraform/downloads"
        }
    } else {
        Ok "Terraform found (version check failed — verify manually with: terraform version)"
    }
} else {
    Fail "Terraform not found — download from https://developer.hashicorp.com/terraform/downloads"
}

# AWS CLI
$awsCmd = Get-Command "aws" -ErrorAction SilentlyContinue
if ($awsCmd) {
    $awsVer = & aws --version 2>&1 | Select-String -Pattern "aws-cli/(\S+)" | ForEach-Object { $_.Matches[0].Groups[1].Value }
    Ok "AWS CLI $awsVer"
} elseif (-not $SkipAws) {
    Fail "AWS CLI not found — install from https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
}

# ---------------------------------------------------------------------------
# 3. Python packages
# ---------------------------------------------------------------------------
Section "Python packages"

$packages = @("boto3", "moto", "pytest", "hypothesis")
foreach ($pkg in $packages) {
    $result = & python -c "import $pkg" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Ok "Python package: $pkg"
    } else {
        Fail "Python package '$pkg' not installed — run: pip install -r backend\requirements-dev.txt"
    }
}

$result = & python -c "import pytest_cov" 2>$null
if ($LASTEXITCODE -eq 0) {
    Ok "Python package: pytest-cov"
} else {
    Fail "Python package 'pytest-cov' not installed — run: pip install -r backend\requirements-dev.txt"
}

# ---------------------------------------------------------------------------
# 4. AWS credentials
# ---------------------------------------------------------------------------
if (-not $SkipAws) {
    Section "AWS credentials"
    $identity = & aws sts get-caller-identity 2>$null | ConvertFrom-Json
    if ($identity) {
        Ok "AWS credentials valid"
        Ok "Account: $($identity.Account)"
        Ok "Identity: $($identity.Arn)"
    } else {
        Fail "AWS credentials not configured or expired — run: aws configure"
    }
}

# ---------------------------------------------------------------------------
# 5. Config files
# ---------------------------------------------------------------------------
Section "Config files [env=$Env]"

$envDir = "infra\envs\$Env"

if (Test-Path "$envDir\terraform.tfvars") {
    $content = Get-Content "$envDir\terraform.tfvars" -Raw
    if ($content -match "<REPLACE") {
        Fail "$envDir\terraform.tfvars has unfilled placeholder values — open the file and replace every <REPLACE: ...>"
    } else {
        Ok "$envDir\terraform.tfvars"
    }
} else {
    Fail "$envDir\terraform.tfvars not found"
}

if (Test-Path "$envDir\backend.tfvars") {
    $content = Get-Content "$envDir\backend.tfvars" -Raw
    if ($content -match "<REPLACE") {
        Fail "$envDir\backend.tfvars has unfilled placeholder values — open the file and replace every <REPLACE: ...>"
    } else {
        Ok "$envDir\backend.tfvars"
    }
} else {
    Fail "$envDir\backend.tfvars not found"
}

if (Test-Path "backend\requirements-dev.txt") {
    Ok "backend\requirements-dev.txt"
} else {
    Fail "backend\requirements-dev.txt not found"
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "Preflight summary: $Pass passed, $Warn warnings, $Fail failed" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

if ($Fail -gt 0) {
    Write-Host ""
    Write-Host "Fix the [FAIL] items above before proceeding." -ForegroundColor Red
    Write-Host "See docs/deployment.md for detailed instructions."
    exit 1
} else {
    Write-Host ""
    Write-Host "All required checks passed." -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps (run in PowerShell):"
    Write-Host "  1. pip install -r backend\requirements-dev.txt"
    Write-Host "  2. python -m pytest backend\tests\ -q"
    Write-Host "  3. For deployment scripts, use WSL2 or Git Bash"
    Write-Host "  See docs/deployment.md for the full deployment guide."
}
