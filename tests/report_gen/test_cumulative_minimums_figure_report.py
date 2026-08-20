TEST_MODULE = "tests/test_cumulative_minimums_figure.py"

REASONS_BY_TEST = {
    "test_cumulative_minimum_skips_infeasible_improvements": (
        "Added while introducing the cumulative-minimum objective figure to ensure infeasible runs never improve "
        "the running best value, even when their raw objective is numerically lower."
    ),
    "test_collect_attempt_series_maps_run_index_to_one_based_iteration": (
        "Protects the run-to-iteration contract used in the new figure: runN.npy must map to tuning iteration N+1. "
        "This prevents off-by-one regressions in the x-axis semantics."
    ),
    "test_hover_text_includes_objective_constraints_and_feasibility": (
        "Ensures hover tooltips keep the intended transparency content (objective, per-constraint KPI checks, and "
        "feasibility state) after future formatting refactors."
    ),
    "test_build_figure_uses_model_colors_alpha_and_blank_empty_panel": (
        "Introduced together with fixed 5x2 subplot rendering to verify codex/opus color mapping, shared alpha=0.5 "
        "styling, log y-axis configuration, and that the intentionally blank panel remains unlabeled."
    ),
    "test_main_writes_html_output": (
        "Guards the end-to-end artifact contract for analysts by checking that main() writes "
        "analysis_artifacts/figures/cumulative_minimums.html from discovered run data."
    ),
}

REASONS_BY_NODEID = {}
