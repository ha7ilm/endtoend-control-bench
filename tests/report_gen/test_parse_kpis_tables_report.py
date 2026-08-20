TEST_MODULE = "tests/test_parse_kpis_tables.py"

REASONS_BY_TEST = {
    "test_pass_all_constraints": (
        "Verify that a scalar setup (motorspeed_dt) with all KPIs within limits is correctly classified as feasible. "
        "Added while building the KPI parsing and static table generation modules to ensure the constraint registry "
        "accurately translates setup specifications into boolean feasibility checks."
    ),
    "test_fail_settling_time": (
        "Confirm that exceeding a single scalar constraint (settling_time_sec >= 2) correctly fails feasibility "
        "and reports the violated constraint description. Guards against regression in strict-less-than comparison logic."
    ),
    "test_fail_overshoot": (
        "Ensure boundary-equal values (overshoot_pct == 5, not strictly less than 5) are correctly rejected. "
        "This protects the strict '<' semantics specified in setup descriptions."
    ),
    "test_missing_key_is_infeasible": (
        "Verify that a missing KPI field causes infeasibility rather than silent pass. "
        "Missing data must always be treated conservatively as a constraint violation."
    ),
    "test_nan_value_is_infeasible": (
        "Confirm that NaN values in KPI fields are treated as infeasible. "
        "NaN comparisons must fail the '<' check by IEEE 754 semantics; this test makes that contract explicit."
    ),
    "test_boundary_just_below_passes": (
        "Verify values just below each constraint limit pass feasibility. "
        "Complements the boundary-equal rejection test to ensure the '<' boundary is correctly placed."
    ),
    "test_pass_all": (
        "Verify multi-channel (SIMO) inverted pendulum setup passes when all per-channel constraints are met. "
        "Ensures the channel extraction logic correctly navigates nested KPI dicts."
    ),
    "test_fail_x_cart_rise_time": (
        "Confirm x_cart.rise_time_sec constraint violation is detected in the multi-channel inverted pendulum setup. "
        "Guards against regressions in per-channel constraint routing."
    ),
    "test_fail_phi_max_abs_rad": (
        "Verify phi_angle.max_abs_rad constraint is enforced for the inverted pendulum. "
        "This KPI is unique to the angle channel and must not be silently skipped."
    ),
    "test_missing_channel_key": (
        "Ensure a completely missing channel (phi_angle) in the KPI dict causes multiple constraint failures. "
        "Protects against partial KPI dicts sneaking through as feasible."
    ),
    "test_missing_channels_dict": (
        "Verify that a KPI dict without the 'channels' key at all is infeasible for inverted pendulum setups. "
        "Guards against type confusion between scalar and multi-channel KPI structures."
    ),
    "test_realistic_variant_relaxed_rise_time": (
        "Confirm that the realistic inverted pendulum variant (quanserip02) has a relaxed x_cart rise_time limit (0.8 vs 0.5). "
        "Ensures the per-variant constraint override logic works correctly."
    ),
    "test_motorspeed_formula": (
        "Verify compute_objective uses overshoot_pct + 3*settling_time_sec for motorspeed_dt. "
        "Direct formula correctness check against the prompt specification."
    ),
    "test_cruisecontrol_formula": (
        "Verify compute_objective uses overshoot_pct + 2*rise_time_sec for cruisecontrol_dt. "
        "Ensures the correct objective group formula is selected for cruise control setups."
    ),
    "test_invertedpendulum_formula": (
        "Verify the inverted pendulum objective formula sums per-channel settling times and weighted steady-state errors. "
        "The multi-channel objective is more complex and this test catches formula transcription errors."
    ),
    "test_missing_key_returns_inf": (
        "Confirm compute_objective returns inf when required KPI terms are missing. "
        "Inf signals that comparison should exclude this attempt from ranking."
    ),
    "test_unknown_setup_raises": (
        "Ensure compute_objective raises ValueError for unrecognized setup names. "
        "Prevents silent misuse with typos or unsupported setups."
    ),
    "test_non_dict_kpis_raises": (
        "Ensure compute_objective rejects non-dict KPI inputs with TypeError. "
        "Type guard against accidentally passing raw numpy arrays or strings."
    ),
    "test_less_than_1": (
        "Verify format_objective uses 4 decimal places for values < 1. "
        "Snapshot test for the adaptive precision formatting rules."
    ),
    "test_less_than_1_trailing_zeros": (
        "Confirm trailing zeros are trimmed while preserving at least 1 decimal digit. "
        "Ensures '0.1000' becomes '0.1', not '0.1000' or '0.'."
    ),
    "test_between_1_and_10": (
        "Verify 3 decimal places for objective values in [1, 10). "
        "Adaptive precision snapshot test."
    ),
    "test_between_1_and_10_trailing_zeros": (
        "Confirm trailing zeros trimmed for values in [1, 10) with exact decimal. "
        "Ensures '3.000' becomes '3.0'."
    ),
    "test_between_10_and_100": (
        "Verify 2 decimal places for values in [10, 100). "
        "Adaptive precision snapshot test."
    ),
    "test_above_100": (
        "Verify 1 decimal place for values >= 100. "
        "Adaptive precision snapshot test for large objectives."
    ),
    "test_zero": (
        "Confirm zero formats as '0.0'. "
        "Edge case: zero falls in the < 1 bracket but should still display cleanly."
    ),
    "test_inf": (
        "Confirm inf formats as the string 'inf'. "
        "Non-finite values must render gracefully in table cells."
    ),
    "test_precision_snapshot_small": (
        "Snapshot: 0.0001 should render as '0.0001' with all 4 decimal digits. "
        "Catches rounding or truncation bugs at the lower precision boundary."
    ),
    "test_precision_snapshot_medium": (
        "Snapshot: 15.1 should render as '15.1' with trailing zeros trimmed. "
        "Validates trim logic interacts correctly with 2-decimal bracket."
    ),
    "test_controller_techniques_loaded_from_selected_run": (
        "Verify the manually curated controller-techniques CSV is loaded from the selected results directory. "
        "Added while moving run-specific analysis input out of the ignored cld notes directory so --folder controls "
        "both experiment artifacts and their optional technique annotations."
    ),
    "test_controller_techniques_file_is_optional": (
        "Confirm table analysis continues with empty technique data and a warning when the optional CSV is absent. "
        "Added while documenting the manual annotation workflow to protect fresh reruns that have not yet been reviewed."
    ),
    "test_success_rate_numerator_denominator": (
        "Integration test: verify success rate table correctly counts feasible/total attempts from a synthetic result tree. "
        "Exercises the full pipeline: best.txt reading, npy_match lookup, KPI loading, and feasibility checking."
    ),
    "test_exclusion_list_content": (
        "Integration test: verify that infeasible selected controllers appear in the exclusion list with correct metadata. "
        "The exclusion list is a key transparency feature for understanding why attempts were dropped from comparison."
    ),
    "test_green_highlight_on_better_objective": (
        "Integration test: verify generated HTML contains green highlighting for the better objective. "
        "Visual correctness check for the comparison table's color semantics."
    ),
    "test_missing_best_txt_handled": (
        "Integration test: verify that a missing best.txt causes the attempt to count in the denominator but not the numerator. "
        "Ensures graceful degradation when LLM agents don't complete the conclusion phase."
    ),
    "test_fail_status_in_npy_match_excluded": (
        "Integration test: verify that FAIL status in npy_match.csv prevents the controller from being counted as feasible. "
        "Guards against using unverified controller-to-run mappings in success rate computation."
    ),
    "test_scalar_all_pass": (
        "Verify explain_constraints returns all-passed tuples for a fully feasible scalar setup. "
        "Ensures the transparency function agrees with meets_design_spec on a clean input."
    ),
    "test_scalar_one_fail": (
        "Confirm explain_constraints correctly identifies a single failing constraint with its actual value and limit. "
        "Guards against silent masking of individual constraint violations in the explanation output."
    ),
    "test_multichannel": (
        "Verify explain_constraints handles multi-channel (inverted pendulum) setups and includes channel prefixes in descriptions. "
        "Ensures channel routing is correctly reflected in the transparency output."
    ),
    "test_missing_key_nan": (
        "Confirm explain_constraints reports NaN for missing KPI keys and marks the constraint as failed. "
        "Missing data must surface clearly in background files rather than silently disappearing."
    ),
    "test_motorspeed_terms": (
        "Verify explain_objective returns correct term labels, values, and weights for motorspeed_dt. "
        "Ensures the objective formula breakdown matches the compute_objective calculation."
    ),
    "test_cruisecontrol_terms": (
        "Verify explain_objective returns overshoot_pct (weight 1) and rise_time_sec (weight 2) for cruise control. "
        "Catches formula group selection errors between OS+3ST and OS+2RT objective groups."
    ),
    "test_invertedpendulum_terms": (
        "Verify explain_objective returns all four multi-channel terms for inverted pendulum setups. "
        "Ensures the per-channel term decomposition matches the aggregate objective formula."
    ),
    "test_which_better_html_no_attempt_column": (
        "Integration test: verify refactored which_better.html uses best-of-N format with no Attempt column. "
        "Confirms the table has one row per setup instead of one row per attempt."
    ),
    "test_which_better_background_generated": (
        "Integration test: verify which_better_background.txt lists per-model feasible attempts and declares a winner. "
        "Ensures the background file provides transparency into the best-of-N selection logic."
    ),
    "test_objective_background_generated": (
        "Integration test: verify objective_calculation_background.txt shows formula terms for each attempt. "
        "Ensures the objective breakdown background file is generated from the synthetic result tree."
    ),
    "test_constraint_background_generated": (
        "Integration test: verify constraint_calculation_background.txt shows PASS/FAIL per constraint. "
        "Ensures the constraint check background file is generated and contains expected status labels."
    ),
}

REASONS_BY_NODEID = {}
