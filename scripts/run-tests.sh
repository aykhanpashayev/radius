#!/usr/bin/env bash
# run-tests.sh — Run all Radius test suites and print a coverage summary.
# Usage: bash scripts/run-tests.sh [--fast]
#
# Options:
#   --fast    Skip property-based tests (faster CI mode)

set -euo pipefail

# ---------------------------------------------------------------------------
# Windows/WSL2 compatibility — date +%s%N may not work on all systems.
# Fall back to Python for nanosecond timestamps if needed.
# ---------------------------------------------------------------------------
_timestamp_ns() {
  local ts
  ts=$(date +%s%N 2>/dev/null)
  if [[ "$ts" == *N* ]] || [[ -z "$ts" ]]; then
    # date doesn't support %N (macOS without coreutils, some WSL2 setups)
    python3 -c "import time; print(int(time.time() * 1e9))"
  else
    echo "$ts"
  fi
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
FAST=false
for arg in "$@"; do
  [[ "$arg" == "--fast" ]] && FAST=true
done

# Stable JSON coverage report written by pytest-cov; parsed after each suite.
COVERAGE_JSON=".coverage-report.json"

# ---------------------------------------------------------------------------
# Parallel arrays to accumulate suite results
# ---------------------------------------------------------------------------
SUITE_NAMES=()
SUITE_TESTS=()
SUITE_PASSED=()
SUITE_FAILED=()
SUITE_COVERAGE=()
SUITE_DURATIONS=()
TOTAL_FAILURES=0

# ---------------------------------------------------------------------------
# run_suite <name> <pytest-command>
#
# Runs a pytest command, captures output, parses pass/fail counts and
# reads coverage from the JSON report (stable across pytest-cov versions).
# Uses "|| true" so set -e does not abort the script on test failures.
# ---------------------------------------------------------------------------
run_suite() {
  local suite_name="$1"
  local pytest_cmd="$2"

  echo ""
  echo "Running: ${suite_name}"
  echo "  cmd: ${pytest_cmd}"

  local start_ts
  start_ts=$(_timestamp_ns)

  # Capture output; allow non-zero exit so we can record failures
  local output
  output=$(eval "${pytest_cmd}" 2>&1) || true

  local end_ts
  end_ts=$(_timestamp_ns)

  # Duration in seconds with one decimal place
  local duration_ns=$(( end_ts - start_ts ))
  local duration_s
  duration_s=$(awk "BEGIN { printf \"%.1f\", ${duration_ns}/1000000000 }")

  # Parse passed/failed counts from pytest summary line
  local passed=0
  local failed=0

  if echo "${output}" | grep -qE '[0-9]+ passed'; then
    passed=$(echo "${output}" | grep -oE '[0-9]+ passed' | tail -1 | grep -oE '[0-9]+')
  fi

  if echo "${output}" | grep -qE '[0-9]+ failed'; then
    failed=$(echo "${output}" | grep -oE '[0-9]+ failed' | tail -1 | grep -oE '[0-9]+')
  fi

  # Parse coverage from the JSON report — stable format regardless of pytest-cov version.
  # Falls back to "N/A" if the file is absent or malformed.
  local coverage="N/A"
  if [[ -f "${COVERAGE_JSON}" ]]; then
    coverage=$(python3 -c "
import json, sys
try:
    data = json.load(open('${COVERAGE_JSON}'))
    pct = data['totals']['percent_covered_display']
    print(pct + '%')
except Exception:
    print('N/A')
")
  fi

  local total=$(( passed + failed ))

  SUITE_NAMES+=("${suite_name}")
  SUITE_TESTS+=("${total}")
  SUITE_PASSED+=("${passed}")
  SUITE_FAILED+=("${failed}")
  SUITE_COVERAGE+=("${coverage}")
  SUITE_DURATIONS+=("${duration_s}s")

  TOTAL_FAILURES=$(( TOTAL_FAILURES + failed ))

  # Print captured output so the user can see pytest details
  echo "${output}"
}

# ---------------------------------------------------------------------------
# print_summary_table
#
# Prints a formatted table of all suite results followed by a TOTAL row
# and a final pass/fail message.
# ---------------------------------------------------------------------------
print_summary_table() {
  local sep="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  local thin="─────────────────────────────────────────────────────────────────────────────"

  echo ""
  echo "${sep}"
  echo "Test Suite Summary"
  echo "${sep}"
  printf "%-24s  %-7s  %-7s  %-7s  %-10s  %s\n" \
    "Suite" "Tests" "Passed" "Failed" "Coverage" "Duration"
  echo "${thin}"

  local total_tests=0
  local total_passed=0
  local total_failed=0
  local total_duration_s=0

  local i
  for i in "${!SUITE_NAMES[@]}"; do
    printf "%-24s  %-7s  %-7s  %-7s  %-10s  %s\n" \
      "${SUITE_NAMES[$i]}" \
      "${SUITE_TESTS[$i]}" \
      "${SUITE_PASSED[$i]}" \
      "${SUITE_FAILED[$i]}" \
      "${SUITE_COVERAGE[$i]}" \
      "${SUITE_DURATIONS[$i]}"

    total_tests=$(( total_tests + SUITE_TESTS[$i] ))
    total_passed=$(( total_passed + SUITE_PASSED[$i] ))
    total_failed=$(( total_failed + SUITE_FAILED[$i] ))
    # Sum durations (strip trailing 's')
    local d="${SUITE_DURATIONS[$i]%s}"
    total_duration_s=$(awk "BEGIN { printf \"%.1f\", ${total_duration_s} + ${d} }")
  done

  echo "${thin}"
  printf "%-24s  %-7s  %-7s  %-7s  %-10s  %s\n" \
    "TOTAL" "${total_tests}" "${total_passed}" "${total_failed}" "" "${total_duration_s}s"
  echo "${sep}"

  if [[ "${TOTAL_FAILURES}" -eq 0 ]]; then
    echo "All tests passed."
  else
    echo "FAILED: ${TOTAL_FAILURES} test(s) failed."
  fi
}

# ---------------------------------------------------------------------------
# Suite invocations
# ---------------------------------------------------------------------------

# Suite 1: Unit tests (exclude integration and property-based)
run_suite "Unit Tests" \
  "pytest backend/tests/ \
   --ignore=backend/tests/integration \
   --ignore=backend/tests/test_*_properties.py \
   --cov=backend --cov-report=term-missing --cov-report=json:${COVERAGE_JSON} -q"

# Suite 2: Integration tests
run_suite "Integration Tests" \
  "pytest backend/tests/integration/ \
   --cov=backend --cov-append --cov-report=term-missing --cov-report=json:${COVERAGE_JSON} -q"

# Suite 3: Property-based tests (skipped with --fast)
if [[ "${FAST}" == "false" ]]; then
  run_suite "Property-Based Tests" \
    "pytest backend/tests/test_*_properties.py \
     --cov=backend --cov-append --cov-report=term-missing --cov-report=json:${COVERAGE_JSON} -q"
fi

# ---------------------------------------------------------------------------
# Summary and exit
# ---------------------------------------------------------------------------
print_summary_table

# Clean up the temporary coverage JSON file
rm -f "${COVERAGE_JSON}"

if [[ "${TOTAL_FAILURES}" -eq 0 ]]; then
  exit 0
else
  exit 1
fi
