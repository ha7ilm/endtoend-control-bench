"""Suspension setup for the feedback loop server."""

from __future__ import annotations

from typing import Literal

import numpy as np

from .base import BaseSetup, SimulationConfig


class SuspensionSetup(BaseSetup):
    """Quarter-car active suspension with road-step disturbance rejection."""

    name = "suspension"

    # Parameters from Suspension.tex
    m1 = 2500.0  # 1/4 bus body mass [kg]
    m2 = 320.0  # suspension mass [kg]
    k1 = 80000.0  # suspension spring constant [N/m]
    k2 = 500000.0  # tire spring constant [N/m]
    b1 = 350.0  # suspension damping [N*s/m]
    b2 = 15020.0  # tire damping [N*s/m]

    def initial_state(self) -> np.ndarray:
        # x = [x1_m, x1_dot_m_per_sec, x2_m, x2_dot_m_per_sec]
        return np.array([0.0, 0.0, 0.0, 0.0], dtype=float)

    def reference_for_step(self, step_index: int, config: SimulationConfig) -> float:
        del step_index
        del config
        # Regulator objective: return suspension travel to zero.
        return 0.0

    def disturbance_for_step(self, step_index: int, config: SimulationConfig) -> float:
        if step_index < config.warmup_samples:
            return 0.0
        return float(config.step_ref)

    def measurement_from_state(self, state: np.ndarray) -> float:
        x1 = float(state[0])
        x2 = float(state[2])
        return x1 - x2

    def kpi_mode(self) -> Literal["step", "disturbance"]:
        return "disturbance"

    def kpi_event_start_index(
        self,
        time_sec: np.ndarray,
        ref: np.ndarray,
        meas: np.ndarray,
        config: SimulationConfig,
    ) -> int:
        del time_sec
        del ref
        del meas
        return int(config.warmup_samples)

    def kpi_target_value(self, config: SimulationConfig) -> float:
        del config
        return 0.0

    def kpi_normalization_scale(self, config: SimulationConfig) -> float:
        return abs(float(config.step_ref))

    def _rhs(
        self,
        _t: float,
        x: np.ndarray,
        actuator_force: float,
        road_displacement: float,
    ) -> np.ndarray:
        x1, x1_dot, x2, x2_dot = x

        dx1_dt = x1_dot
        dx2_dt = x2_dot

        dx1_dot_dt = (
            -self.b1 * (x1_dot - x2_dot) - self.k1 * (x1 - x2) + actuator_force
        ) / self.m1

        # Road disturbance is piecewise-constant after step onset, so w_dot = 0.
        dx2_dot_dt = (
            self.b1 * (x1_dot - x2_dot)
            + self.k1 * (x1 - x2)
            - self.b2 * x2_dot
            + self.k2 * (road_displacement - x2)
            - actuator_force
        ) / self.m2

        return np.array([dx1_dt, dx1_dot_dt, dx2_dt, dx2_dot_dt], dtype=float)

