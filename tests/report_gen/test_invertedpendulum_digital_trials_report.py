TEST_MODULE = "tests/test_invertedpendulum_digital_trials.py"

REASONS_BY_TEST = {
    "test_invertedpendulum_digital_baseline_runs_with_dict_signals": (
        "Validate that the digital inverted-pendulum loop uses dict-valued x_cart/phi_angle channels end-to-end and produces "
        "finite signals with non-trivial control action in the baseline case."
    ),
    "test_invertedpendulum_precompensator_reduces_cart_steady_state_error": (
        "Ensure adding Nbar precompensation improves cart steady-state error versus tuned no-Nbar LQR, preserving the "
        "expected benefit of precompensator design."
    ),
    "test_invertedpendulum_observer_controller_tracks_and_is_finite": (
        "Check observer-based digital controller remains finite and meets practical tracking thresholds (steady-state "
        "error < 2%, settling < 5 s)."
    ),
    "test_invertedpendulum_dt_nl_baseline_is_finite": (
        "Smoke-test the nonlinear inverted-pendulum discrete variant for finite x_cart/phi_angle measurement channels and finite "
        "control values under baseline LQR settings."
    ),
    "test_invertedpendulum_dt_nl_quanserip02_baseline_is_finite": (
        "Smoke-test the nonlinear Quanser IP02 pendulum discrete variant for finite x_cart/phi_angle measurement channels and finite "
        "control values under baseline LQR settings."
    ),
    "test_invertedpendulum_dt_nl_lim_quanserip02_baseline_is_finite": (
        "Smoke-test the nonlinear limited Quanser IP02 pendulum discrete variant for finite x_cart/phi_angle channels and finite "
        "control values under baseline LQR settings."
    ),
}

REASONS_BY_NODEID = {}
