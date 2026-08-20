#!/usr/bin/env bash
set -euo pipefail

# Ensure any leftover process on port 9000 is killed (ignore “no process” error)
fuser -k 9000/tcp 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

PORT=9000
EXPERIMENT_ID="run_all_ct_examples"
ATTEMPT=0

MOTORSPEED_EXAMPLES=(
    controlclient.examples.ct.motorspeed_trial1_p
    controlclient.examples.ct.motorspeed_trial2_pid
    controlclient.examples.ct.motorspeed_trial3_pid
    controlclient.examples.ct.motorspeed_trial4_pid
)

MOTORPOSITION_EXAMPLES=(
    # controlclient.examples.ct.motorposition_trial1_p_kp1
    # controlclient.examples.ct.motorposition_trial2_p_kp11
    # controlclient.examples.ct.motorposition_trial3_p_kp21
    # controlclient.examples.ct.motorposition_trial4_pi_ki100
    # controlclient.examples.ct.motorposition_trial5_pi_ki300
    # controlclient.examples.ct.motorposition_trial6_pi_ki500
    # controlclient.examples.ct.motorposition_trial7_pid_kd005
    # controlclient.examples.ct.motorposition_trial8_pid_kd015
    # controlclient.examples.ct.motorposition_trial9_pid_kd025
)

CRUISECONTROL_EXAMPLES=(
    controlclient.examples.ct.cruisecontrol_trial1_p_kp100
    controlclient.examples.ct.cruisecontrol_trial2_p_kp5000
    controlclient.examples.ct.cruisecontrol_trial3_pi_kp600_ki1
    controlclient.examples.ct.cruisecontrol_trial4_pi_kp800_ki40
    controlclient.examples.ct.cruisecontrol_trial5_pid_kp1_ki1_kd1
)

SUSPENSION_EXAMPLES=(
    controlclient.examples.ct.suspension_trial1_pid_lowgain
    controlclient.examples.ct.suspension_trial2_pid_highgain
)

INVERTEDPENDULUM_EXAMPLES=(
    controlclient.examples.ct.invertedpendulum_trial1_pid_kp1_ki1_kd1
    controlclient.examples.ct.invertedpendulum_trial2_pid_kp100_ki1_kd1
    controlclient.examples.ct.invertedpendulum_trial3_pid_kp100_ki1_kd20
)

AIRCRAFTPITCH_EXAMPLES=(
    controlclient.examples.ct.aircraftpitch_trial1_p_kp2
    controlclient.examples.ct.aircraftpitch_trial2_p_kp11269
    controlclient.examples.ct.aircraftpitch_trial3_pi_kp113_ki00263
    controlclient.examples.ct.aircraftpitch_trial4_pid_kp10482_ki05241_kd05241
    controlclient.examples.ct.aircraftpitch_trial5_pid_kp417_ki12882_kd026
    controlclient.examples.ct.aircraftpitch_trial6_pid_kp51852_ki174_kd298
)

BALLANDBEAM_EXAMPLES=(
    controlclient.examples.ct.ballandbeam_trial1_p_kp1
    controlclient.examples.ct.ballandbeam_trial2_pd_kp10_kd10
    controlclient.examples.ct.ballandbeam_trial3_pd_kp10_kd20
    controlclient.examples.ct.ballandbeam_trial4_pd_kp15_kd40
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

    # Wait for the server to start listening.
    sleep 0.5

    for example in "${examples[@]}"; do
        echo "--- Running $example ---"
        URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES=0 URLETRA_MACHINE_PORT="$PORT" python -m "$example"
    done

    echo "=== Stopping server for setup: $setup ==="
    kill "$server_pid"
    wait "$server_pid" 2>/dev/null || true
}

run_setup motorspeed_ct "${MOTORSPEED_EXAMPLES[@]}"
# run_setup motorposition_ct "${MOTORPOSITION_EXAMPLES[@]}"
run_setup cruisecontrol_ct "${CRUISECONTROL_EXAMPLES[@]}"
run_setup suspension_ct "${SUSPENSION_EXAMPLES[@]}"
run_setup invertedpendulum_ct "${INVERTEDPENDULUM_EXAMPLES[@]}"
run_setup aircraftpitch_ct "${AIRCRAFTPITCH_EXAMPLES[@]}"
run_setup ballandbeam_ct "${BALLANDBEAM_EXAMPLES[@]}"

echo "=== All CT examples completed ==="
