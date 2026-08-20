TEST_MODULE = "tests/test_motorposition_digital_trials.py"

REASONS_BY_TEST = {
    "test_final_root_locus_compensator_meets_digital_specs": (
        "Validate final root-locus compensator meets digital MotorPosition acceptance thresholds: settled, overshoot < 16%, "
        "and settling time < 0.04 s."
    ),
    "test_final_compensator_reduces_ss_error_vs_uncompensated": (
        "Ensure final compensator improves steady-state error compared to uncompensated baseline, preserving design-step "
        "improvement direction."
    ),
}

REASONS_BY_NODEID = {}
