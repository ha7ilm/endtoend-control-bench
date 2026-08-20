TEST_MODULE = "tests/test_motorspeed_settling_pid_tex.py"

REASONS_BY_TEST = {
    "test_pid_from_motorspeed_tex_settles_within_simulation_horizon": (
        "Ensure the tutorial PID gains from MotorSpeed.tex produce a response that settles before horizon end, preventing "
        "regressions in the canonical example controller."
    ),
}

REASONS_BY_NODEID = {}
