"""Cruise control setup for the feedback loop server."""

from __future__ import annotations

from typing import Mapping

import numpy as np

from .base import BaseSetup, SimulationConfig


class CruiseControlSetup(BaseSetup):
    """First-order cruise-control plant simulation with sampled remote control."""

    name = "cruisecontrol"

    # Parameters from CruiseControl.tex.
    m = 1000.0  # kg
    b = 50.0  # N*s/m
    traction_force_min_n = -np.inf  # N
    traction_force_max_n = np.inf  # N

    def __init__(
        self,
        *,
        variant_name: str | None = None,
        model_params: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(variant_name=variant_name, model_params=model_params)
        if float(self.traction_force_min_n) > float(self.traction_force_max_n):
            raise ValueError(
                "traction_force_min_n must be less than or equal to traction_force_max_n."
            )

    def initial_state(self) -> np.ndarray:
        # x = [vehicle_speed_m_per_sec]
        return np.array([0.0], dtype=float)

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
        traction_force: float,
        disturbance: float,
    ) -> np.ndarray:
        del disturbance
        force = float(
            np.clip(
                float(traction_force),
                float(self.traction_force_min_n),
                float(self.traction_force_max_n),
            )
        )
        # m*dv/dt + b*v = u  ->  dv/dt = (-b/m)*v + (1/m)*u
        velocity = float(x[0])
        dvelocity_dt = (-self.b / self.m) * velocity + (1.0 / self.m) * force
        return np.array([dvelocity_dt], dtype=float)
