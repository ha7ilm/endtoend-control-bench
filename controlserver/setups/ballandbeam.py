"""Ball and beam setup for the feedback loop server."""

from __future__ import annotations

from typing import Mapping

import numpy as np
from scipy.integrate import solve_ivp

from .base import BaseSetup, SimulationConfig


class BallAndBeamSetup(BaseSetup):
    """Ball-and-beam plant with linear, nonlinear, and actuator-NL DT variants."""

    name = "ballandbeam"

    # Parameters from BallAndBeam.tex / ballandbeam_digital.m.
    m = 0.111
    R = 0.015
    g = -9.8
    L = 1.0
    d = 0.03
    J = 9.99e-6

    # Actuator model defaults for ballandbeam_dt_nl_act.
    actuator_tau_sec = 0.08
    actuator_theta_limit_rad = 6.0
    actuator_theta_dot_limit_rad_per_sec = 20.0

    def __init__(
        self,
        *,
        variant_name: str | None = None,
        model_params: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(variant_name=variant_name, model_params=model_params)
        if "_dt_nl_act" in self.name:
            self._model_mode = "nl_act"
        elif self.name.endswith("_dt_nl"):
            self._model_mode = "nl_foh"
        else:
            self._model_mode = "linear"

        self._previous_gear_angle: float | None = None
        self._interval_beam_angle_start = 0.0
        self._interval_beam_angle_rate = 0.0

    def initial_state(self) -> np.ndarray:
        self._previous_gear_angle = 0.0
        self._interval_beam_angle_start = 0.0
        self._interval_beam_angle_rate = 0.0
        if self._model_mode == "nl_act":
            # x = [ball_position_m, ball_velocity_m_per_sec, gear_angle_rad]
            return np.array([0.0, 0.0, 0.0], dtype=float)
        # x = [ball_position_m, ball_velocity_m_per_sec]
        return np.array([0.0, 0.0], dtype=float)

    def reference_for_step(self, step_index: int, config: SimulationConfig) -> float:
        if step_index < config.warmup_samples:
            return 0.0
        return config.step_ref

    def measurement_from_state(self, state: np.ndarray) -> float:
        return float(state[0])

    def _rhs(
        self,
        t: float,
        x: np.ndarray,
        gear_angle: float,
        disturbance: float,
    ) -> np.ndarray:
        del disturbance
        inertia_term = self.J / self.R**2 + self.m

        if self._model_mode == "nl_act":
            position, velocity, gear_angle_actual = x
            dposition_dt = velocity

            command_limit = abs(float(self.actuator_theta_limit_rad))
            cmd = float(np.clip(float(gear_angle), -command_limit, command_limit))

            tau = max(float(self.actuator_tau_sec), float(np.finfo(float).eps))
            dgear_angle_dt = (cmd - float(gear_angle_actual)) / tau

            rate_limit = abs(float(self.actuator_theta_dot_limit_rad_per_sec))
            dgear_angle_dt = float(np.clip(dgear_angle_dt, -rate_limit, rate_limit))

            beam_angle = (self.d / self.L) * float(gear_angle_actual)
            beam_angle_rate = (self.d / self.L) * dgear_angle_dt

            dvelocity_dt = (
                -self.m * self.g * np.sin(beam_angle)
                + self.m * float(position) * beam_angle_rate**2
            ) / inertia_term
            return np.array([dposition_dt, dvelocity_dt, dgear_angle_dt], dtype=float)

        position, velocity = x
        dposition_dt = velocity

        if self._model_mode == "nl_foh":
            # For the nonlinear variant, treat sampled gear-angle commands as
            # first-order held over one dt interval so alpha_dot is defined.
            beam_angle = (
                self._interval_beam_angle_start
                + self._interval_beam_angle_rate * float(t)
            )
            beam_angle_rate = self._interval_beam_angle_rate
            dvelocity_dt = (
                -self.m * self.g * np.sin(beam_angle)
                + self.m * float(position) * beam_angle_rate**2
            ) / inertia_term
        else:
            plant_gain = -self.m * self.g * self.d / (self.L * inertia_term)
            dvelocity_dt = plant_gain * float(gear_angle)

        return np.array([dposition_dt, dvelocity_dt], dtype=float)

    def integrate_one_step(
        self,
        state: np.ndarray,
        control: float,
        disturbance: float,
        dt: float,
    ) -> np.ndarray:
        if self._model_mode == "linear":
            return super().integrate_one_step(state, control, disturbance, dt)

        if self._model_mode == "nl_act":
            current_gear_angle = float(control)
            solution = solve_ivp(
                fun=lambda t, x: self._rhs(t, x, current_gear_angle, disturbance),
                t_span=(0.0, dt),
                y0=state,
                method="RK45",
                rtol=1e-8,
                atol=1e-10,
            )
            return np.asarray(solution.y[:, -1], dtype=float)

        current_gear_angle = float(control)
        previous_gear_angle = (
            current_gear_angle
            if self._previous_gear_angle is None
            else float(self._previous_gear_angle)
        )

        beam_angle_start = (self.d / self.L) * previous_gear_angle
        beam_angle_end = (self.d / self.L) * current_gear_angle
        self._interval_beam_angle_start = beam_angle_start
        self._interval_beam_angle_rate = (beam_angle_end - beam_angle_start) / float(dt)

        solution = solve_ivp(
            fun=lambda t, x: self._rhs(t, x, current_gear_angle, disturbance),
            t_span=(0.0, dt),
            y0=state,
            method="RK45",
            rtol=1e-8,
            atol=1e-10,
        )

        self._previous_gear_angle = current_gear_angle
        return np.asarray(solution.y[:, -1], dtype=float)
