TEST_MODULE = "tests/test_invertedpendulum_protocol_and_loop.py"

REASONS_BY_TEST = {
    "test_invertedpendulum_run_feedback_loop_uses_dict_ref_and_meas": (
        "Enforce protocol semantics for multi-output setups: controller input and stored trace must carry dict ref/meas "
        "keys (x_cart, phi_angle) with per-channel lengths matching simulation time."
    ),
}

REASONS_BY_NODEID = {}
