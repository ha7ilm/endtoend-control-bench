TEST_MODULE = "tests/test_kpi_modes.py"

REASONS_BY_TEST = {
    "test_step_mode_is_default_for_tracking_setups": (
        "Protect default KPI semantics by requiring tracking setups (e.g., motorspeed) to use step-mode calculations."
    ),
    "test_step_mode_kpis_follow_reference_step_semantics": (
        "Regression-check step KPI formulas on synthetic signals so overshoot, settling time, and steady-state error "
        "remain numerically consistent with expected definitions."
    ),
    "test_step_mode_target_band_not_final_sample_band": (
        "Ensure step settling uses the fixed target band around the commanded reference, not a band around the final "
        "sample, so slowly rising traces are not incorrectly marked as settled."
    ),
    "test_step_mode_matches_python_control_for_stable_step_trace": (
        "Cross-validate rise and settling time against python-control step_info on a stable step trace to keep KPI "
        "implementation aligned with standard control-toolbox semantics."
    ),
    "test_disturbance_mode_uses_warmup_event_and_zero_target": (
        "Validate disturbance-mode KPI interpretation for suspension, including warmup-based event start and zero-target "
        "error normalization behavior."
    ),
    "test_suspension_disturbance_starts_after_warmup_samples": (
        "Guarantee disturbance injection scheduling starts exactly at warmup_samples for suspension setups, preventing "
        "off-by-one timing regressions."
    ),
}

REASONS_BY_NODEID = {}
