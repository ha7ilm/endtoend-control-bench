TEST_MODULE = "tests/test_aircraftpitch_ct_pid_tex_trials.py"

REASONS_BY_TEST = {
    "test_aircraftpitch_tex_ct_pid_trials_have_finite_signals": (
        "Validate that every PID gain set copied from AircraftPitch.tex produces numerically stable "
        "closed-loop traces in the continuous-time variant, so later KPI checks are not based on NaN/Inf artifacts."
    ),
    "test_aircraftpitch_tex_ct_final_pid_meets_specs": (
        "Enforce the final AircraftPitch.tex design targets (overshoot < 10%, rise time < 2 s, settling < 10 s, "
        "steady-state error < 3.5%, and settled-within-horizon) for the recommended final PID gains."
    ),
}

REASONS_BY_NODEID = {}
