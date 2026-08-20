TEST_MODULE = "tests/test_motorspeed_digital_trials.py"

REASONS_BY_TEST = {
    "test_modified_digital_pid_meets_motorspeed_specs": (
        "Validate modified digital PID polynomial form meets Motorspeed targets: settled response, overshoot < 5%, and "
        "steady-state error < 1%."
    ),
    "test_modified_controller_improves_on_raw_tustin_pid": (
        "Ensure modified controller architecture improves steady-state error relative to raw Tustin PID, capturing the "
        "intended benefit of additional pole/scale shaping."
    ),
    "test_gpt_maxonre30_pi_meets_motorspeed_specs": (
        "Verify the Maxon RE30-specific digital PI controller meets Motorspeed design limits for settling time, overshoot, "
        "and steady-state error on motorspeed_dt_lim_maxonre30."
    ),
}

REASONS_BY_NODEID = {}
