"""Simulation session orchestration for one feedback loop run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

from .protocol import ProtocolError, read_message, write_message
from .setups.base import BaseSetup, SimulationConfig


@dataclass
class SimulationTrace:
    """Captured sampled traces for one simulation episode."""

    setup_name: str
    time_sec: np.ndarray
    ref: np.ndarray | dict[str, np.ndarray]
    meas: np.ndarray | dict[str, np.ndarray]
    control: np.ndarray
    disturbance: np.ndarray
    kpis: dict[str, Any]


ControllerStep = Callable[[dict[str, Any]], dict[str, Any]]
SignalValue = float | dict[str, float]


def _validate_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Client hello '{field}' must be a string.")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"Client hello '{field}' must be a non-empty string.")
    return stripped


def _read_client_hello(conn, expected_setup: str) -> dict[str, str]:
    message = read_message(conn)
    if not isinstance(message, dict):
        raise ValueError("First message must be a map.")

    msg_type = message.get("type")
    if msg_type != "client_hello":
        raise ValueError("First message must have type='client_hello'.")

    setup = _validate_non_empty_text(message.get("setup"), "setup")
    if setup != expected_setup:
        raise ValueError(
            f"Client setup '{setup}' does not match server setup '{expected_setup}'."
        )

    description = _validate_non_empty_text(message.get("description"), "description")
    why = _validate_non_empty_text(message.get("why"), "why")
    return {
        "setup": setup,
        "description": description,
        "why": why,
    }


def _normalize_signal_value(value: Any, field: str) -> SignalValue:
    if isinstance(value, Mapping):
        if not value:
            raise ValueError(f"Controller signal '{field}' map must not be empty.")

        normalized: dict[str, float] = {}
        for key, raw_value in value.items():
            if not isinstance(key, str):
                raise ValueError(
                    f"Controller signal '{field}' map keys must be strings."
                )
            key = key.strip()
            if not key:
                raise ValueError(
                    f"Controller signal '{field}' map keys must be non-empty."
                )
            parsed = float(raw_value)
            if not np.isfinite(parsed):
                raise ValueError(
                    f"Controller signal '{field}.{key}' must be finite."
                )
            normalized[key] = parsed
        return normalized

    parsed = float(value)
    if not np.isfinite(parsed):
        raise ValueError(f"Controller signal '{field}' must be finite.")
    return parsed


def _controller_input(ref_value: SignalValue, meas_value: SignalValue) -> dict[str, Any]:
    if isinstance(ref_value, dict):
        ref_payload: float | dict[str, float] = dict(ref_value)
    else:
        ref_payload = float(ref_value)

    if isinstance(meas_value, dict):
        meas_payload: float | dict[str, float] = dict(meas_value)
    else:
        meas_payload = float(meas_value)

    return {
        "type": "controller_input",
        "done": False,
        "ref": ref_payload,
        "meas": meas_payload,
    }


def _control_from_message(message: dict[str, Any]) -> float:
    if not isinstance(message, dict):
        raise ValueError("Controller output message must be a map.")

    msg_type = message.get("type")
    if msg_type == "error":
        raise ValueError(f"Controller client reported error: {message.get('message', '')}")
    if msg_type != "controller_output":
        raise ValueError("Controller output message must have type='controller_output'.")

    if "control" not in message:
        raise ValueError("Controller output missing 'control'.")

    control = float(message["control"])
    if not np.isfinite(control):
        raise ValueError("Controller output 'control' must be finite.")
    return control


def run_feedback_loop(
    setup: BaseSetup,
    config: SimulationConfig,
    controller_step: ControllerStep,
) -> SimulationTrace:
    """Run one sampled feedback-loop simulation with a remote-like controller callback."""
    num_steps = int(round(config.horizon_sec / config.dt))
    if num_steps <= 0:
        raise ValueError("Simulation horizon and dt must produce at least one step.")

    time_sec = np.arange(num_steps, dtype=float) * config.dt

    ref_scalar = np.zeros(num_steps, dtype=float)
    meas_scalar = np.zeros(num_steps, dtype=float)
    ref_map: dict[str, np.ndarray] | None = None
    meas_map: dict[str, np.ndarray] | None = None
    ref_mode: str | None = None
    meas_mode: str | None = None
    ref_keys: tuple[str, ...] | None = None
    meas_keys: tuple[str, ...] | None = None

    control_signal = np.zeros(num_steps, dtype=float)
    disturbance_signal = np.zeros(num_steps, dtype=float)

    state = setup.initial_state()

    for step_index in range(num_steps):
        ref_value = _normalize_signal_value(
            setup.reference_for_step(step_index, config),
            field="ref",
        )
        meas_value = _normalize_signal_value(
            setup.measurement_from_state(state),
            field="meas",
        )
        controller_input = _controller_input(ref_value, meas_value)

        controller_output = controller_step(controller_input)
        control = _control_from_message(controller_output)
        disturbance = setup.disturbance_for_step(step_index, config)
        disturbance = float(disturbance)
        if not np.isfinite(disturbance):
            raise ValueError("Setup disturbance must be finite.")

        if isinstance(ref_value, dict):
            current_keys = tuple(sorted(ref_value))
            if ref_mode is None:
                ref_mode = "map"
                ref_keys = current_keys
                ref_map = {key: np.zeros(num_steps, dtype=float) for key in current_keys}
            if ref_mode != "map":
                raise ValueError("Reference signal type changed within one run.")
            assert ref_keys is not None
            if current_keys != ref_keys:
                raise ValueError("Reference signal keys changed within one run.")
            assert ref_map is not None
            for key in ref_keys:
                ref_map[key][step_index] = float(ref_value[key])
        else:
            if ref_mode is None:
                ref_mode = "scalar"
            if ref_mode != "scalar":
                raise ValueError("Reference signal type changed within one run.")
            ref_scalar[step_index] = float(ref_value)

        if isinstance(meas_value, dict):
            current_keys = tuple(sorted(meas_value))
            if meas_mode is None:
                meas_mode = "map"
                meas_keys = current_keys
                meas_map = {
                    key: np.zeros(num_steps, dtype=float) for key in current_keys
                }
            if meas_mode != "map":
                raise ValueError("Measurement signal type changed within one run.")
            assert meas_keys is not None
            if current_keys != meas_keys:
                raise ValueError("Measurement signal keys changed within one run.")
            assert meas_map is not None
            for key in meas_keys:
                meas_map[key][step_index] = float(meas_value[key])
        else:
            if meas_mode is None:
                meas_mode = "scalar"
            if meas_mode != "scalar":
                raise ValueError("Measurement signal type changed within one run.")
            meas_scalar[step_index] = float(meas_value)

        control_signal[step_index] = control
        disturbance_signal[step_index] = disturbance

        state = setup.integrate_one_step(state, control, disturbance, config.dt)

    if ref_mode is None:
        raise ValueError("Reference signal trace is empty.")
    if meas_mode is None:
        raise ValueError("Measurement signal trace is empty.")

    ref: np.ndarray | dict[str, np.ndarray]
    meas: np.ndarray | dict[str, np.ndarray]
    if ref_mode == "map":
        assert ref_map is not None
        ref = ref_map
    else:
        ref = ref_scalar

    if meas_mode == "map":
        assert meas_map is not None
        meas = meas_map
    else:
        meas = meas_scalar

    kpis = setup.compute_kpis(
        time_sec=time_sec,
        ref=ref,
        meas=meas,
        config=config,
    )

    return SimulationTrace(
        setup_name=setup.name,
        time_sec=time_sec,
        ref=ref,
        meas=meas,
        control=control_signal,
        disturbance=disturbance_signal,
        kpis=kpis,
    )


def save_trace(
    result_root: Path,
    setup_name: str,
    experiment_id: str,
    design_attempt: int,
    run_index: int,
    trace: SimulationTrace,
    llm_said: dict[str, str],
) -> tuple[Path, int]:
    """Persist one simulation run to results/current_run/sim/<setup>/<id>/attemptN/runN.npy."""
    result_dir = result_root / setup_name / experiment_id / f"attempt{design_attempt}"
    result_dir.mkdir(parents=True, exist_ok=True)

    run_payload = {
        "setup": trace.setup_name,
        "llm_said": llm_said,
        "time_sec": trace.time_sec,
        "ref": trace.ref,
        "meas": trace.meas,
        "control": trace.control,
        "disturbance": trace.disturbance,
        "kpis": trace.kpis,
    }

    np.save(result_dir / f"run{run_index}.npy", run_payload, allow_pickle=True)

    return result_dir, run_index


def run_socket_session(
    conn,
    setup: BaseSetup,
    config: SimulationConfig,
    result_root: Path,
    experiment_id: str,
    design_attempt: int,
    run_index: int,
) -> tuple[Path, int, dict[str, Any]]:
    """Run one feedback loop session over a TCP connection."""
    llm_said: dict[str, str] | None = None

    def controller_step(controller_input: dict[str, Any]) -> dict[str, Any]:
        write_message(conn, controller_input)
        return read_message(conn)

    try:
        llm_said = _read_client_hello(conn, expected_setup=setup.name)
        trace = run_feedback_loop(setup, config, controller_step)

        write_message(
            conn,
            {
                "type": "controller_input",
                "done": True,
                "kpis": trace.kpis,
            },
        )

        result_dir, run_index = save_trace(
            result_root=result_root,
            setup_name=setup.name,
            experiment_id=experiment_id,
            design_attempt=design_attempt,
            run_index=run_index,
            trace=trace,
            llm_said=llm_said,
        )
        return result_dir, run_index, trace.kpis
    except Exception as exc:
        try:
            write_message(conn, {"type": "error", "message": str(exc)})
        except ProtocolError:
            pass
        raise
