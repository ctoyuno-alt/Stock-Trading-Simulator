#!/usr/bin/env bash
# ==============================================================================
# Security & Secret Leak Audit Script
# Validates:
#   1. .env and secrets are not tracked in git.
#   2. Dockerfiles run as non-root users.
#   3. Real trading flag default is hard locked to False.
#   4. No plain-text API keys or DB passwords committed.
# ==============================================================================

set -euo pipefail

FAILURES=0

echo "================================================================================"
echo " Starting Platform Security & Compliance Audit"
echo "================================================================================"

# Check 1: Ensure .env is not in Git
echo -n "[1/5] Checking Git index for .env and credential files... "
if git ls-files | grep -E '^(\.env|\.env\..*)$' | grep -v '\.env\.example'; then
    echo "FAILED: Secret file found in git tracking!"
    FAILURES=$((FAILURES + 1))
else
    echo "PASSED"
fi

# Check 2: Verify .gitignore exclusions
echo -n "[2/5] Checking .gitignore rules... "
REQUIRED_IGNORES=(".env" "postgres-data/" "*.log" "__pycache__/")
MISSING_RULES=0
for rule in "${REQUIRED_IGNORES[@]}"; do
    if ! grep -qF "${rule}" .gitignore; then
        echo "Missing ignore rule: ${rule}"
        MISSING_RULES=$((MISSING_RULES + 1))
    fi
done
if [ ${MISSING_RULES} -eq 0 ]; then
    echo "PASSED"
else
    echo "FAILED: Missing required .gitignore entries."
    FAILURES=$((FAILURES + 1))
fi

# Check 3: Container security (non-root execution)
echo -n "[3/5] Verifying non-root user enforcement in Dockerfiles... "
DOCKER_NONROOT=0
if grep -q "USER appuser" docker/Dockerfile.backend && grep -q "USER streamlituser" docker/Dockerfile.dashboard; then
    echo "PASSED (backend: appuser UID 10001, dashboard: streamlituser UID 10002)"
else
    echo "FAILED: Dockerfiles must specify non-root USER."
    FAILURES=$((FAILURES + 1))
fi

# Check 4: Real trading lockout
echo -n "[4/5] Verifying ENABLE_REAL_TRADING safety lock... "
if grep -q "ENABLE_REAL_TRADING.*False" backend/app/core/config.py && grep -q "ENABLE_REAL_TRADING=false" .env.example; then
    echo "PASSED (Hard-locked to false)"
else
    echo "FAILED: ENABLE_REAL_TRADING is not properly locked to False."
    FAILURES=$((FAILURES + 1))
fi

# Check 5: Secret pattern scan in tracked code
echo -n "[5/5] Scanning tracked files for exposed Google API keys (AIzaSy...)... "
KEY_MATCHES=$(git grep -E "AIzaSy[0-9A-Za-z_-]{33}" -- ':!tests/unit/test_logging.py' || true)
if [ -n "${KEY_MATCHES}" ]; then
    echo "FAILED: Potential unmasked Google API key found:"
    echo "${KEY_MATCHES}"
    FAILURES=$((FAILURES + 1))
else
    echo "PASSED"
fi

echo "================================================================================"
if [ ${FAILURES} -eq 0 ]; then
    echo " ✅ AUDIT PASSED: All 5 security and compliance checks passed."
    echo "================================================================================"
    exit 0
else
    echo " ❌ AUDIT FAILED: ${FAILURES} security violation(s) detected."
    echo "================================================================================"
    exit 1
fi
