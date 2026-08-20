TEST_MODULE = "tests/test_suspension_digital_observer.py"

REASONS_BY_TEST = {
    "test_observer_based_suspension_controller_has_finite_signals_and_recovery": (
        "Check both observer-controller implementations keep signals finite, cap control magnitude (<2e5), and show recovery "
        "(final absolute measurement lower than peak)."
    ),
}

REASONS_BY_NODEID = {}
