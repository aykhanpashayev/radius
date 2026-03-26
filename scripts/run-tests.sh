#!/usr/bin/env bash
# run-tests.sh — Run all Radius test suites and print a coverage summary.
# Usage: bash scripts/run-tests.sh [--fast]
#
# Options:
#   --fast    Skip property-based tests (faster CI mode)

set -euo pipefail

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
FAST=false
for arg in "$@"; do
  [[ "$arg" == "--fast" ]] && FAST=true
done

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
# coverage percentage, and appends results to the parallel arrays above.
# Uses "|| true" so set -e does not abort the script on test failures.
# ---------------------------------------------------------------------------
run_suite() {
  local suite_name="$1"
  local pytest_cmd="$2"

  echo ""
  echo "Running: ${suite_name}"
  echo "  cmd: ${pytest_cmd}"

  local start_ts
  start_ts=$(date +%s%N)   # nanoseconds

  # Capture output; allow non-zero exit so we can record failures
  local output
  output=$(eval "${pytest_cmd}" 2>&1) || true

  local end_ts
  end_ts=$(date +%s%N)

  # Duration in seconds with one decimal place
  local duration_ns=$(( end_ts - start_ts ))
  local duration_s
  duration_s=$(awk "BEGIN { printf \"%.1f\", ${duration_ns}/1000000000 }")

  # Parse passed count  — pytest summary line: "42 passed" or "42 passed, 1 failed"
  local passed=0
  local failed=0

  if echo "${output}" | grep -qE '[0-9]+ passed'; then
    passed=$(echo "${output}" | grep -oE '[0-9]+ passed' | tail -1 | grep -oE '[0-9]+')
  fi

  if echo "${output}" | grep -qE '[0-9]+ failed'; then
    failed=$(echo "${output}" | grep -oE '[0-9]+ failed' | tail -1 | grep -oE '[0-9]+')
  fi

  # Parse coverage percentage from the TOTAL line produced by pytest-cov:
  # "TOTAL    1234   456   63%"
  local coverage="N/A"
  if echo "${output}" | grep -qE '^TOTAL\s+'; then
    coverage=$(echo "${output}" | grep -E '^TOTAL\s+' | tail -1 | awk '{print $NF}')
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
   --cov=backend --cov-report=term-missing -q"

# Suite 2: Integration tests
run_suite "Integration Tests" \
  "pytest backend/tests/integration/ \
   --cov=backend --cov-append --cov-report=term-missing -q"

# Suite 3: Property-based tests (skipped with --fast)
if [[ "${FAST}" == "false" ]]; then
  run_suite "Property-Based Tests" \
    "pytest backend/tests/test_*_properties.py \
     --cov=backend --cov-append --cov-report=term-missing -q"
fi

# ---------------------------------------------------------------------------
# Summary and exit
# ---------------------------------------------------------------------------
print_summary_table

if [[ "${TOTAL_FAILURES}" -eq 0 ]]; then
  exit 0
else
  exit 1
fi
