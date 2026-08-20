TEST_MODULE = "tests/test_motorspeed_dt_limit_variant.py"

REASONS_BY_TEST = {
    "test_motorspeed_dt_lim_clamps_to_pm_24_volts": (
        "Verify the motorspeed_dt_lim setup enforces +/-24 V actuator saturation exactly by comparing one-step state updates "
        "against unclamped setup evaluated at clipped inputs."
    ),
    "test_existing_motorspeed_variants_remain_unclamped": (
        "Protect backward compatibility of existing motorspeed variants by confirming behavior at 25 V still differs from "
        "24 V, i.e., no accidental clamp introduced."
    ),
    "test_motorspeed_dt_lim_maxonre30_clamps_to_pm_36_volts": (
        "Verify the Maxon RE30 limited variant enforces +/-36 V saturation exactly by comparing saturated extreme inputs "
        "to explicit +/-36 V one-step responses."
    ),
    "test_motorspeed_dt_lim_maxonre30_uses_expected_model_parameters": (
        "Lock in the configured Maxon RE30 plant constants and voltage limit so variant wiring/regression changes cannot "
        "silently alter controller design assumptions."
    ),
}

REASONS_BY_NODEID = {}
