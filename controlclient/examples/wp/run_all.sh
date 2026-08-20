#!/usr/bin/env bash
set -euo pipefail

# Ensure any leftover process on port 9000 is killed (ignore "no process" error)
fuser -k 9000/tcp 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

PORT=9000
EXPERIMENT_ID="run_all_wp_examples"
ATTEMPT=0

run_setup_example() {
    local setup="$1"
    local example="$2"

    echo "=== Starting server for setup: $setup ==="
    python -m controlserver.server \
        --port "$PORT" \
        --setup "$setup" \
        --experiment_id "$EXPERIMENT_ID" \
        --design_attempt "$ATTEMPT" &
    local server_pid=$!

    sleep 0.5

    echo "--- Running $example ---"
    (
        cd "$SCRIPT_DIR"
        PYTHONPATH="$REPO_ROOT" URLETRA_MACHINE_PORT="$PORT" python -m "$example"
    )

    echo "=== Stopping server for setup: $setup ==="
    kill "$server_pid"
    wait "$server_pid" 2>/dev/null || true
}

run_setup_example aircraftpitch_dt controlclient.examples.wp.aircraftpitch_dt_p1
run_setup_example ballandbeam_dt controlclient.examples.wp.ballandbeam_dt_p1
run_setup_example ballandbeam_dt_nl_act_mg996r controlclient.examples.wp.ballandbeam_dt_nl_act_mg996r_p1
run_setup_example cruisecontrol_dt controlclient.examples.wp.cruisecontrol_dt_p1
run_setup_example cruisecontrol_dt_lim_hondajazz controlclient.examples.wp.cruisecontrol_dt_lim_hondajazz_p1
run_setup_example invertedpendulum_dt controlclient.examples.wp.invertedpendulum_dt_p1
run_setup_example invertedpendulum_dt_nl_lim_quanserip02 controlclient.examples.wp.invertedpendulum_dt_nl_lim_quanserip02_p1
run_setup_example motorspeed_dt controlclient.examples.wp.motorspeed_dt_p1
run_setup_example motorspeed_dt_lim_maxonre30 controlclient.examples.wp.motorspeed_dt_lim_maxonre30_p1

echo "=== All WP examples completed ==="
