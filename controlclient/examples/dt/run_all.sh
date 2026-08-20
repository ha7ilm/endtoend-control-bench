#!/usr/bin/env bash
set -euo pipefail

# Ensure any leftover process on port 9000 is killed (ignore “no process” error)
fuser -k 9000/tcp 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

PORT=9000
EXPERIMENT_ID="run_all_dt_examples"
ATTEMPT=0

MOTORSPEED_EXAMPLES=(
    controlclient.examples.dt.motorspeed_digital_trial1_uncompensated
    controlclient.examples.dt.motorspeed_digital_trial2_pid_tustin
    controlclient.examples.dt.motorspeed_digital_trial3_modified_pid
)

MOTORSPEED_MAXONRE30_ONLY_EXAMPLES=(
    controlclient.examples.dt.motorspeed_digital_gpt_maxonre30_spec_met
)

MOTORPOSITION_EXAMPLES=(
    # controlclient.examples.dt.motorposition_digital_trial1_uncompensated
    # controlclient.examples.dt.motorposition_digital_trial2_integrator_zero
    # controlclient.examples.dt.motorposition_digital_trial3_add_pole_near_mz
    # controlclient.examples.dt.motorposition_digital_trial4_add_two_zeros_one_pole
    # controlclient.examples.dt.motorposition_digital_trial5_final_gain800
)

CRUISECONTROL_EXAMPLES=(
    controlclient.examples.dt.cruisecontrol_digital_trial1_gain_only
    controlclient.examples.dt.cruisecontrol_digital_trial2_lag_compensated
)

SUSPENSION_EXAMPLES=(
    controlclient.examples.dt.suspension_digital_trial1_open_loop
    controlclient.examples.dt.suspension_digital_trial2_place_observer_feedback
    controlclient.examples.dt.suspension_digital_trial3_state_estimator_feedback_extra
)

INVERTEDPENDULUM_EXAMPLES=(
    controlclient.examples.dt.invertedpendulum_digital_trial1_lqr_baseline
    controlclient.examples.dt.invertedpendulum_digital_trial2_lqr_tuned_q
    controlclient.examples.dt.invertedpendulum_digital_trial3_lqr_precomp_nbar
    controlclient.examples.dt.invertedpendulum_digital_trial4_observer_state_feedback
)

AIRCRAFTPITCH_EXAMPLES=(
    controlclient.examples.dt.aircraftpitch_digital_trial1_dlqr_baseline
    controlclient.examples.dt.aircraftpitch_digital_trial2_dlqr_precomp_nbar
)

BALLANDBEAM_EXAMPLES=(
    controlclient.examples.dt.ballandbeam_digital_trial1_open_loop
    controlclient.examples.dt.ballandbeam_digital_trial2_p_kp100
    controlclient.examples.dt.ballandbeam_digital_trial3_pd_kp100_kd10
    controlclient.examples.dt.ballandbeam_digital_trial4_pd_kp1000_kd10
)

run_setup() {
    local setup="$1"
    shift
    local examples=("$@")

    echo "=== Starting server for setup: $setup ==="
    python -m controlserver.server \
        --port "$PORT" \
        --setup "$setup" \
        --experiment_id "$EXPERIMENT_ID" \
        --design_attempt "$ATTEMPT" &
    local server_pid=$!

    sleep 0.5

    for example in "${examples[@]}"; do
        echo "--- Running $example ---"
        URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES=0 URLETRA_MACHINE_PORT="$PORT" python -m "$example"
    done

    echo "=== Stopping server for setup: $setup ==="
    kill "$server_pid"
    wait "$server_pid" 2>/dev/null || true
}

run_setup_with_cli_setup() {
    local setup="$1"
    shift
    local examples=("$@")

    echo "=== Starting server for setup: $setup ==="
    python -m controlserver.server \
        --port "$PORT" \
        --setup "$setup" \
        --experiment_id "$EXPERIMENT_ID" \
        --design_attempt "$ATTEMPT" &
    local server_pid=$!

    sleep 0.5

    for example in "${examples[@]}"; do
        echo "--- Running $example --setup $setup ---"
        URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES=0 URLETRA_MACHINE_PORT="$PORT" python -m "$example" --setup "$setup"
    done

    echo "=== Stopping server for setup: $setup ==="
    kill "$server_pid"
    wait "$server_pid" 2>/dev/null || true
}

run_setup_with_cli_setup motorspeed_dt "${MOTORSPEED_EXAMPLES[@]}"
run_setup_with_cli_setup motorspeed_dt_lim "${MOTORSPEED_EXAMPLES[@]}"
run_setup_with_cli_setup motorspeed_dt_lim_maxonre30 "${MOTORSPEED_EXAMPLES[@]}"
# Maxon-only tuned controller that is intentionally restricted to this setup.
run_setup_with_cli_setup motorspeed_dt_lim_maxonre30 "${MOTORSPEED_MAXONRE30_ONLY_EXAMPLES[@]}"
# run_setup motorposition_dt "${MOTORPOSITION_EXAMPLES[@]}"
run_setup_with_cli_setup cruisecontrol_dt "${CRUISECONTROL_EXAMPLES[@]}"
run_setup_with_cli_setup cruisecontrol_dt_lim_hondajazz "${CRUISECONTROL_EXAMPLES[@]}"
run_setup suspension_dt "${SUSPENSION_EXAMPLES[@]}"
run_setup aircraftpitch_dt "${AIRCRAFTPITCH_EXAMPLES[@]}"
run_setup_with_cli_setup invertedpendulum_dt "${INVERTEDPENDULUM_EXAMPLES[@]}"
run_setup_with_cli_setup invertedpendulum_dt_nl "${INVERTEDPENDULUM_EXAMPLES[@]}"
run_setup_with_cli_setup invertedpendulum_dt_nl_quanserip02 "${INVERTEDPENDULUM_EXAMPLES[@]}"
run_setup_with_cli_setup invertedpendulum_dt_nl_lim_quanserip02 "${INVERTEDPENDULUM_EXAMPLES[@]}"
run_setup_with_cli_setup ballandbeam_dt "${BALLANDBEAM_EXAMPLES[@]}"
run_setup_with_cli_setup ballandbeam_dt_nl "${BALLANDBEAM_EXAMPLES[@]}"
run_setup_with_cli_setup ballandbeam_dt_nl_act "${BALLANDBEAM_EXAMPLES[@]}"
run_setup_with_cli_setup ballandbeam_dt_nl_act_mg996r "${BALLANDBEAM_EXAMPLES[@]}"

echo "=== All digital examples completed ==="
