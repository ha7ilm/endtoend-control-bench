TEST_MODULE = "tests/test_setups_and_cli.py"

REASONS_BY_TEST = {
    "test_setup_registry_includes_all_supported_variants": (
        "Verify setup registry exposes exactly the supported variant names (dt/ct plus explicit nonlinear and limited variants) "
        "and excludes legacy base names."
    ),
    "test_variant_configs_have_expected_sampling_and_shared_fields": (
        "Check each variant config preserves expected dt relationships and shared fields (horizon, warmup, step_ref), including "
        "extra dt-only variants inheriting base dt setup values."
    ),
    "test_create_setup_returns_expected_variant_name": (
        "For every declared variant name, ensure create_setup instantiates a setup whose runtime name matches exactly, catching "
        "registry wiring mistakes."
    ),
    "test_invertedpendulum_dt_nl_quanserip02_applies_params_and_nonlinear_mode": (
        "Confirm the Quanser IP02 nonlinear pendulum variant applies its registry parameter overrides and enables nonlinear "
        "dynamics mode in setup construction."
    ),
    "test_invertedpendulum_dt_nl_lim_quanserip02_applies_params_nonlinear_and_limit": (
        "Confirm the limited Quanser IP02 nonlinear pendulum variant applies registry parameter overrides, enables nonlinear "
        "dynamics mode, and configures the expected actuator force limit."
    ),
    "test_invertedpendulum_dt_nl_lim_quanserip02_clamps_to_pm_13_44_newton": (
        "Verify the limited Quanser IP02 nonlinear pendulum variant hard-clamps actuator force commands to +/-13.44 N by "
        "comparing saturated one-step responses against explicit limit commands."
    ),
    "test_invertedpendulum_dt_nl_quanserip02_variant_remains_unclamped": (
        "Guard backward compatibility for the non-limited Quanser IP02 variant by confirming larger commands still produce "
        "larger one-step cart-velocity response."
    ),
    "test_signal_metadata_is_defined_for_all_required_series": (
        "Guarantee every setup variant publishes expected signal metadata used by dashboards and reporting (ref/meas/control names and units)."
    ),
    "test_server_cli_accepts_variant_setup_names": (
        "Confirm CLI parser accepts valid variant setup arguments and correctly parses experiment/attempt fields."
    ),
    "test_server_cli_rejects_legacy_setup_names": (
        "Ensure obsolete setup aliases are rejected by CLI parsing to prevent ambiguous or unsupported runtime selection."
    ),
    "test_server_cli_rejects_negative_design_attempt": (
        "Enforce non-negative design attempt values at CLI level, avoiding invalid result path semantics."
    ),
}

REASONS_BY_NODEID = {}
