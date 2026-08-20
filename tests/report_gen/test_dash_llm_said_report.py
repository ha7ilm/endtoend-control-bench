TEST_MODULE = "tests/test_dash_llm_said.py"

REASONS_BY_TEST = {
    "test_load_runs_requires_llm_said": (
        "Ensure dashboard run loading rejects incomplete payloads missing llm_said metadata while still loading valid "
        "runs and reporting actionable warnings."
    ),
    "test_llm_said_table_only_includes_visible_legend_entries": (
        "Verify that the LLM metadata table reflects legend visibility filtering so hidden traces do not leak into the "
        "displayed provenance table."
    ),
    "test_each_run_has_distinct_color": (
        "Guarantee each visible run gets a unique color assignment, preserving visual trace discrimination when multiple "
        "runs are plotted together."
    ),
    "test_load_runs_accepts_dict_ref_and_meas_for_invertedpendulum": (
        "Confirm loader and figure code correctly accept dict-valued ref/meas channels (x, phi) and map them to "
        "multi-axis traces without shape warnings."
    ),
    "test_build_figure_plots_more_than_two_channels_on_additional_axes": (
        "Protect multichannel plotting behavior for 3-channel responses by asserting y/y2/y3 axis mapping, consistent "
        "run coloring, and additional-axis layout creation."
    ),
    "test_multichannel_response_uses_y3_when_control_subplot_is_enabled": (
        "Verify axis allocation remains correct when control subplot is enabled: response channels must move to y and y3 "
        "while control occupies y2 to avoid overlap."
    ),
    "test_create_app_removes_signal_selector": (
        "Enforce the intended Dash UI simplification by asserting signal-selector is absent while required setup/experiment/attempt "
        "selectors remain present."
    ),
    "test_create_app_defaults_best_only_checkbox_and_initial_filter": (
        "Added while making the trophy filter default-on, to lock startup behavior: the display checklist must include best_only "
        "while the newer design-checkpoint filter remains opt-in, and the preloaded figure must already exclude non-starred runs "
        "before any callback executes."
    ),
    "test_resolve_best_legend_groups_uses_pass_warn_and_ignores_fail": (
        "Added while wiring best.txt highlighting into the step-response dashboard, to lock the run-resolution contract "
        "that only PASS/WARN rows in npy_match.csv may drive best-run selection and FAIL rows must be ignored."
    ),
    "test_resolve_dagger_legend_groups_uses_why_phase_boundary": (
        "Introduced for the new design-checkpoint marker so per-attempt selection is anchored to llm_said why-phase transitions: "
        "last Design run before first Tuning run, with attempts lacking tuning excluded."
    ),
    "test_best_run_star_shows_in_legend_table_and_hover": (
        "Backstops the UI change introduced during best-controller provenance work: starred best runs must appear consistently "
        "in graph legend text, llm_said table legend cells, and hover payloads so analysts can trust what is marked best."
    ),
    "test_best_run_star_shows_in_short_legend_mode": (
        "Guards the short-legend iteration mode added for compact plotting views, ensuring the new best-run star marker remains "
        "visible after legend-name remapping to Iteration N labels."
    ),
    "test_build_figure_best_only_filter_shows_only_starred_runs": (
        "Added while introducing the trophy-only display toggle, to ensure graph filtering can collapse to only starred "
        "best-controller traces without leaking non-best runs into the rendered figure."
    ),
    "test_dagger_run_shows_in_legend_table_and_hover": (
        "Added with the dagger feature to lock consistent surfacing of the design-checkpoint marker across graph legend text, "
        "hover payload suffixes, and the llm_said table legend column."
    ),
    "test_build_figure_design_checkpoint_filter_shows_only_dagger_runs": (
        "Protects the new ⛳ checkbox behavior by asserting dagger-only filtering excludes non-checkpoint runs under the same "
        "setup/experiment/attempt selection."
    ),
    "test_build_figure_best_and_dagger_filters_union_when_both_enabled": (
        "Guards combined marker/filter semantics so checking both 🏆 and ⛳ behaves as a union: runs matching either marker "
        "remain visible, instead of over-restrictive intersection filtering."
    ),
    "test_llm_said_table_controller_links_and_view_route": (
        "Added while exposing controller source links in the llm_said table, to lock two contracts: each visible run row must "
        "render a new-tab controller_N.py link, and the viewer route must return the mapped controller source for that run."
    ),
}

REASONS_BY_NODEID = {}
