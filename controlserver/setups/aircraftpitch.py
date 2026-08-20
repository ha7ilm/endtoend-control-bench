"""Aircraft pitch setup for the feedback loop server."""

from __future__ import annotations

import numpy as np

from .base import BaseSetup, SimulationConfig


class AircraftPitchSetup(BaseSetup):
    """Linearized longitudinal aircraft pitch dynamics."""

    name = "aircraftpitch"

    # Parameters from AircraftPitch.tex / aircraftpitch_digital.m.
    a11 = -0.313
    a12 = 56.7
    b1 = 0.232

    a21 = -0.0139
    a22 = -0.426
    b2 = 0.0203

    a32 = 56.7

    def initial_state(self) -> np.ndarray:
        # x = [alpha_rad, q_rad_per_sec, theta_rad]
        return np.array([0.0, 0.0, 0.0], dtype=float)

    def reference_for_step(self, step_index: int, config: SimulationConfig) -> float:
        if step_index < config.warmup_samples:
            return 0.0
        return config.step_ref

    def measurement_from_state(self, state: np.ndarray) -> float:
        # Output is pitch angle theta.
        return float(state[2])

    def _rhs(
        self,
        _t: float,
        x: np.ndarray,
        elevator_deflection: float,
        disturbance: float,
    ) -> np.ndarray:
        del disturbance

        alpha, pitch_rate, theta = x
        del theta

        dalpha_dt = self.a11 * alpha + self.a12 * pitch_rate + self.b1 * elevator_deflection
        dq_dt = self.a21 * alpha + self.a22 * pitch_rate + self.b2 * elevator_deflection
        dtheta_dt = self.a32 * pitch_rate

        return np.array([dalpha_dt, dq_dt, dtheta_dt], dtype=float)
