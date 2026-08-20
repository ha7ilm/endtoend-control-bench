#!/usr/bin/env bash
set -euo pipefail

START_TS="$(date +%Y%m%d_%H%M%S)"
GRR="$(git rev-parse --show-toplevel)"
SERVER_LOG_DIR="$GRR/results/current_run/server_logs"
mkdir -p $SERVER_LOG_DIR
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_FILE="${SCRIPT_DIR}/prompt.md"
CODEXS_LOG=".codex/codexs_log_${START_TS}.log"

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
mkdir -p .codex

cat "${PROMPT_FILE}" | codexs exec --model gpt-5.3-codex --config model_reasoning_effort="xhigh" --sandbox workspace-write --config sandbox_workspace_write.network_access="true" --skip-git-repo-check --json | tee "${CODEXS_LOG}" | python $GRR/dashes/codex_viewer_pv.py
