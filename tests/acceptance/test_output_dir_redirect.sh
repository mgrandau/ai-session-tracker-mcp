#!/usr/bin/env bash
# =============================================================================
# Acceptance Test: AI_OUTPUT_DIR environment variable redirect (Issue #19)
#
# Verifies that when AI_OUTPUT_DIR is set, ALL session data goes to the
# specified directory and NOTHING is created in the default .ai_sessions dir.
#
# This is an integration/acceptance test that runs outside the unit test
# framework. It spawns a real environment, uses the CLI to create and
# complete a session, and inspects the filesystem for correctness.
#
# Usage:
#   ./tests/acceptance/test_output_dir_redirect.sh
#
# Requirements:
#   - ai-session-tracker CLI available (pip install or pdm install)
#   - Run from the repo root, or set REPO_ROOT
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

log_pass() {
    echo -e "  ${GREEN}✅ PASS${NC}: $1"
    PASS=$((PASS + 1))
}

log_fail() {
    echo -e "  ${RED}❌ FAIL${NC}: $1"
    FAIL=$((FAIL + 1))
}

log_info() {
    echo -e "  ${YELLOW}ℹ️${NC}  $1"
}

# ── Setup ────────────────────────────────────────────────────────────────────

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
TEST_ROOT=$(mktemp -d "/tmp/ast-acceptance-XXXXXX")
WORK_DIR="${TEST_ROOT}/project"
CUSTOM_OUTPUT="${TEST_ROOT}/custom-output"
DEFAULT_DIR="${WORK_DIR}/.ai_sessions"

echo "============================================================"
echo " Acceptance Test: AI_OUTPUT_DIR redirect (Issue #19)"
echo "============================================================"
echo ""
echo "  Repo root:      ${REPO_ROOT}"
echo "  Test root:       ${TEST_ROOT}"
echo "  Work dir:        ${WORK_DIR}"
echo "  Custom output:   ${CUSTOM_OUTPUT}"
echo "  Default dir:     ${DEFAULT_DIR}"
echo ""

# Create the working directory (simulates a project)
mkdir -p "${WORK_DIR}"

# Activate venv if present
if [ -f "${REPO_ROOT}/.venv/bin/activate" ]; then
    source "${REPO_ROOT}/.venv/bin/activate"
    log_info "Activated venv: ${REPO_ROOT}/.venv"
fi

# Verify CLI is available
if ! command -v ai-session-tracker &>/dev/null; then
    echo -e "${RED}ERROR: ai-session-tracker CLI not found in PATH${NC}"
    echo "Run 'pdm install' in ${REPO_ROOT} first."
    rm -rf "${TEST_ROOT}"
    exit 1
fi

CLI_VERSION=$(ai-session-tracker --version 2>&1 || echo "unknown")
log_info "CLI version: ${CLI_VERSION}"

# ── Cleanup trap ─────────────────────────────────────────────────────────────

cleanup() {
    echo ""
    echo "── Cleanup ──"
    rm -rf "${TEST_ROOT}"
    log_info "Removed ${TEST_ROOT}"
}
trap cleanup EXIT

# =============================================================================
# TEST 1: Default behavior (no AI_OUTPUT_DIR) — baseline
# =============================================================================
echo ""
echo "── Test 1: Default behavior (no AI_OUTPUT_DIR) ──"

cd "${WORK_DIR}"
unset AI_OUTPUT_DIR 2>/dev/null || true

# Start a session
RESULT=$(ai-session-tracker start \
    --name "baseline-test" \
    --type code_generation \
    --model "test-model" \
    --mins 10 \
    --source manual \
    --developer "test-user" \
    --project "test-project" \
    --json 2>/dev/null)

SESSION_ID=$(echo "${RESULT}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',d).get('session_id',''))" 2>/dev/null || echo "")

if [ -z "${SESSION_ID}" ]; then
    log_fail "Could not start baseline session"
    echo "  CLI output: ${RESULT}"
else
    log_pass "Started baseline session: ${SESSION_ID}"
fi

# Verify default dir was created
if [ -d "${DEFAULT_DIR}" ]; then
    log_pass "Default .ai_sessions directory created at ${DEFAULT_DIR}"
else
    log_fail "Default .ai_sessions directory NOT created (expected at ${DEFAULT_DIR})"
fi

# Verify session file has data
if [ -f "${DEFAULT_DIR}/sessions.json" ]; then
    SESSION_COUNT=$(python3 -c "import json; print(len(json.load(open('${DEFAULT_DIR}/sessions.json'))))" 2>/dev/null || echo "0")
    if [ "${SESSION_COUNT}" -gt 0 ]; then
        log_pass "sessions.json has ${SESSION_COUNT} session(s) in default dir"
    else
        log_fail "sessions.json is empty in default dir"
    fi
else
    log_fail "sessions.json not found in default dir"
fi

# End the baseline session
if [ -n "${SESSION_ID}" ]; then
    ai-session-tracker end \
        --session-id "${SESSION_ID}" \
        --outcome success \
        --notes "baseline acceptance test" \
        --json >/dev/null 2>&1
    log_pass "Ended baseline session"
fi

# Clean up default dir for next test
rm -rf "${DEFAULT_DIR}"
log_info "Cleaned up default dir for redirect test"

# =============================================================================
# TEST 2: AI_OUTPUT_DIR set — the actual bug test
# =============================================================================
echo ""
echo "── Test 2: AI_OUTPUT_DIR redirect ──"

cd "${WORK_DIR}"
export AI_OUTPUT_DIR="${CUSTOM_OUTPUT}"
log_info "AI_OUTPUT_DIR=${AI_OUTPUT_DIR}"

# Verify the custom dir does NOT exist yet
if [ ! -d "${CUSTOM_OUTPUT}" ]; then
    log_pass "Custom output dir does not exist yet (will be auto-created)"
else
    log_fail "Custom output dir already exists before test"
fi

# Verify default dir does NOT exist
if [ ! -d "${DEFAULT_DIR}" ]; then
    log_pass "Default .ai_sessions dir does not exist before test"
else
    log_fail "Default .ai_sessions dir exists before test (should have been cleaned)"
fi

# Start a session with AI_OUTPUT_DIR set
RESULT2=$(ai-session-tracker start \
    --name "redirect-test" \
    --type debugging \
    --model "test-model-v2" \
    --mins 15 \
    --source manual \
    --developer "test-user" \
    --project "test-project" \
    --json 2>/dev/null)

SESSION_ID2=$(echo "${RESULT2}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',d).get('session_id',''))" 2>/dev/null || echo "")

if [ -z "${SESSION_ID2}" ]; then
    log_fail "Could not start redirect session"
    echo "  CLI output: ${RESULT2}"
else
    log_pass "Started redirect session: ${SESSION_ID2}"
fi

# ── CRITICAL ASSERTION: default dir must NOT exist ──
if [ ! -d "${DEFAULT_DIR}" ]; then
    log_pass "Default .ai_sessions dir was NOT created (correct!)"
else
    log_fail "Default .ai_sessions dir WAS created — BUG CONFIRMED (Issue #19)"
    echo "  Contents of default dir:"
    ls -la "${DEFAULT_DIR}" 2>/dev/null || true
fi

# ── CRITICAL ASSERTION: custom dir must exist ──
if [ -d "${CUSTOM_OUTPUT}" ]; then
    log_pass "Custom output dir was created at ${CUSTOM_OUTPUT}"
else
    log_fail "Custom output dir was NOT created"
fi

# Verify session data is in custom dir
if [ -f "${CUSTOM_OUTPUT}/sessions.json" ]; then
    SESSION_COUNT2=$(python3 -c "import json; print(len(json.load(open('${CUSTOM_OUTPUT}/sessions.json'))))" 2>/dev/null || echo "0")
    if [ "${SESSION_COUNT2}" -gt 0 ]; then
        log_pass "sessions.json has ${SESSION_COUNT2} session(s) in custom dir"
    else
        log_fail "sessions.json is empty in custom dir"
    fi
else
    log_fail "sessions.json not found in custom dir"
fi

# Log an interaction
if [ -n "${SESSION_ID2}" ]; then
    ai-session-tracker log \
        --session-id "${SESSION_ID2}" \
        --prompt "Test prompt for redirect" \
        --summary "Test response for redirect" \
        --rating 4 \
        --json >/dev/null 2>&1
    log_pass "Logged interaction to redirect session"

    # Verify interaction landed in custom dir
    if [ -f "${CUSTOM_OUTPUT}/interactions.json" ]; then
        INT_COUNT=$(python3 -c "import json; print(len(json.load(open('${CUSTOM_OUTPUT}/interactions.json'))))" 2>/dev/null || echo "0")
        if [ "${INT_COUNT}" -gt 0 ]; then
            log_pass "interactions.json has ${INT_COUNT} interaction(s) in custom dir"
        else
            log_fail "interactions.json is empty in custom dir"
        fi
    else
        log_fail "interactions.json not found in custom dir"
    fi
fi

# End the redirect session
if [ -n "${SESSION_ID2}" ]; then
    ai-session-tracker end \
        --session-id "${SESSION_ID2}" \
        --outcome success \
        --notes "redirect acceptance test" \
        --json >/dev/null 2>&1
    log_pass "Ended redirect session"

    # Verify session was updated (status=completed)
    if [ -f "${CUSTOM_OUTPUT}/sessions.json" ]; then
        STATUS=$(python3 -c "
import json
sessions = json.load(open('${CUSTOM_OUTPUT}/sessions.json'))
s = sessions.get('${SESSION_ID2}', {})
print(s.get('status', 'unknown'))
" 2>/dev/null || echo "unknown")
        if [ "${STATUS}" = "completed" ]; then
            log_pass "Session status is 'completed' in custom dir"
        else
            log_fail "Session status is '${STATUS}', expected 'completed'"
        fi
    fi
fi

# =============================================================================
# TEST 3: Install → parse mcp.json → run with env override
# =============================================================================
echo ""
echo "── Test 3: Install-generated config with AI_OUTPUT_DIR override ──"

# Set up a fresh project directory for install test
INSTALL_DIR="${TEST_ROOT}/install-project"
INSTALL_OUTPUT="${TEST_ROOT}/install-output"
INSTALL_DEFAULT="${INSTALL_DIR}/.ai_sessions"
mkdir -p "${INSTALL_DIR}"
cd "${INSTALL_DIR}"

unset AI_OUTPUT_DIR 2>/dev/null || true

# Run the install command to generate mcp.json
ai-session-tracker install >/dev/null 2>&1
log_info "Ran 'ai-session-tracker install' in ${INSTALL_DIR}"

MCP_JSON="${INSTALL_DIR}/.vscode/mcp.json"

if [ -f "${MCP_JSON}" ]; then
    log_pass "mcp.json created at ${MCP_JSON}"
else
    log_fail "mcp.json NOT created by install"
fi

# Parse the generated mcp.json — extract command and args
if [ -f "${MCP_JSON}" ]; then
    PARSED=$(python3 -c "
import json, sys

config = json.load(open('${MCP_JSON}'))
server = config.get('servers', {}).get('ai-session-tracker', {})
command = server.get('command', '')
args = server.get('args', [])

# Check for _env_example (the documentation block)
env_example = server.get('_env_example', {})
has_env_block = 'env' in server
has_env_example = '_env_example' in server

print(json.dumps({
    'command': command,
    'args': args,
    'has_env_block': has_env_block,
    'has_env_example': has_env_example,
    'env_example': env_example,
    'env': server.get('env', {}),
}))
" 2>/dev/null || echo "{}")

    CMD=$(echo "${PARSED}" | python3 -c "import sys,json; print(json.load(sys.stdin)['command'])" 2>/dev/null || echo "")
    ARGS=$(echo "${PARSED}" | python3 -c "import sys,json; print(' '.join(json.load(sys.stdin)['args']))" 2>/dev/null || echo "")
    HAS_ENV=$(echo "${PARSED}" | python3 -c "import sys,json; print(json.load(sys.stdin)['has_env_block'])" 2>/dev/null || echo "")
    HAS_ENV_EX=$(echo "${PARSED}" | python3 -c "import sys,json; print(json.load(sys.stdin)['has_env_example'])" 2>/dev/null || echo "")

    log_info "Parsed from mcp.json:"
    log_info "  command: ${CMD}"
    log_info "  args: ${ARGS}"
    log_info "  has 'env' block: ${HAS_ENV}"
    log_info "  has '_env_example' block: ${HAS_ENV_EX}"

    if [ "${HAS_ENV_EX}" = "True" ]; then
        log_pass "Install generated _env_example block (documentation)"
    else
        log_fail "Install did NOT generate _env_example block"
    fi

    # NOTE: This is the UX issue — install creates _env_example but not env.
    # The MCP host only reads 'env', not '_env_example'.
    if [ "${HAS_ENV}" = "True" ]; then
        log_info "'env' block exists in generated config"
    else
        log_info "No 'env' block in generated config (user must create manually)"
    fi

    # Now run using the parsed command + args, with AI_OUTPUT_DIR override
    # This simulates what happens when a user sets the env var and the MCP
    # host spawns the server — except we're using the CLI directly.
    if [ -n "${CMD}" ]; then
        log_info "Running session lifecycle using installed config + AI_OUTPUT_DIR override"
        export AI_OUTPUT_DIR="${INSTALL_OUTPUT}"

        # Clean up any default dir that install may have created
        rm -rf "${INSTALL_DEFAULT}"

        # Start session using the command from mcp.json (but via CLI, not server mode)
        RESULT3=$(ai-session-tracker start \
            --name "install-config-test" \
            --type testing \
            --model "config-model" \
            --mins 5 \
            --source manual \
            --developer "test-user" \
            --project "install-project" \
            --json 2>/dev/null)

        SESSION_ID3=$(echo "${RESULT3}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',d).get('session_id',''))" 2>/dev/null || echo "")

        if [ -z "${SESSION_ID3}" ]; then
            log_fail "Could not start session using installed config"
        else
            log_pass "Started session from installed config: ${SESSION_ID3}"
        fi

        # CRITICAL: default dir must NOT exist
        if [ ! -d "${INSTALL_DEFAULT}" ]; then
            log_pass "Default .ai_sessions NOT created when using install config + AI_OUTPUT_DIR"
        else
            log_fail "Default .ai_sessions WAS created — install config does not properly support AI_OUTPUT_DIR"
            echo "  Contents:"
            ls -la "${INSTALL_DEFAULT}" 2>/dev/null || true
        fi

        # Custom dir must have the data
        if [ -d "${INSTALL_OUTPUT}" ]; then
            log_pass "AI_OUTPUT_DIR path created: ${INSTALL_OUTPUT}"
        else
            log_fail "AI_OUTPUT_DIR path was NOT created"
        fi

        if [ -f "${INSTALL_OUTPUT}/sessions.json" ]; then
            S3_COUNT=$(python3 -c "import json; print(len(json.load(open('${INSTALL_OUTPUT}/sessions.json'))))" 2>/dev/null || echo "0")
            if [ "${S3_COUNT}" -gt 0 ]; then
                log_pass "sessions.json has ${S3_COUNT} session(s) in AI_OUTPUT_DIR"
            else
                log_fail "sessions.json is empty in AI_OUTPUT_DIR"
            fi
        else
            log_fail "sessions.json not found in AI_OUTPUT_DIR"
        fi

        # Log interaction
        if [ -n "${SESSION_ID3}" ]; then
            ai-session-tracker log \
                --session-id "${SESSION_ID3}" \
                --prompt "Test from installed config" \
                --summary "Verifying install + env override" \
                --rating 5 \
                --json >/dev/null 2>&1
            log_pass "Logged interaction via installed config"
        fi

        # End session
        if [ -n "${SESSION_ID3}" ]; then
            ai-session-tracker end \
                --session-id "${SESSION_ID3}" \
                --outcome success \
                --notes "install config acceptance test" \
                --json >/dev/null 2>&1
            log_pass "Ended session via installed config"

            # Verify completed status
            if [ -f "${INSTALL_OUTPUT}/sessions.json" ]; then
                STATUS3=$(python3 -c "
import json
sessions = json.load(open('${INSTALL_OUTPUT}/sessions.json'))
s = sessions.get('${SESSION_ID3}', {})
print(s.get('status', 'unknown'))
" 2>/dev/null || echo "unknown")
                if [ "${STATUS3}" = "completed" ]; then
                    log_pass "Session completed in AI_OUTPUT_DIR via installed config"
                else
                    log_fail "Session status '${STATUS3}', expected 'completed'"
                fi
            fi
        fi

        # FINAL: default dir still must not exist
        if [ ! -d "${INSTALL_DEFAULT}" ]; then
            log_pass "Default .ai_sessions still absent after full lifecycle via installed config"
        else
            log_fail "Default .ai_sessions appeared during installed config lifecycle"
        fi

        echo ""
        echo "── Install output dir contents ──"
        if [ -d "${INSTALL_OUTPUT}" ]; then
            ls -la "${INSTALL_OUTPUT}/"
        else
            echo "  (directory does not exist)"
        fi
    fi
fi

# ── FINAL CHECK: default dir still must NOT exist (Test 2) ──
echo ""
echo "── Final verification ──"

if [ ! -d "${DEFAULT_DIR}" ]; then
    log_pass "Default .ai_sessions dir still does not exist after full lifecycle"
else
    log_fail "Default .ai_sessions dir appeared during session lifecycle — BUG"
    echo "  Contents:"
    ls -la "${DEFAULT_DIR}" 2>/dev/null || true
fi

# Verify custom dir has all expected files
echo ""
echo "── Custom output dir contents ──"
if [ -d "${CUSTOM_OUTPUT}" ]; then
    ls -la "${CUSTOM_OUTPUT}/"
else
    echo "  (directory does not exist)"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "============================================================"
echo " Results: ${PASS} passed, ${FAIL} failed"
echo "============================================================"

if [ "${FAIL}" -gt 0 ]; then
    echo -e "${RED}FAILED${NC} — Issue #19 bug is present"
    exit 1
else
    echo -e "${GREEN}ALL PASSED${NC} — AI_OUTPUT_DIR redirect works correctly"
    exit 0
fi
