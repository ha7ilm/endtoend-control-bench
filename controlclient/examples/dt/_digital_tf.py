"""Utility helpers for discrete-time controller transfer functions."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np


def _as_real_array(values: Iterable[float] | np.ndarray, name: str) -> np.ndarray:
    arr = np.asarray(list(values), dtype=np.complex128).reshape(-1)
    if arr.size == 0:
        raise ValueError(f"{name} must not be empty.")
    arr = np.real_if_close(arr, tol=1000)
    if np.iscomplexobj(arr):
        raise ValueError(f"{name} must be real-valued.")
    return np.asarray(arr, dtype=float)


class DiscreteTransferController:
    """SISO causal controller implemented as a transfer function in z^-1."""

    def __init__(
        self,
        numerator_q: Sequence[float],
        denominator_q: Sequence[float],
        *,
        control_limit: float | None = None,
    ) -> None:
        b = _as_real_array(numerator_q, "numerator_q")
        a = _as_real_array(denominator_q, "denominator_q")
        if np.isclose(a[0], 0.0):
            raise ValueError("The first denominator coefficient must be non-zero.")

        scale = float(a[0])
        self._b = b / scale
        self._a = a / scale

        self._error_hist = np.zeros(self._b.size, dtype=float)
        self._control_hist = np.zeros(max(self._a.size - 1, 0), dtype=float)
        self._control_limit = None if control_limit is None else abs(float(control_limit))

    @classmethod
    def from_zpk(
        cls,
        zeros_z: Sequence[float],
        poles_z: Sequence[float],
        gain: float,
        *,
        control_limit: float | None = None,
    ) -> "DiscreteTransferController":
        zeros = _as_real_array(zeros_z, "zeros_z")
        poles = _as_real_array(poles_z, "poles_z")
        if zeros.size > poles.size:
            raise ValueError("Non-causal controller: more zeros than poles in z-domain.")

        # Convert from z-domain factors to q = z^-1 factors.
        b_q = np.poly(zeros) * float(gain)
        a_q = np.poly(poles)

        # If denominator order exceeds numerator order, z->q conversion adds pure delay q^(m-n).
        order_gap = poles.size - zeros.size
        if order_gap > 0:
            b_q = np.concatenate((np.zeros(order_gap, dtype=float), b_q.astype(float)))

        return cls(b_q, a_q, control_limit=control_limit)

    def step(self, error: float) -> float:
        if self._error_hist.size > 1:
            self._error_hist[1:] = self._error_hist[:-1]
        self._error_hist[0] = float(error)

        control = float(np.dot(self._b, self._error_hist))
        if self._control_hist.size > 0:
            control -= float(np.dot(self._a[1:], self._control_hist))

        if not np.isfinite(control):
            control = 0.0

        if self._control_limit is not None:
            control = float(np.clip(control, -self._control_limit, self._control_limit))

        if self._control_hist.size > 1:
            self._control_hist[1:] = self._control_hist[:-1]
        if self._control_hist.size > 0:
            self._control_hist[0] = control

        return control


def pid_tustin_coefficients(kp: float, ki: float, kd: float, dt: float) -> tuple[np.ndarray, np.ndarray]:
    """Return q-domain coefficients for PID discretized with Tustin's method."""
    dt = float(dt)
    if dt <= 0.0:
        raise ValueError("dt must be positive.")

    ki_term = float(ki) * dt / 2.0
    kd_term = 2.0 * float(kd) / dt
    kp = float(kp)

    b_q = np.array(
        [
            kp + ki_term + kd_term,
            2.0 * (ki_term - kd_term),
            -kp + ki_term + kd_term,
        ],
        dtype=float,
    )
    a_q = np.array([1.0, 0.0, -1.0], dtype=float)
    return b_q, a_q
