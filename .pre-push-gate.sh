#!/usr/bin/env bash
# mcpschema pre-push quality gate (Invariant 23).
#
# Refuses `git push` unless:
#   1. README.md, LICENSE, QA_REPORT.md, FUZZING_REPORT.md exist
#   2. Working tree is clean
#   3. Both QA_REPORT.md and FUZZING_REPORT.md end with "VERDICT: SHIP"
#   4. The full pytest suite is green (145/145 passing)
#   5. Secret scan is clean
#
# Install: `ln -sf ../../.pre-push-gate.sh .git/hooks/pre-push`

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

fail=0

echo "[gate] Checking required artifacts..."

required=(README.md LICENSE QA_REPORT.md FUZZING_REPORT.md)
for f in "${required[@]}"; do
    if [[ ! -f "$f" ]]; then
        echo "  X missing: $f"
        fail=1
    else
        echo "  ok $f"
    fi
done

if [[ $fail -ne 0 ]]; then
    echo "[gate] FAIL — required artifacts missing. Refusing push."
    exit 1
fi

echo "[gate] Checking working tree..."
if ! git diff --quiet HEAD 2>/dev/null; then
    echo "  X working tree has uncommitted changes"
    echo "[gate] FAIL — refusing push."
    exit 1
fi
echo "  ok working tree clean"

echo "[gate] Checking QA verdict..."
if ! tail -5 QA_REPORT.md | grep -q "VERDICT: SHIP"; then
    echo "  X QA_REPORT.md does not end with 'VERDICT: SHIP'"
    echo "[gate] FAIL — refusing push."
    exit 1
fi
echo "  ok QA_REPORT.md verdict SHIP"

echo "[gate] Checking FUZZING verdict..."
if ! tail -5 FUZZING_REPORT.md | grep -q "VERDICT: SHIP"; then
    echo "  X FUZZING_REPORT.md does not end with 'VERDICT: SHIP'"
    echo "[gate] FAIL — refusing push."
    exit 1
fi
echo "  ok FUZZING_REPORT.md verdict SHIP"

echo "[gate] Running pytest..."
if ! python3 -m pytest -q --tb=line; then
    echo "[gate] FAIL — pytest failed."
    exit 1
fi

echo "[gate] Scanning for secrets..."
if git grep -nE 'ghp_|pypi-AgEI|npm_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer ey[A-Za-z0-9._-]+|BEGIN PRIVATE KEY' -- ':!*.md' ':!LICENSE' ':!.pre-push-gate.sh'; then
    echo "[gate] FAIL — secret pattern found in source."
    exit 1
fi
echo "  ok no secrets found"

echo "[gate] PASS — all checks succeeded."
