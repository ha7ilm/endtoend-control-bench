"""Suspension digital controllers (place-based and observer/LQR extra)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.linalg import solve_discrete_are
from scipy.signal import cont2discrete, place_poles, ss2tf

from controlclient.machine import MachineClient


@dataclass(frozen=True)
class SuspensionDigitalControllerConfig:
    dt: float = 0.0005
    warmup_samples: int = 2
    disturbance_step_m: float = 0.1
    control_limit: float = 200000.0


def _build_discrete_model(dt: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build the transformed discrete suspension_dt model used in suspension_digital.m."""
    # State-space model from suspension_digital.m: x=[X1, X1dot, Y1, Y1dot], y=Y1.
    m1 = 2500.0
    m2 = 320.0
    k1 = 80000.0
    k2 = 500000.0
    b1 = 350.0
    b2 = 15020.0

    a = np.array(
        [
            [0.0, 1.0, 0.0, 0.0],
            [
                -(b1 * b2) / (m1 * m2),
                0.0,
                ((b1 / m1) * ((b1 / m1) + (b1 / m2) + (b2 / m2))) - (k1 / m1),
                -(b1 / m1),
            ],
            [b2 / m2, 0.0, -((b1 / m1) + (b1 / m2) + (b2 / m2)), 1.0],
            [k2 / m2, 0.0, -((k1 / m1) + (k1 / m2) + (k2 / m2)), 0.0],
        ],
        dtype=float,
    )
    b = np.array(
        [
            [0.0, 0.0],
            [1.0 / m1, (b1 * b2) / (m1 * m2)],
            [0.0, -(b2 / m2)],
            [(1.0 / m1) + (1.0 / m2), -(k2 / m2)],
        ],
        dtype=float,
    )
    c = np.array([[0.0, 0.0, 1.0, 0.0]], dtype=float)
    d = np.zeros((1, 2), dtype=float)

    ad, bd, cd, _, _ = cont2discrete((a, b, c, d), dt=float(dt), method="zoh")
    return np.asarray(ad, dtype=float), np.asarray(bd, dtype=float), np.asarray(cd, dtype=float)


def _build_runtime_discrete_model(dt: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build a discrete model aligned with controlserver/setups/suspension.py dynamics."""
    m1 = 2500.0
    m2 = 320.0
    k1 = 80000.0
    k2 = 500000.0
    b1 = 350.0
    b2 = 15020.0

    # Runtime states are [x1, x1_dot, x2, x2_dot], output is y=x1-x2.
    a = np.array(
        [
            [0.0, 1.0, 0.0, 0.0],
            [-(k1 / m1), -(b1 / m1), (k1 / m1), (b1 / m1)],
            [0.0, 0.0, 0.0, 1.0],
            [(k1 / m2), (b1 / m2), -((k1 + k2) / m2), -((b1 + b2) / m2)],
        ],
        dtype=float,
    )
    b = np.array(
        [
            [0.0, 0.0],
            [1.0 / m1, 0.0],
            [0.0, 0.0],
            [-(1.0 / m2), (k2 / m2)],
        ],
        dtype=float,
    )
    c = np.array([[1.0, 0.0, -1.0, 0.0]], dtype=float)
    d = np.zeros((1, 2), dtype=float)

    ad, bd, cd, _, _ = cont2discrete((a, b, c, d), dt=float(dt), method="zoh")
    return np.asarray(ad, dtype=float), np.asarray(bd, dtype=float), np.asarray(cd, dtype=float)


def _build_observer_gain(ad: np.ndarray, cd: np.ndarray) -> np.ndarray:
    qn = np.diag([1e-7, 1e-3, 1e-7, 1e-3])
    rn = np.array([[1e-6]], dtype=float)
    p = solve_discrete_are(ad.T, cd.T, qn, rn)
    return np.asarray(p @ cd.T @ np.linalg.inv(cd @ p @ cd.T + rn), dtype=float).reshape(-1)


def _augment_model_for_integrator(
    ad: np.ndarray,
    bd: np.ndarray,
    cd: np.ndarray,
    dt: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build the 5-state augmented model used in the MATLAB digital design."""
    aa = np.block(
        [
            [ad, np.zeros((4, 1), dtype=float)],
            [dt * cd, np.array([[1.0]], dtype=float)],
        ]
    )
    ba = np.vstack((bd, np.zeros((1, 2), dtype=float)))
    ca = np.hstack((cd, np.zeros((1, 1), dtype=float)))
    return aa, ba, ca


class SuspensionPlaceEstimatorController:
    """Observer + pole-placement gain for the runtime suspension_dt dynamics."""

    def __init__(self, cfg: SuspensionDigitalControllerConfig | None = None) -> None:
        self.cfg = cfg or SuspensionDigitalControllerConfig()

        ad, bd, cd = _build_runtime_discrete_model(self.cfg.dt)
        self._ad = ad
        self._bd = bd
        self._cd = cd.reshape(-1)

        self._observer_gain = _build_observer_gain(ad=ad, cd=cd)
        self._k = self._build_place_feedback_gain(ad=ad, bd=bd, cd=cd, dt=self.cfg.dt)

        self._xhat = np.zeros(4, dtype=float)
        self._integral_output = 0.0
        self._previous_control = 0.0
        self._step_index = 0

    @staticmethod
    def _project_inside_unit_circle(pole: complex) -> complex:
        mag = abs(pole)
        if mag < 1.0:
            return pole
        # scipy and MATLAB numerical conversions can differ slightly; keep a stable projection.
        return pole * (0.999 / max(mag, np.finfo(float).eps))

    def _build_place_feedback_gain(
        self,
        ad: np.ndarray,
        bd: np.ndarray,
        cd: np.ndarray,
        dt: float,
    ) -> np.ndarray:
        aa, ba, ca = _augment_model_for_integrator(ad=ad, bd=bd, cd=cd, dt=dt)

        # Match suspension_digital.m workflow: choose 3 poles from zeros of input-0 path,
        # then append p4=0.9992 and p5=0.5.
        num, _den = ss2tf(aa, ba, ca, np.zeros((1, 2), dtype=float), input=0)
        num_vec = np.asarray(num, dtype=float).reshape(-1)
        num_vec = np.trim_zeros(num_vec, trim="f")
        if num_vec.size <= 1:
            raise ValueError("Failed to derive augmented-input transfer numerator for pole selection.")

        zeros = np.roots(num_vec)
        if zeros.size == 0:
            raise ValueError("No zeros found for pole-selection stage.")

        # Pick one real zero and one complex-conjugate pair when available.
        sorted_zeros = sorted(zeros, key=lambda z: (abs(abs(z) - 1.0), -abs(np.imag(z))))

        real_zero: complex | None = None
        complex_pos: complex | None = None
        for z in sorted_zeros:
            if abs(np.imag(z)) < 1e-8 and real_zero is None:
                real_zero = complex(float(np.real(z)), 0.0)
            if np.imag(z) > 1e-8 and complex_pos is None:
                complex_pos = complex(z)

        selected: list[complex] = []
        if real_zero is not None:
            selected.append(real_zero)
        if complex_pos is not None:
            selected.extend([complex_pos, np.conj(complex_pos)])

        if len(selected) < 3:
            for z in sorted_zeros:
                candidate = complex(z)
                if any(abs(candidate - s) < 1e-8 for s in selected):
                    continue
                selected.append(candidate)
                if len(selected) == 3:
                    break

        while len(selected) < 3:
            selected.append(0.9 - 0.1 * len(selected))

        desired = [self._project_inside_unit_circle(p) for p in selected[:3]]
        desired.extend([0.9992, 0.5])

        gain = place_poles(aa, ba[:, [0]], desired, method="YT").gain_matrix
        return np.asarray(np.real_if_close(gain[0]), dtype=float)

    def step(self, ref: float, meas: float) -> float:
        del ref  # Suspension setup is regulator mode with reference fixed to zero.

        x_pred = (
            self._ad @ self._xhat
            + self._bd[:, 0] * self._previous_control
        )
        y_pred = float(self._cd @ x_pred)
        innovation = float(meas) - y_pred
        self._xhat = x_pred + self._observer_gain * innovation

        self._integral_output += float(self.cfg.dt) * float(meas)
        x_aug = np.concatenate((self._xhat, np.array([self._integral_output], dtype=float)))

        control = -float(self._k @ x_aug)
        if not np.isfinite(control):
            control = 0.0
        control = float(np.clip(control, -self.cfg.control_limit, self.cfg.control_limit))

        self._previous_control = control
        self._step_index += 1
        return control


class SuspensionEstimatorController:
    """Kalman-observer + augmented-state LQR controller (kept as extra)."""

    def __init__(self, cfg: SuspensionDigitalControllerConfig | None = None) -> None:
        self.cfg = cfg or SuspensionDigitalControllerConfig()

        ad, bd, cd = _build_discrete_model(self.cfg.dt)
        self._ad = ad
        self._bd = bd
        self._cd = cd.reshape(-1)

        self._observer_gain = _build_observer_gain(ad=ad, cd=cd)
        self._kx, self._ki = self._build_augmented_feedback_gain(
            ad=ad,
            bd=bd,
            cd=cd,
            dt=self.cfg.dt,
        )

        self._xhat = np.zeros(4, dtype=float)
        self._integral_error = 0.0
        self._previous_control = 0.0
        self._step_index = 0

    @staticmethod
    def _build_augmented_feedback_gain(
        ad: np.ndarray,
        bd: np.ndarray,
        cd: np.ndarray,
        dt: float,
    ) -> tuple[np.ndarray, float]:
        # Augmented integral-of-error state; gain computed via discrete LQR.
        aa = np.block(
            [
                [ad, np.zeros((4, 1), dtype=float)],
                [-dt * cd, np.array([[1.0]], dtype=float)],
            ]
        )
        bu = np.vstack((bd[:, [0]], np.zeros((1, 1), dtype=float)))

        q = np.diag([1e3, 1.0, 2e7, 1.0, 1e10])
        r = np.array([[1.0]], dtype=float)
        p = solve_discrete_are(aa, bu, q, r)
        k = np.linalg.solve(bu.T @ p @ bu + r, bu.T @ p @ aa)
        return np.asarray(k[0, :4], dtype=float), float(k[0, 4])

    def step(self, ref: float, meas: float) -> float:
        disturbance_est = (
            float(self.cfg.disturbance_step_m)
            if self._step_index >= int(self.cfg.warmup_samples)
            else 0.0
        )

        x_pred = (
            self._ad @ self._xhat
            + self._bd[:, 0] * self._previous_control
            + self._bd[:, 1] * disturbance_est
        )
        y_pred = float(self._cd @ x_pred)
        innovation = float(meas) - y_pred
        self._xhat = x_pred + self._observer_gain * innovation

        error = float(ref) - float(meas)
        self._integral_error += float(self.cfg.dt) * error

        control = -(float(self._kx @ self._xhat) + self._ki * self._integral_error)
        if not np.isfinite(control):
            control = 0.0
        control = float(np.clip(control, -self.cfg.control_limit, self.cfg.control_limit))

        self._previous_control = control
        self._step_index += 1
        return control


def run_suspension_digital_place_trial(description: str, why: str) -> None:
    controller = SuspensionPlaceEstimatorController()

    with MachineClient(setup="suspension_dt", description=description, why=why) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            control = controller.step(ref=ctl_input["ref"], meas=ctl_input["meas"])
            machine.write({"control": control})


def run_suspension_digital_trial(description: str, why: str) -> None:
    """Legacy alias: run the observer/LQR suspension_dt digital controller."""
    controller = SuspensionEstimatorController()

    with MachineClient(setup="suspension_dt", description=description, why=why) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                print(ctl_input["kpis"])
                break

            control = controller.step(ref=ctl_input["ref"], meas=ctl_input["meas"])
            machine.write({"control": control})
