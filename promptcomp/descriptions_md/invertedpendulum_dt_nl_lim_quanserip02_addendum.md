# `invertedpendulum_dt_nl_lim_quanserip02` Addendum

In this task, you are designing a controller for the plant `invertedpendulum_dt_nl_lim_quanserip02`, which differs from the linear plant described before, in the following ways.

Compared with the regular linear baseline, this setup uses full nonlinear cart-pendulum dynamics, Quanser IP02/SIP parameter values, and a symmetric cart-force actuator limit.

## State, input, and outputs

- State: $x = [x,\ \dot x,\ \phi,\ \dot\phi]$
- Controller command: $u$ (cart force command)
- Applied force after actuator and disturbance: $F = u_{act} + d$
- Outputs: cart position $x$ and pendulum angle deviation $\phi$

## Actuator limit

$$
u_{act} = \mathrm{clip}(u,\ -F_{max},\ +F_{max})
$$

with:

$$
F_{max} = 13.44\ \mathrm{N}
$$

## Nonlinear equations

Kinematics:

$$
\frac{d}{dt}x = \dot x, \qquad \frac{d}{dt}\phi = \dot\phi
$$

Dynamics are solved from:

$$
\begin{bmatrix}
M+m & -m l \cos\phi \\
-m l \cos\phi & I + m l^2
\end{bmatrix}
\begin{bmatrix}
\ddot x \\
\ddot\phi
\end{bmatrix}
=
\begin{bmatrix}
F - b\dot x - m l \sin\phi\ \dot\phi^2 \\
m g l \sin\phi
\end{bmatrix}
$$

This replaces the small-angle linearized equations used earlier.

## Parameters for `invertedpendulum_dt_nl_lim_quanserip02`

- $M = 0.57$
- $m = 0.230$
- $b = 5.4$
- $I = 7.88\times10^{-3}$
- $g = 9.81$
- $l = 0.3302$
- Actuator limit: $|u_{act}| \le 13.44\ \mathrm{N}$
- Sampling: $dt = 0.01\ \mathrm{s}$

## What changes versus the linear plant described before

- Nonlinear trigonometric terms ($\sin\phi$, $\cos\phi$) are active.
- Centrifugal coupling term $m l \sin\phi\ \dot\phi^2$ is included.
- Physical parameters are substantially different from CTMS defaults.
- Input force is hard-limited to $\pm 13.44$ N.
- Behavior is strongly state-dependent and constraint-limited outside small-angle conditions.
