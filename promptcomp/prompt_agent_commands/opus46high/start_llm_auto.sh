#!/usr/bin/env bash
set -euo pipefail

START_TS="$(date +%Y%m%d_%H%M%S)"
GRR="$(git rev-parse --show-toplevel)"
SERVER_LOG_DIR="$GRR/results/current_run/server_logs"
mkdir -p $SERVER_LOG_DIR
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_FILE="${SCRIPT_DIR}/prompt.md"
CLAUDE_LOG=".claude/claude_log_${START_TS}.jsonl"

mkdir -p "${SERVER_LOG_DIR}"

pushd $GRR
python -m controlserver.server \
    --port 9000 \
    --setup %SETUP% \
    --experiment_id %CASE% \
    --design_attempt %ATTEMPT% \
    >"${SERVER_LOG_DIR}/server_%SETUP%_%CASE%_%ATTEMPT%_${START_TS}.log" 2>&1 &
popd

trap 'fuser -k "9000/tcp" || true' EXIT

cd ./lwp/rlwp
mkdir -p .claude

export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
cat "${PROMPT_FILE}" | claudes -p --verbose --model opus --dangerously-skip-permissions --disallowedTools "Bash(rm:*),Bash(curl:*),Bash(git:*),WebFetch,WebSearch" --output-format stream-json | tee "${CLAUDE_LOG}" | python $GRR/dashes/claude_viewer_pv.py
