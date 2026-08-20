TEST_MODULE = "tests/test_ballandbeam_digital_trials.py"

REASONS_BY_TEST = {
    "test_ballandbeam_digital_trials_have_finite_signals": (
        "Check that the digital trial progression (open-loop, gain-only, and PD variants) remains numerically finite "
        "for measurement and control, preventing unstable arithmetic from masking real behavior."
    ),
    "test_ballandbeam_digital_final_pd_meets_design_specs": (
        "Enforce final digital PD acceptance limits for Ball-and-Beam: settled within horizon, overshoot below 5%, "
        "and settling time below 3 seconds."
    ),
    "test_ballandbeam_digital_final_pd_reduces_steady_state_error": (
        "Confirm that the final PD gains improve steady-state tracking relative to both open-loop and lower-gain PD, "
        "so final tuning is directionally better than earlier trials."
    ),
    "test_ballandbeam_digital_open_loop_matches_matlab_reference": (
        "Anchor the open-loop discrete model against the known MATLAB reference endpoint (~0.651), ensuring model "
        "equivalence after code changes."
    ),
    "test_ballandbeam_dt_nl_trial_has_finite_signals": (
        "Smoke-test the nonlinear Ball-and-Beam variant for finite response and control under baseline controller "
        "settings to detect integration/model explosions early."
    ),
    "test_ballandbeam_dt_nl_act_trials_stay_finite_and_bounded": (
        "Verify actuator-limited nonlinear trials stay finite and keep measurement magnitude below 10, enforcing a "
        "practical boundedness constraint in addition to NaN/Inf checks."
    ),
    "test_ballandbeam_dt_nl_act_mg996r_trials_stay_finite_and_bounded": (
        "Guard the MG996R actuator variant against numeric blowups by requiring finite measurement/control traces and "
        "bounded measurement magnitude under the same controller progression used for other nonlinear actuator trials."
    ),
    "test_ballandbeam_ct_diverging_trial_is_not_marked_settled": (
        "Prevent false-positive settling on the known divergent continuous-time trial by requiring "
        "settled_within_horizon=False and settling_time to fall back to the full simulation horizon."
    ),
}

REASONS_BY_NODEID = {}
