TEST_MODULE = "tests/test_motorspeed_sampling.py"

REASONS_BY_TEST = {
    "test_sampling_time_converges_below_ten_ms": (
        "Check Motorspeed discretization convergence by comparing dt=10/5/2 ms trajectories and enforcing tighter MAE "
        "at smaller sampling intervals."
    ),
    "test_sampled_feedback_matches_transfer_function_response": (
        "Cross-check sampled Motorspeed closed-loop simulation against analytical feedback(C*P,1) step response, with "
        "bounds on mean and max error after warmup alignment."
    ),
}

REASONS_BY_NODEID = {}
