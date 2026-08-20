# Ball & Beam: System Modeling and Performance Specifications

## Physical setup

A ball is placed on a beam, where it is allowed to roll with 1 degree of freedom along the length of the beam. A lever arm is attached to the beam at one end and a servo gear at the other. As the servo gear turns by an angle $\theta$, the lever changes the angle of the beam by $\alpha$. When the angle is changed from the horizontal position, gravity causes the ball to roll along the beam. A controller will be designed for this system so that the ball's position can be manipulated.

## System parameters

For this setup, we assume the ball rolls without slipping and friction between the beam and ball is negligible. The model parameters are:

| Symbol | Description | Value |
| --- | --- | --- |
| $m$ | Ball mass | $0.111\ \mathrm{kg}$ |
| $R$ | Ball radius | $0.015\ \mathrm{m}$ |
| $J$ | Ball moment of inertia | $9.99\times10^{-6}\ \mathrm{kg\cdot m^2}$ |
| $g$ | Gravitational acceleration | $-9.8\ \mathrm{m/s^2}$ |
| $d$ | Lever arm offset | $0.035\ \mathrm{m}$ |
| $L$ | Beam length | $0.5\ \mathrm{m}$ |
| $d/L$ | Beam-angle gain from servo angle | $0.07$ |
| $\tau$ | Servo actuator lag constant | $0.12\ \mathrm{s}$ |
| $\theta_{max}$ | Servo position limit | $1.0471975511965976\ \mathrm{rad}$ (about $\pm 60^\circ$) |
| $\dot\theta_{max}$ | Servo rate limit | $6.0\ \mathrm{rad/s}$ |
| $dt$ | Sampling period | $0.02\ \mathrm{s}$ |

Variables used in the equations are $r$ (ball position), $\alpha$ (beam angle), and $\theta$ (servo gear angle).

## Design criteria 

For step response:
* Settling time < 3 seconds
* Overshoot < 8%

## System equations

The second derivative of the input angle $\alpha$ actually affects the second derivative of $r$. However, we will ignore this contribution. The Lagrangian equation of motion for the ball is then given by the following:

$$ 0 = \left(\frac{J}{R^2}+m\right) \ddot{r} + m g \sin{\alpha} - m r \dot{\alpha}^2 $$

## Model

## State, input, and output

- State: $x = [r,\ \dot r,\ \theta]$
- Commanded input: $\theta_{cmd}$ (servo command)
- Physical beam angle: $\alpha = \frac{d}{L}\theta$
- Output: $y = r$

## Nonlinear plant and actuator equations

Define:

$$
I_{eq} = \frac{J}{R^2} + m
$$

Actuator dynamics and limits:

$$
\theta_{cmd,sat} = \mathrm{clip}(\theta_{cmd}, -\theta_{max}, \theta_{max})
$$

$$
\dot\theta = \mathrm{clip}\!\left(\frac{\theta_{cmd,sat}-\theta}{\tau}, -\dot\theta_{max}, \dot\theta_{max}\right)
$$

Beam kinematics:

$$
\alpha = \frac{d}{L}\theta, \qquad \dot\alpha = \frac{d}{L}\dot\theta
$$

Ball dynamics:

$$
\dot r = v
$$

$$
\dot v = \frac{-m g \sin(\alpha) + m r \dot\alpha^2}{I_{eq}}
$$

## Control interface

Connect to the plant with `MachineClient(setup="ballandbeam_dt_nl_act_mg996r", ...)`.

### Signal mapping

| Symbol | Role | Command | Unit |
| --- | --- | --- | --- |
| - | reference | `machine_msg["ref"]` | m |
| $r$ | measurement | `machine_msg["meas"]` | m |
| $\theta_{cmd}$ | control command | `control_msg["control"]` | rad |

### KPI mapping

| Design requirement | KPI command | Unit |
| --- | --- | --- |
| Settling time | `machine_msg["kpis"]["settling_time_sec"]` | s |
| Overshoot | `machine_msg["kpis"]["overshoot_pct"]` | % |
