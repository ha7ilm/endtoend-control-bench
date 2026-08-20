"""Motor speed setup for the feedback loop server."""

from __future__ import annotations

from typing import Mapping

import numpy as np

from .base import BaseSetup, SimulationConfig


class MotorSpeedSetup(BaseSetup):
    """Continuous-time DC motor simulation with sampled remote control."""

    name = "motorspeed"

    # Motor parameters from MotorSpeed.tex
    J = 0.01
    b = 0.1
    K = 0.01
    R = 1.0
    L = 0.5
    actuator_voltage_limit_volts = 24.0

    def __init__(
        self,
        *,
        variant_name: str | None = None,
        model_params: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(variant_name=variant_name, model_params=model_params)
        self._use_voltage_limit = self.name.startswith("motorspeed_dt_lim")

    def initial_state(self) -> np.ndarray:
        # x = [omega_rad_per_sec, armature_current_amp]
        return np.array([0.0, 0.0], dtype=float)

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
        voltage = float(armature_voltage)
        if self._use_voltage_limit:
            limit = abs(float(self.actuator_voltage_limit_volts))
            voltage = float(np.clip(voltage, -limit, limit))

        omega, current = x
        domega_dt = (-self.b / self.J) * omega + (self.K / self.J) * current
        dcurrent_dt = (
            (-self.K / self.L) * omega
            + (-self.R / self.L) * current
            + (1.0 / self.L) * voltage
        )
        return np.array([domega_dt, dcurrent_dt], dtype=float)
