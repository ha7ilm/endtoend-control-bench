"""Inverted pendulum setup for the feedback loop server."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from .base import BaseSetup, SimulationConfig


class InvertedPendulumSetup(BaseSetup):
    """Cart-pendulum dynamics with linearized and nonlinear DT variants."""

    name = "invertedpendulum"

    # Parameters from InvertedPendulum.tex / invertedpendulum_digital.m
    M = 0.5
    m = 0.2
    b = 0.1
    I = 0.006
    g = 9.8
    l = 0.3
    actuator_force_limit_n = np.inf

    def __init__(
        self,
        *,
        variant_name: str | None = None,
        model_params: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(variant_name=variant_name, model_params=model_params)
        self._use_nonlinear = self.name.endswith("_dt_nl") or "_dt_nl_" in self.name

    def initial_state(self) -> np.ndarray:
        # x = [cart_position_m, cart_velocity_m_per_sec, phi_rad, phi_dot_rad_per_sec]
        return np.array([0.0, 0.0, 0.0, 0.0], dtype=float)

    def reference_for_step(
        self,
        step_index: int,
        config: SimulationConfig,
    ) -> dict[str, float]:
        x_ref = 0.0 if step_index < config.warmup_samples else float(config.step_ref)
        return {
            "x_cart": x_ref,
            "phi_angle": 0.0,
        }

    def measurement_from_state(self, state: np.ndarray) -> dict[str, float]:
        return {
            "x_cart": float(state[0]),
            "phi_angle": float(state[2]),
        }

    def _rhs(
        self,
        _t: float,
        x: np.ndarray,
        control: float,
        disturbance: float,
    ) -> np.ndarray:
        # Disturbance is modeled as additive cart force after actuator saturation.
        actuator_force = float(control)
        limit = abs(float(self.actuator_force_limit_n))
        if np.isfinite(limit):
            actuator_force = float(np.clip(actuator_force, -limit, limit))
        force = actuator_force + float(disturbance)

        cart_pos, cart_vel, phi, phi_dot = x
        del cart_pos

        p = self.I * (self.M + self.m) + self.M * self.m * self.l**2

        dcart_pos_dt = cart_vel
        dphi_dt = phi_dot

        if self._use_nonlinear:
            cos_phi = float(np.cos(phi))
            sin_phi = float(np.sin(phi))

            a11 = self.M + self.m
            a12 = -self.m * self.l * cos_phi
            a21 = -self.m * self.l * cos_phi
            a22 = self.I + self.m * self.l**2

            rhs1 = force - self.b * cart_vel - self.m * self.l * sin_phi * phi_dot**2
            rhs2 = self.m * self.g * self.l * sin_phi

            determinant = a11 * a22 - a12 * a21
            if abs(determinant) <= float(np.finfo(float).eps):
                raise ValueError("Inverted pendulum dynamics matrix is singular.")

            dcart_vel_dt = (rhs1 * a22 - a12 * rhs2) / determinant
            dphi_dot_dt = (a11 * rhs2 - rhs1 * a21) / determinant
        else:
            dcart_vel_dt = (
                -((self.I + self.m * self.l**2) * self.b / p) * cart_vel
                + ((self.m**2 * self.g * self.l**2) / p) * phi
                + ((self.I + self.m * self.l**2) / p) * force
            )
            dphi_dot_dt = (
                -(self.m * self.l * self.b / p) * cart_vel
                + (self.m * self.g * self.l * (self.M + self.m) / p) * phi
                + (self.m * self.l / p) * force
            )

        return np.array([dcart_pos_dt, dcart_vel_dt, dphi_dt, dphi_dot_dt], dtype=float)

    def compute_kpis(
        self,
        time_sec: np.ndarray,
        ref: np.ndarray | dict[str, np.ndarray],
        meas: np.ndarray | dict[str, np.ndarray],
        config: SimulationConfig,
    ) -> dict[str, Any]:
        """Return per-channel KPI bundles for cart-position tracking and phi regulation."""
        if not isinstance(ref, dict) or not isinstance(meas, dict):
            raise ValueError(
                "InvertedPendulumSetup expects dict-valued ref and meas channels."
            )

        required = ("x_cart", "phi_angle")
        missing = [key for key in required if key not in ref or key not in meas]
        if missing:
            raise KeyError(
                "InvertedPendulumSetup requires 'x_cart' and 'phi_angle' channels in ref and meas."
            )

        x_kpis = super().compute_kpis(
            time_sec=time_sec,
            ref=np.asarray(ref["x_cart"], dtype=float),
            meas=np.asarray(meas["x_cart"], dtype=float),
            config=config,
        )

        phi_kpis = self._compute_phi_regulation_kpis(
            time_sec=np.asarray(time_sec, dtype=float),
            phi_meas=np.asarray(meas["phi_angle"], dtype=float),
            config=config,
        )

        return {
            "channels": {
                "x_cart": x_kpis,
                "phi_angle": phi_kpis,
            }
        }

    def _compute_phi_regulation_kpis(
        self,
        time_sec: np.ndarray,
        phi_meas: np.ndarray,
        config: SimulationConfig,
    ) -> dict[str, Any]:
        """Compute phi regulation KPIs from warmup onward against phi_target=0."""
        eps = float(np.finfo(float).eps)
        if phi_meas.size == 0:
            return {
                "overshoot_pct": 0.0,
                "rise_time_sec": float(config.horizon_sec),
                "settling_time_sec": float(config.horizon_sec),
                "steady_state_error_pct": 0.0,
                "settled_within_horizon": False,
                "simulation_horizon_sec": float(config.horizon_sec),
                "max_abs_rad": 0.0,
            }

        event_start = int(np.clip(int(config.warmup_samples), 0, phi_meas.size - 1))
        phi_step = np.asarray(phi_meas[event_start:], dtype=float)
        time_step = np.asarray(time_sec[event_start:] - time_sec[event_start], dtype=float)
        if phi_step.size == 0:
            return {
                "overshoot_pct": 0.0,
                "rise_time_sec": float(config.horizon_sec),
                "settling_time_sec": float(config.horizon_sec),
                "steady_state_error_pct": 0.0,
                "settled_within_horizon": False,
                "simulation_horizon_sec": float(config.horizon_sec),
                "max_abs_rad": 0.0,
            }

        if not np.all(np.isfinite(phi_step)) or not np.all(np.isfinite(time_step)):
            invalid = self._invalid_kpis(config=config)
            invalid["max_abs_rad"] = 0.0
            return invalid

        # Percent-style phi KPIs are normalized to the 20-degree design bound.
        phi_scale_rad = 0.35
        target = 0.0
        error = np.asarray(phi_step - target, dtype=float)
        abs_error = np.abs(error)
        peak_abs_error = float(np.max(abs_error))

        overshoot_pct = peak_abs_error / phi_scale_rad * 100.0
        max_abs_rad = peak_abs_error

        tolerance = 0.02 * phi_scale_rad
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
                settling_time_sec = float(time_step[last_outside + 1])
                settled_within_horizon = settling_time_sec < config.horizon_sec

        if peak_abs_error <= eps:
            rise_time_sec = 0.0
        else:
            level90 = 0.9 * peak_abs_error
            rise_crossing = self._first_crossing_time(
                t=time_step,
                y=abs_error,
                level=level90,
                direction=1.0,
            )
            if rise_crossing is None:
                rise_time_sec = float(config.horizon_sec)
            else:
                rise_time_sec = float(rise_crossing)

        steady_state_error_pct = abs(float(error[-1])) / phi_scale_rad * 100.0

        return {
            "overshoot_pct": float(overshoot_pct),
            "rise_time_sec": float(rise_time_sec),
            "settling_time_sec": float(settling_time_sec),
            "steady_state_error_pct": float(steady_state_error_pct),
            "settled_within_horizon": bool(settled_within_horizon),
            "simulation_horizon_sec": float(config.horizon_sec),
            "max_abs_rad": float(max_abs_rad),
        }
