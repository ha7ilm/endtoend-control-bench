import numpy as np
import pytest

from controlclient.examples.dt._digital_tf import DiscreteTransferController
from controlserver.config import get_setup_config
from controlserver.session import run_feedback_loop
from controlserver.setups import create_setup
from controlserver.setups.base import SimulationConfig


def _run_controller(
    controller: DiscreteTransferController,
    *,
    setup_name: str = "ballandbeam_dt",
):
    return _run_control_policy(
        lambda controller_input: float(
            controller.step(controller_input["ref"] - controller_input["meas"])
        ),
        setup_name=setup_name,
    )


def _run_control_policy(policy, *, setup_name: str = "ballandbeam_dt"):
    setup = create_setup(setup_name)
    config = SimulationConfig.from_dict(get_setup_config(setup_name))

    def controller_step(controller_input: dict):
        return {
            "type": "controller_output",
            "control": float(policy(controller_input)),
        }

    return run_feedback_loop(setup, config, controller_step), config


def _pd_controller(kp: float, kd: float) -> DiscreteTransferController:
    # C(z) = ((Kp+Kd) z^2 - (Kp+2Kd) z + Kd) / (z^2 + z)
    # q = z^-1 form: C(q) = ((Kp+Kd) - (Kp+2Kd) q + Kd q^2) / (1 + q)
    b_q = np.array([kp + kd, -(kp + 2.0 * kd), kd], dtype=float)
    a_q = np.array([1.0, 1.0], dtype=float)
    return DiscreteTransferController(b_q, a_q, control_limit=1e6)


def test_ballandbeam_digital_trials_have_finite_signals():
    controllers = [
        DiscreteTransferController([1.0], [1.0], control_limit=1e6),
        DiscreteTransferController([100.0], [1.0], control_limit=1e6),
        _pd_controller(kp=100.0, kd=10.0),
        _pd_controller(kp=1000.0, kd=10.0),
    ]

    for controller in controllers:
        trace, _ = _run_controller(controller)
        assert trace.setup_name == "ballandbeam_dt"
        assert np.all(np.isfinite(trace.meas))
        assert np.all(np.isfinite(trace.control))


def test_ballandbeam_digital_final_pd_meets_design_specs():
    final_trace, _ = _run_controller(_pd_controller(kp=1000.0, kd=10.0))

    assert bool(final_trace.kpis["settled_within_horizon"])
    assert float(final_trace.kpis["overshoot_pct"]) < 5.0
    assert float(final_trace.kpis["settling_time_sec"]) < 3.0


def test_ballandbeam_digital_final_pd_reduces_steady_state_error():
    open_loop_trace, _ = _run_controller(
        DiscreteTransferController([1.0], [1.0], control_limit=1e6)
    )
    pd_low_trace, _ = _run_controller(_pd_controller(kp=100.0, kd=10.0))
    pd_final_trace, _ = _run_controller(_pd_controller(kp=1000.0, kd=10.0))

    assert float(pd_final_trace.kpis["steady_state_error_pct"]) < float(
        open_loop_trace.kpis["steady_state_error_pct"]
    )
    assert float(pd_final_trace.kpis["steady_state_error_pct"]) < float(
        pd_low_trace.kpis["steady_state_error_pct"]
    )


def test_ballandbeam_digital_open_loop_matches_matlab_reference():
    # MATLAB run0 uses step(0.25 * ball_d, 5), i.e. fixed input u=ref.
    # With warmup_samples=2, the terminal sample is slightly lower than the no-warmup case.
    open_loop_trace, _ = _run_control_policy(lambda controller_input: controller_input["ref"])
    assert open_loop_trace.meas[-1] == pytest.approx(0.6406, abs=0.005)


def test_ballandbeam_dt_nl_trial_has_finite_signals():
    trace, _ = _run_controller(
        DiscreteTransferController([1.0], [1.0], control_limit=1e6),
        setup_name="ballandbeam_dt_nl",
    )
    assert trace.setup_name == "ballandbeam_dt_nl"
    assert np.all(np.isfinite(trace.meas))
    assert np.all(np.isfinite(trace.control))


def test_ballandbeam_dt_nl_act_trials_stay_finite_and_bounded():
    controllers = [
        DiscreteTransferController([100.0], [1.0], control_limit=1e6),
        _pd_controller(kp=100.0, kd=10.0),
        _pd_controller(kp=1000.0, kd=10.0),
    ]

    for controller in controllers:
        trace, _ = _run_controller(controller, setup_name="ballandbeam_dt_nl_act")
        meas = np.asarray(trace.meas, dtype=float)
        control = np.asarray(trace.control, dtype=float)
        assert trace.setup_name == "ballandbeam_dt_nl_act"
        assert np.all(np.isfinite(meas))
        assert np.all(np.isfinite(control))
        assert float(np.max(np.abs(meas))) < 10.0


def test_ballandbeam_dt_nl_act_mg996r_trials_stay_finite_and_bounded():
    controllers = [
        DiscreteTransferController([100.0], [1.0], control_limit=1e6),
        _pd_controller(kp=100.0, kd=10.0),
        _pd_controller(kp=1000.0, kd=10.0),
    ]

    for controller in controllers:
        trace, _ = _run_controller(controller, setup_name="ballandbeam_dt_nl_act_mg996r")
        meas = np.asarray(trace.meas, dtype=float)
        control = np.asarray(trace.control, dtype=float)
        assert trace.setup_name == "ballandbeam_dt_nl_act_mg996r"
        assert np.all(np.isfinite(meas))
        assert np.all(np.isfinite(control))
        assert float(np.max(np.abs(meas))) < 10.0


def test_ballandbeam_ct_diverging_trial_is_not_marked_settled():
    trace, config = _run_controller(
        _pd_controller(kp=1000.0, kd=10.0),
        setup_name="ballandbeam_ct",
    )

    meas = np.asarray(trace.meas, dtype=float)
    assert trace.setup_name == "ballandbeam_ct"
    assert np.all(np.isfinite(meas))
    assert not bool(trace.kpis["settled_within_horizon"])
    assert np.isclose(float(trace.kpis["settling_time_sec"]), config.horizon_sec, atol=1e-9)
