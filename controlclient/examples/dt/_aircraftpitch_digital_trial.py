"""Shared helpers for AircraftPitch digital controller examples."""

from __future__ import annotations

import numpy as np
from scipy.linalg import solve_discrete_are
from scipy.signal import cont2discrete, place_poles

from controlclient.machine import MachineClient


def _continuous_state_space_matrices() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # Parameters from AircraftPitch.tex / aircraftpitch_digital.m.
    a = np.array(
        [
            [-0.313, 56.7, 0.0],
            [-0.0139, -0.426, 0.0],
            [0.0, 56.7, 0.0],
        ],
        dtype=float,
    )
    b = np.array([[0.232], [0.0203], [0.0]], dtype=float)
    c = np.array([[0.0, 0.0, 1.0]], dtype=float)
    return a, b, c


def _discrete_state_space_matrices(dt: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    a, b, c = _continuous_state_space_matrices()
    d = np.zeros((1, 1), dtype=float)
    ad, bd, cd, _, _ = cont2discrete((a, b, c, d), dt=float(dt), method="zoh")
    return np.asarray(ad, dtype=float), np.asarray(bd, dtype=float), np.asarray(cd, dtype=float)


class AircraftPitchDigitalLqrController:
    """DLQR controller variants used across aircraftpitch_digital.m trials."""

    def __init__(
        self,
        *,
        dt: float = 0.01,
        p: float = 50.0,
        r: float = 1.0,
        nbar: float | None = None,
        observer_poles: tuple[float, float, float] = (0.4, 0.5, 0.6),
        control_limit: float = 1e6,
    ) -> None:
        self.dt = float(dt)
        if self.dt <= 0.0:
            raise ValueError("dt must be positive.")

        self._ad, self._bd, self._cd = _discrete_state_space_matrices(self.dt)

        q = float(p) * (self._cd.T @ self._cd)
        r_mat = np.array([[float(r)]], dtype=float)
        p_solution = solve_discrete_are(self._ad, self._bd, q, r_mat)
        self._k = np.linalg.solve(
            self._bd.T @ p_solution @ self._bd + r_mat,
            self._bd.T @ p_solution @ self._ad,
        ).reshape(-1)

        gain = place_poles(
            self._ad.T,
            self._cd.T,
            [float(pole) for pole in observer_poles],
            method="YT",
        ).gain_matrix
        self._observer_gain = np.asarray(gain.T, dtype=float).reshape(-1)

        self._nbar = None if nbar is None else float(nbar)
        self._control_limit = abs(float(control_limit))

        self._xhat = np.zeros(3, dtype=float)
        self._previous_control = 0.0

    def step(self, ref: float, meas: float) -> float:
        x_pred = self._ad @ self._xhat + self._bd[:, 0] * self._previous_control
        y_pred = float((self._cd @ x_pred).item())
        innovation = float(meas) - y_pred
        self._xhat = x_pred + self._observer_gain * innovation

        # Baseline CTMS DLQR uses delta = theta_des - Kx; Nbar replaces the
        # unity reference scale when precompensation is enabled.
        ref_scale = 1.0 if self._nbar is None else float(self._nbar)
        control = ref_scale * float(ref) - float(self._k @ self._xhat)

        if not np.isfinite(control):
            control = 0.0
        control = float(np.clip(control, -self._control_limit, self._control_limit))
        self._previous_control = control
        return control


def run_aircraftpitch_digital_trial(
    controller: AircraftPitchDigitalLqrController,
    description: str,
    why: str,
) -> None:
    with MachineClient(setup="aircraftpitch_dt", description=description, why=why) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            control = controller.step(ref=ctl_input["ref"], meas=ctl_input["meas"])
            machine.write({"control": control})
