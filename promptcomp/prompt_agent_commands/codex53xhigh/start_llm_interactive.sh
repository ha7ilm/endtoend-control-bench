#!/usr/bin/env bash
set -euo pipefail

START_TS="$(date +%Y%m%d_%H%M%S)"
GRR="$(git rev-parse --show-toplevel)"
SERVER_LOG_DIR="$GRR/results/current_run/server_logs"
mkdir -p $SERVER_LOG_DIR

pushd $GRR
python -m controlserver.server \
    --port 9000 \
    --setup %SETUP% \
    --experiment_id %CASE% \
    --design_attempt %ATTEMPT% \
    >"${SERVER_LOG_DIR}/server_%SETUP%_%CASE%_attempt%ATTEMPT%_${START_TS}.log" 2>&1 &
trap 'fuser -k "9000/tcp" || true' EXIT
popd

cd ./lwp/rlwp
codexs --model gpt-5.3-codex --config model_reasoning_effort="xhigh"
