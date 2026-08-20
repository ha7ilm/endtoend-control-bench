# `ballandbeam_dt_nl_act_mg996r` Addendum

In this task, you are designing a controller for the plant `ballandbeam_dt_nl_act_mg996r`, which differs from the linear plant described before, in the following ways.

Regular linear baseline uses a 2-state linear plant with direct input-to-acceleration mapping:

$$
\ddot r = -\frac{m g d}{L\left(\frac{J}{R^2}+m\right)} \, \theta
$$

`ballandbeam_dt_nl_act_mg996r` replaces that with a nonlinear ball-beam model plus an explicit servo actuator state.

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

## Parameters used in `ballandbeam_dt_nl_act_mg996r`

- Ball/beam core: $m=0.111$, $R=0.015$, $J=9.99\times10^{-6}$, $g=-9.8$
- Geometry override: $d=0.035$, $L=0.5$ (so $d/L=0.07$)
- Actuator lag: $\tau = 0.12\ \mathrm{s}$
- Actuator position limit: $\theta_{max} = 1.0471975511965976\ \mathrm{rad}$ (about $\pm 60^\circ$)
- Actuator rate limit: $\dot\theta_{max} = 6.0\ \mathrm{rad/s}$
- Sampling: $dt = 0.02\ \mathrm{s}$

## What changes most versus the regular linear setup

- Nonlinear gravity term: $\sin(\alpha)$ replaces the small-angle linearization.
- Additional nonlinear coupling: $m r \dot\alpha^2$ appears in acceleration.
- Actuator is no longer instantaneous: command passes through lag, position clamp, and slew-rate clamp.
- State dimension increases from 2 to 3 (physical servo angle is dynamic).
- Geometry gain changes from $d/L=0.03$ (baseline) to $0.07$, increasing beam-angle sensitivity per servo angle command.
