TEST_MODULE = "tests/test_cruisecontrol_digital_trials.py"

REASONS_BY_TEST = {
    "test_lag_compensator_reduces_steady_state_error_vs_gain_only": (
        "Protect the cruise-control digital design objective: the lag-compensated controller must both beat the "
        "gain-only baseline and keep steady-state error under 3%."
    ),
}

REASONS_BY_NODEID = {}
