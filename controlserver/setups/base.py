"""Base interface for pluggable physical simulation setups."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, Mapping

import numpy as np
from scipy.integrate import solve_ivp


@dataclass(frozen=True)
class SimulationConfig:
    """Sampling and reference configuration for one setup."""

    dt: float
    horizon_sec: float
    warmup_samples: int
    step_ref: float

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "SimulationConfig":
        if "step_ref" not in config:
            raise KeyError("Simulation config requires 'step_ref'.")
        return cls(
            dt=float(config["dt"]),
            horizon_sec=float(config["horizon_sec"]),
            warmup_samples=int(config["warmup_samples"]),
            step_ref=float(config["step_ref"]),
        )


class BaseSetup(ABC):
    """Interface for setup-specific dynamics and controller I/O mapping."""

    name: str

    def __init__(
        self,
        *,
        variant_name: str | None = None,
        model_params: Mapping[str, float] | None = None,
    ) -> None:
        if variant_name is not None:
            self.name = self._validated_non_empty_name(variant_name)
        if model_params is not None:
            self._apply_model_params(model_params)

    @staticmethod
    def _validated_non_empty_name(name: str) -> str:
        if not isinstance(name, str):
            raise TypeError("setup variant_name must be a string.")
        stripped = name.strip()
        if not stripped:
            raise ValueError("setup variant_name must be a non-empty string.")
        return stripped

    def _apply_model_params(self, model_params: Mapping[str, float]) -> None:
        for raw_key, raw_value in model_params.items():
            if not isinstance(raw_key, str):
                raise TypeError("model parameter names must be strings.")
            key = raw_key.strip()
            if not key:
                raise ValueError("model parameter names must be non-empty.")
            if not hasattr(self, key):
                raise ValueError(
                    f"Unknown model parameter '{key}' for setup '{self.name}'."
                )

            value = float(raw_value)
            if not np.isfinite(value):
                raise ValueError(
                    f"Model parameter '{key}' for setup '{self.name}' must be finite."
                )
            setattr(self, key, value)

    @abstractmethod
    def initial_state(self) -> np.ndarray:
        """Return the initial state vector for a new simulation run."""

    @abstractmethod
    def reference_for_step(
        self,
        step_index: int,
        config: SimulationConfig,
    ) -> float | dict[str, float]:
        """Return reference value for the current sample step."""

    @abstractmethod
    def measurement_from_state(self, state: np.ndarray) -> float | dict[str, float]:
        """Return measured plant output from the current state."""

    @abstractmethod
    def _rhs(
        self,
        t: float,
        x: np.ndarray,
        control: float,
        disturbance: float,
    ) -> np.ndarray:
        """Continuous-time plant dynamics x_dot = f(t, x, u)."""

    def disturbance_for_step(self, step_index: int, config: SimulationConfig) -> float:
        """Return additive disturbance value for the current sample step."""
        del step_index
        del config
        return 0.0

    def kpi_mode(self) -> Literal["step", "disturbance"]:
        """Return KPI semantics mode for this setup."""
        return "step"

    def kpi_event_start_index(
        self,
        time_sec: np.ndarray,
        ref: np.ndarray,
        meas: np.ndarray,
        config: SimulationConfig,
    ) -> int:
        """Return the event onset index used by disturbance-mode KPI calculations."""
        del time_sec
        del ref
        del meas
        return int(config.warmup_samples)

    def kpi_target_value(self, config: SimulationConfig) -> float:
        """Return desired steady-state output for KPI calculations."""
        return float(config.step_ref)

    def kpi_normalization_scale(self, config: SimulationConfig) -> float:
        """Return normalization scale used for percent-style KPIs."""
        return abs(float(config.step_ref))

    def compute_kpis(
        self,
        time_sec: np.ndarray,
        ref: np.ndarray,
        meas: np.ndarray,
        config: SimulationConfig,
    ) -> dict[str, Any]:
        """Compute KPIs using setup-selected mode semantics."""
        mode = self.kpi_mode()
        if mode == "step":
            return self._compute_step_kpis(time_sec=time_sec, ref=ref, meas=meas, config=config)
        if mode == "disturbance":
            return self._compute_disturbance_kpis(
                time_sec=time_sec,
                ref=ref,
                meas=meas,
                config=config,
            )
        raise ValueError(f"Unsupported KPI mode '{mode}' for setup '{self.name}'.")

    def _compute_step_kpis(
        self,
        time_sec: np.ndarray,
        ref: np.ndarray,
        meas: np.ndarray,
        config: SimulationConfig,
    ) -> dict[str, Any]:
        """Compute standard step-tracking KPIs with target-based semantics."""
        eps = float(np.finfo(float).eps)
        target = float(self.kpi_target_value(config))
        step_indices = np.flatnonzero(np.abs(ref) > eps)

        if step_indices.size == 0:
            return self._empty_kpis(config=config)

        step_start = int(step_indices[0])
        y_step = np.asarray(meas[step_start:], dtype=float)
        t_step = np.asarray(time_sec[step_start:] - time_sec[step_start], dtype=float)
        if y_step.size == 0:
            return {
                "overshoot_pct": 0.0,
                "rise_time_sec": float(config.horizon_sec),
                "settling_time_sec": float(config.horizon_sec),
                "steady_state_error_pct": 0.0,
                "settled_within_horizon": False,
                "simulation_horizon_sec": float(config.horizon_sec),
            }
        if not np.all(np.isfinite(y_step)) or not np.all(np.isfinite(t_step)):
            return self._invalid_kpis(config=config)

        y0 = float(y_step[0])
        y_final = float(y_step[-1])
        target_delta = target - y0
        transition_mag = abs(target_delta)
        direction = 1.0 if target_delta >= 0.0 else -1.0

        if transition_mag <= eps:
            overshoot_pct = 0.0
        else:
            extremum = float(np.max(y_step)) if direction >= 0.0 else float(np.min(y_step))
            overshoot_pct = max(
                0.0,
                direction * (extremum - target) / transition_mag * 100.0,
            )

        # Match stepinfo-style settling width scaling against commanded transition.
        tolerance_base = transition_mag
        if tolerance_base <= eps:
            tolerance_base = max(abs(target), eps)
        tolerance = 0.02 * tolerance_base
        outside_indices = np.flatnonzero(np.abs(y_step - target) > tolerance)

        if outside_indices.size == 0:
            settling_time_sec = 0.0
            settled_within_horizon = True
        else:
            last_outside = int(outside_indices[-1])
            if last_outside == y_step.size - 1:
                settling_time_sec = float(config.horizon_sec)
                settled_within_horizon = False
            else:
                settling_time_sec = float(t_step[last_outside + 1])
                settled_within_horizon = settling_time_sec < config.horizon_sec

        if transition_mag <= eps:
            rise_time_sec = 0.0
        else:
            level10 = y0 + 0.1 * target_delta
            level90 = y0 + 0.9 * target_delta
            t10 = self._first_crossing_time(t_step, y_step, level10, direction)
            t90 = self._first_crossing_time(t_step, y_step, level90, direction)
            if t10 is None or t90 is None or t90 < t10:
                rise_time_sec = float(config.horizon_sec)
            else:
                rise_time_sec = float(t90 - t10)

        scale = max(abs(target), transition_mag, eps)
        steady_state_error_pct = abs(target - y_final) / scale * 100.0

        return {
            "overshoot_pct": float(overshoot_pct),
            "rise_time_sec": float(rise_time_sec),
            "settling_time_sec": float(settling_time_sec),
            "steady_state_error_pct": float(steady_state_error_pct),
            "settled_within_horizon": bool(settled_within_horizon),
            "simulation_horizon_sec": float(config.horizon_sec),
        }

    def _compute_disturbance_kpis(
        self,
        time_sec: np.ndarray,
        ref: np.ndarray,
        meas: np.ndarray,
        config: SimulationConfig,
    ) -> dict[str, Any]:
        """Compute regulator/disturbance-rejection KPIs relative to a target output."""
        eps = float(np.finfo(float).eps)
        if meas.size == 0:
            return {
                "overshoot_pct": 0.0,
                "rise_time_sec": float(config.horizon_sec),
                "settling_time_sec": float(config.horizon_sec),
                "steady_state_error_pct": 0.0,
                "settled_within_horizon": False,
                "simulation_horizon_sec": float(config.horizon_sec),
            }

        event_start = int(self.kpi_event_start_index(time_sec=time_sec, ref=ref, meas=meas, config=config))
        event_start = int(np.clip(event_start, 0, meas.size - 1))

        y_step = np.asarray(meas[event_start:], dtype=float)
        t_step = np.asarray(time_sec[event_start:] - time_sec[event_start], dtype=float)
        if y_step.size == 0:
            return {
                "overshoot_pct": 0.0,
                "rise_time_sec": float(config.horizon_sec),
                "settling_time_sec": float(config.horizon_sec),
                "steady_state_error_pct": 0.0,
                "settled_within_horizon": False,
                "simulation_horizon_sec": float(config.horizon_sec),
            }
        if not np.all(np.isfinite(y_step)) or not np.all(np.isfinite(t_step)):
            return self._invalid_kpis(config=config)

        target = float(self.kpi_target_value(config))
        scale = max(float(self.kpi_normalization_scale(config)), eps)
        error = np.asarray(y_step - target, dtype=float)
        abs_error = np.abs(error)
        peak_abs_error = float(np.max(abs_error))

        overshoot_pct = peak_abs_error / scale * 100.0

        tolerance = 0.02 * scale
        outside_indices = np.flatnonzero(abs_error > tolerance)
        if outside_indices.size == 0:
            settling_time_sec = 0.0
            settled_within_horizon = True
        else:
            last_outside = int(outside_indices[-1])
            if last_outside == abs_error.size - 1:
                settling_time_sec = float(config.horizon_sec)
                settled_within_horizon = False
            else:
                settling_time_sec = float(t_step[last_outside + 1])
                settled_within_horizon = settling_time_sec < config.horizon_sec

        if peak_abs_error <= eps:
            rise_time_sec = 0.0
        else:
            level90 = 0.9 * peak_abs_error
            rise_crossing = self._first_crossing_time(
                t=t_step,
                y=abs_error,
                level=level90,
                direction=1.0,
            )
            if rise_crossing is None:
                rise_time_sec = float(config.horizon_sec)
            else:
                rise_time_sec = float(rise_crossing)

        steady_state_error_pct = abs(float(error[-1])) / scale * 100.0

        return {
            "overshoot_pct": float(overshoot_pct),
            "rise_time_sec": float(rise_time_sec),
            "settling_time_sec": float(settling_time_sec),
            "steady_state_error_pct": float(steady_state_error_pct),
            "settled_within_horizon": bool(settled_within_horizon),
            "simulation_horizon_sec": float(config.horizon_sec),
        }

    @staticmethod
    def _invalid_kpis(config: SimulationConfig) -> dict[str, Any]:
        return {
            "overshoot_pct": 0.0,
            "rise_time_sec": float(config.horizon_sec),
            "settling_time_sec": float(config.horizon_sec),
            "steady_state_error_pct": 0.0,
            "settled_within_horizon": False,
            "simulation_horizon_sec": float(config.horizon_sec),
        }

    @staticmethod
    def _empty_kpis(config: SimulationConfig) -> dict[str, Any]:
        return {
            "overshoot_pct": 0.0,
            "rise_time_sec": 0.0,
            "settling_time_sec": 0.0,
            "steady_state_error_pct": 0.0,
            "settled_within_horizon": True,
            "simulation_horizon_sec": float(config.horizon_sec),
        }

    def integrate_one_step(
        self,
        state: np.ndarray,
        control: float,
        disturbance: float,
        dt: float,
    ) -> np.ndarray:
        """Integrate one sample period with zero-order hold control input."""
        solution = solve_ivp(
            fun=lambda t, x: self._rhs(t, x, control, disturbance),
            t_span=(0.0, dt),
            y0=state,
            method="RK45",
            rtol=1e-8,
            atol=1e-10,
        )
        return np.asarray(solution.y[:, -1], dtype=float)

    @staticmethod
    def _first_crossing_time(
        t: np.ndarray,
        y: np.ndarray,
        level: float,
        direction: float,
    ) -> float | None:
        """Return first threshold crossing time with linear interpolation."""
        if y.size == 0:
            return None

        crossed = y >= level if direction >= 0.0 else y <= level
        crossing_indices = np.flatnonzero(crossed)
        if crossing_indices.size == 0:
            return None

        idx = int(crossing_indices[0])
        if idx == 0:
            return float(t[0])

        y0 = float(y[idx - 1])
        y1 = float(y[idx])
        t0 = float(t[idx - 1])
        t1 = float(t[idx])
        dy = y1 - y0
        if abs(dy) <= float(np.finfo(float).eps):
            return t1

        alpha = float(np.clip((level - y0) / dy, 0.0, 1.0))
        return t0 + alpha * (t1 - t0)
