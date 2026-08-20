TEST_MODULE = "tests/test_aircraftpitch_digital_trials.py"

REASONS_BY_TEST = {
    "test_aircraftpitch_digital_baseline_runs_with_finite_outputs": (
        "Smoke-check the baseline digital LQR simulation for finite measured pitch and control effort so numerical "
        "issues are caught before interpreting controller quality metrics."
    ),
    "test_aircraftpitch_digital_baseline_responds_to_step_reference": (
        "Confirm that the baseline DLQR without precompensation responds in the expected qualitative way: non-zero "
        "positive final value with bounded magnitude (< 0.2 rad), matching intended under-tracking behavior."
    ),
    "test_aircraftpitch_precompensator_reduces_steady_state_error": (
        "Verify that enabling Nbar precompensation improves steady-state tracking versus baseline, protecting the "
        "intended design progression from regression."
    ),
}

REASONS_BY_NODEID = {}
