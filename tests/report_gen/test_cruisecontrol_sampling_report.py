TEST_MODULE = "tests/test_cruisecontrol_sampling.py"

REASONS_BY_TEST = {
    "test_sampling_time_converges_below_one_hundred_ms": (
        "Check sampling-time convergence for cruise control: reducing dt from 100 ms to 50 ms to 20 ms must reduce "
        "inter-sample MAE to expected tolerances, showing discretization consistency."
    ),
    "test_sampled_feedback_matches_transfer_function_response": (
        "Cross-validate the sampled ODE loop against the analytical feedback(C*P,1) response at dt=20 ms, bounding "
        "mean and worst-case alignment error after warmup-delay compensation."
    ),
}

REASONS_BY_NODEID = {}
