TEST_MODULE = "tests/test_cruisecontrol_pid_tex_trials.py"

REASONS_BY_TEST = {
    "test_pi_from_cruisecontrol_tex_trial4_meets_specs": (
        "Validate that the PI gains taken from CruiseControl.tex satisfy documented requirements (rise < 5 s, "
        "overshoot < 10%, steady-state error < 2%, and settled)."
    ),
}

REASONS_BY_NODEID = {}
