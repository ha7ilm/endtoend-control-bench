TEST_MODULE = "tests/test_dash_match_csv_handling.py"

REASONS_BY_TEST = {
    "test_load_match_csv_rows_parses_and_normalizes_status": (
        "Added during the dash CSV helper extraction so the new shared loader preserves the status normalization contract "
        "that downstream tooling expects while moving parsing logic out of individual apps."
    ),
    "test_load_match_csv_rows_reports_missing_required_columns": (
        "Backstory: while centralizing npy_match parsing we needed one clear failure mode for schema drift, so this test "
        "locks the required-column validation that protects callers from partial CSV exports."
    ),
    "test_load_match_csv_rows_skips_malformed_rows": (
        "Introduced to protect robustness after unifying logic: malformed rows should not poison the entire file, and the "
        "shared loader must emit actionable issues while still returning usable records."
    ),
    "test_build_controller_lookup_filters_status_and_uses_last_duplicate_policy": (
        "This guards the refactor path where view and tables consume one lookup builder with different status filters; it "
        "ensures PASS/WARN filtering and deterministic duplicate handling stay stable after consolidation."
    ),
    "test_build_controller_lookup_first_duplicate_policy_keeps_first": (
        "Added while designing configurable duplicate policies in the shared library, to ensure callers can opt into "
        "non-overwriting behavior without silent regression in mapping selection."
    ),
    "test_build_run_lookup_filters_status_and_maps_to_controller": (
        "Introduced for the viewer table-link feature that needs run-to-controller resolution; this test locks the new "
        "shared lookup direction so PASS/WARN filtering still yields deterministic run-keyed controller mapping."
    ),
    "test_read_best_controller_name_valid_and_malformed": (
        "Protects the extracted best.txt parser used across dashboards, guaranteeing canonical controller_N.py extraction "
        "and clear malformed-file diagnostics after removing duplicated regex code."
    ),
    "test_parse_sim_run_path_and_classify_why_phase": (
        "Added during run-query library expansion so the shared parser and why-phase classifier remain stable contracts "
        "for downstream dagger/run-phase selection logic."
    ),
    "test_resolve_last_design_before_tuning_run_paths_selects_transition_runs": (
        "Introduced while adding the design-checkpoint marker feature; it locks the core selection rule that each attempt "
        "should map to the last Design run immediately before the first Tuning run."
    ),
    "test_resolve_last_design_before_tuning_run_paths_reports_malformed_or_missing_transition": (
        "Backstops failure-path behavior of the new phase-query helper so malformed run paths, unknown why prefixes, and "
        "attempts without a valid design-before-tuning boundary produce deterministic diagnostics."
    ),
}

REASONS_BY_NODEID = {}
