TEST_MODULE = "tests/test_invertedpendulum_ct_pid_trials.py"

REASONS_BY_TEST = {
    "test_invertedpendulum_tex_ct_pid_trials_have_finite_signals": (
        "Check all continuous-time inverted-pendulum PID trial gains for finite cart/angle signals and finite control, "
        "ensuring numerical soundness of the textbook progression."
    ),
    "test_invertedpendulum_tex_ct_trial3_keeps_phi_residual_small": (
        "Verify the higher-derivative trial keeps final pendulum-angle residual very small (<1e-4) and within the same "
        "order as trial2, guarding near-upright regulation behavior."
    ),
}

REASONS_BY_NODEID = {}
