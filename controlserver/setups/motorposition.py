"""Motor position setup for the feedback loop server."""

from __future__ import annotations

import numpy as np

from .base import BaseSetup, SimulationConfig


class MotorPositionSetup(BaseSetup):
    """Continuous-time DC motor position simulation with sampled remote control."""

    name = "motorposition"

    # Parameters from MotorPosition.tex.
    J = 3.2284e-6
    b = 3.5077e-6
    K = 0.0274
    R = 4.0
    L = 2.75e-6

    def initial_state(self) -> np.ndarray:
        # x = [theta_rad, omega_rad_per_sec, armature_current_amp]
        return np.array([0.0, 0.0, 0.0], dtype=float)

    def reference_for_step(self, step_index: int, config: SimulationConfig) -> float:
        if step_index < config.warmup_samples:
            return 0.0
        return config.step_ref

    def measurement_from_state(self, state: np.ndarray) -> float:
        return float(state[0])

    def _rhs(
        self,
        _t: float,
        x: np.ndarray,
        armature_voltage: float,
        disturbance: float,
    ) -> np.ndarray:
        del disturbance
        theta, omega, current = x
        del theta  # State included for clarity; derivative does not directly depend on theta.
        dtheta_dt = omega
        domega_dt = (-self.b / self.J) * omega + (self.K / self.J) * current
        dcurrent_dt = (
            (-self.K / self.L) * omega
            + (-self.R / self.L) * current
            + (1.0 / self.L) * armature_voltage
        )
        return np.array([dtheta_dt, domega_dt, dcurrent_dt], dtype=float)
