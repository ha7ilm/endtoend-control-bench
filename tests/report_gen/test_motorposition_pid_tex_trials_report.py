TEST_MODULE = "tests/test_motorposition_pid_tex_trials.py"

REASONS_BY_TEST = {
    "test_pid_from_motorposition_tex_trial8_settles_within_horizon": (
        "Check final MotorPosition.tex continuous-time PID gains satisfy basic closed-loop quality gates (settled, overshoot < 16%, "
        "rise/settling within simulation horizon)."
    ),
}

REASONS_BY_NODEID = {}
