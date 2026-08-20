"""Shared helpers for Inverted Pendulum digital controller examples."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
from scipy.linalg import solve_discrete_are
from scipy.signal import cont2discrete, place_poles

from controlclient.machine import MachineClient


def _as_signal_map(value: Any, field: str) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Inverted pendulum '{field}' must be a map with x_cart/phi_angle keys.")

    try:
        x = float(value["x_cart"])
        phi = float(value["phi_angle"])
    except KeyError as exc:
        raise ValueError(
            f"Inverted pendulum '{field}' must contain keys 'x_cart' and 'phi_angle'."
        ) from exc

    if not np.isfinite(x) or not np.isfinite(phi):
        raise ValueError(f"Inverted pendulum '{field}' values must be finite.")
    return {"x_cart": x, "phi_angle": phi}


def _continuous_state_space_matrices() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # Parameters from InvertedPendulum.tex / invertedpendulum_digital.m.
    m_cart = 0.5
    m_pend = 0.2
    friction = 0.1
    inertia = 0.006
    gravity = 9.8
    length = 0.3

    p = inertia * (m_cart + m_pend) + m_cart * m_pend * length**2

    a = np.array(
        [
            [0.0, 1.0, 0.0, 0.0],
            [0.0, -((inertia + m_pend * length**2) * friction / p), (m_pend**2 * gravity * length**2) / p, 0.0],  # noqa: E501
            [0.0, 0.0, 0.0, 1.0],
            [0.0, -(m_pend * length * friction / p), m_pend * gravity * length * (m_cart + m_pend) / p, 0.0],  # noqa: E501
        ],
        dtype=float,
    )
    b = np.array(
        [
            [0.0],
            [(inertia + m_pend * length**2) / p],
            [0.0],
            [m_pend * length / p],
        ],
        dtype=float,
    )
    c = np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ],
        dtype=float,
    )
    return a, b, c


def _discrete_state_space_matrices(dt: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    a, b, c = _continuous_state_space_matrices()
    d = np.zeros((2, 1), dtype=float)
    ad, bd, cd, _, _ = cont2discrete((a, b, c, d), dt=float(dt), method="zoh")
    return np.asarray(ad, dtype=float), np.asarray(bd, dtype=float), np.asarray(cd, dtype=float)


class InvertedPendulumDigitalLqrController:
    """LQR controller variants used across invertedpendulum_digital.m trials."""

    def __init__(
        self,
        *,
        dt: float = 0.01,
        q_cart: float = 1.0,
        q_phi: float = 1.0,
        r: float = 1.0,
        nbar: float | None = None,
        use_observer: bool = False,
        observer_poles: Sequence[float] = (-0.2, -0.21, -0.22, -0.23),
        control_limit: float = 10000.0,
    ) -> None:
        self.dt = float(dt)
        if self.dt <= 0.0:
            raise ValueError("dt must be positive.")

        self._ad, self._bd, self._cd = _discrete_state_space_matrices(self.dt)

        q = np.diag([float(q_cart), 0.0, float(q_phi), 0.0]).astype(float)
        r_mat = np.array([[float(r)]], dtype=float)

        p = solve_discrete_are(self._ad, self._bd, q, r_mat)
        self._k = np.linalg.solve(
            self._bd.T @ p @ self._bd + r_mat,
            self._bd.T @ p @ self._ad,
        ).reshape(-1)

        self._nbar = None if nbar is None else float(nbar)
        self._control_limit = abs(float(control_limit))
        self._previous_control = 0.0

        self._observer_gain: np.ndarray | None = None
        self._xhat = np.zeros(4, dtype=float)
        self._have_previous_sample = False
        self._previous_x = 0.0
        self._previous_phi = 0.0

        if use_observer:
            gain = place_poles(
                self._ad.T,
                self._cd.T,
                [float(pole) for pole in observer_poles],
                method="YT",
            ).gain_matrix
            self._observer_gain = np.asarray(gain.T, dtype=float)

    def _estimate_state(self, x: float, phi: float) -> np.ndarray:
        if self._observer_gain is not None:
            del x
            del phi
            # For the observer-based trial, the control law uses the current
            # state estimate xhat[k]. The observer then propagates xhat[k+1].
            return self._xhat.copy()

        if self._have_previous_sample:
            x_dot = (x - self._previous_x) / self.dt
            phi_dot = (phi - self._previous_phi) / self.dt
        else:
            x_dot = 0.0
            phi_dot = 0.0
            self._have_previous_sample = True

        self._previous_x = x
        self._previous_phi = phi
        self._xhat = np.array([x, x_dot, phi, phi_dot], dtype=float)
        return self._xhat

    def step(self, ref: Mapping[str, Any], meas: Mapping[str, Any]) -> float:
        ref_signal = _as_signal_map(ref, "ref")
        meas_signal = _as_signal_map(meas, "meas")
        x_meas = meas_signal["x_cart"]
        phi_meas = meas_signal["phi_angle"]

        state_estimate = self._estimate_state(
            x=x_meas,
            phi=phi_meas,
        )

        # Baseline digital CTMS model uses unity reference scaling at the
        # plant input; Nbar replaces that scale when precompensation is enabled.
        ref_scale = 1.0 if self._nbar is None else float(self._nbar)
        control = ref_scale * ref_signal["x_cart"] - float(self._k @ state_estimate)

        if not np.isfinite(control):
            control = 0.0
        control = float(np.clip(control, -self._control_limit, self._control_limit))

        if self._observer_gain is not None:
            # xhat[k+1] = A xhat[k] + B u[k] + L (y[k] - C xhat[k])
            y = np.array([x_meas, phi_meas], dtype=float)
            innovation = y - self._cd @ state_estimate
            self._xhat = (
                self._ad @ state_estimate
                + self._bd[:, 0] * control
                + self._observer_gain @ innovation
            )

        self._previous_control = control
        return control


def run_invertedpendulum_digital_trial(
    controller: InvertedPendulumDigitalLqrController,
    description: str,
    why: str,
    *,
    setup: str = "invertedpendulum_dt",
) -> None:
    with MachineClient(setup=setup, description=description, why=why) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            ref = _as_signal_map(ctl_input["ref"], "ref")
            meas = _as_signal_map(ctl_input["meas"], "meas")
            machine.write({"control": controller.step(ref=ref, meas=meas)})
