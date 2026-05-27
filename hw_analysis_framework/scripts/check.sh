#!/usr/bin/env bash
# Pre-commit check for the hardware analysis framework.
#
# Runs every stage (lint, type-check, framework tests, components tests)
# and reports a summary at the end. Continues past failures so a single
# run surfaces ALL outstanding issues, not just the first one.
# Exit status is non-zero if any stage failed.
#
# Components tests reuse the framework venv (components has no venv of
# its own). example_analysis tests are skipped intentionally: they include
# a verification that's *designed* to fail until the block author derates
# the design (see hw_analysis_framework/CLAUDE.md gotcha #12).

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_DIR="$(cd "$HERE/.." && pwd)"
COMPONENTS_DIR="$(cd "$FRAMEWORK_DIR/../components" && pwd)"
VENV_PY="$FRAMEWORK_DIR/.venv/bin/python"

declare -a failures=()

run_stage() {
    local label="$1"
    shift
    echo
    echo "=== $label ==="
    if ! "$@"; then
        failures+=("$label")
    fi
}

cd "$FRAMEWORK_DIR"

run_stage "ruff check (framework)"   poetry run ruff check src tests
run_stage "mypy (framework)"          poetry run mypy
run_stage "pytest (framework)"        poetry run pytest -q

cd "$COMPONENTS_DIR"
run_stage "pytest (components)"       "$VENV_PY" -m pytest -q

echo
if [[ ${#failures[@]} -eq 0 ]]; then
    echo "All checks passed."
    exit 0
else
    echo "FAILED: ${#failures[@]} stage(s):"
    for f in "${failures[@]}"; do
        echo "  - $f"
    done
    exit 1
fi
