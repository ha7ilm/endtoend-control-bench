TEST_MODULE = "tests/test_cruisecontrol_dt_limit_variant.py"

REASONS_BY_TEST = {
    "test_cruisecontrol_dt_lim_hondajazz_clamps_to_iso_asymmetric_limits": (
        "Verify the Honda Jazz cruisecontrol limit variant enforces asymmetric ISO force saturation exactly by comparing one-step "
        "state updates against clipped-force equivalents."
    ),
    "test_existing_cruisecontrol_variants_remain_unclamped": (
        "Protect existing cruisecontrol ctms variants from accidental saturation by confirming larger commands still change the "
        "next-step state more than sub-limit commands."
    ),
    "test_cruisecontrol_dt_lim_hondajazz_uses_expected_model_parameters": (
        "Ensure the Honda Jazz limited variant applies the intended plant mass/drag and asymmetric acceleration/deceleration "
        "force bounds."
    ),
}

REASONS_BY_NODEID = {}
