# `cruisecontrol_dt_lim_hondajazz` Addendum

In this task, you are designing a controller for the plant `cruisecontrol_dt_lim_hondajazz`, which differs from the linear plant described before, in the following ways.

Relative to the regular cruise baseline, the plant keeps the same first-order structure but changes physical mass to that of a Honda Jazz model, and adds asymmetric traction-force limits according to ISO standards on cruise control. 

## State, input, and output

- State: $x = [v]$
- Controller input command: $u$ (traction force command, N)
- Applied force: $u_{act}$
- Output: $y = v$

## Equations

Command limiting:

$$
u_{act} = \mathrm{clip}(u,\ F_{min},\ F_{max})
$$

Vehicle dynamics:

$$
m\dot v + b v = u_{act}
$$

or:

$$
\dot v = -\frac{b}{m}v + \frac{1}{m}u_{act}
$$

## Parameters for `cruisecontrol_dt_lim_hondajazz`

- $m = 1240\ \mathrm{kg}$
- $b = 50\ \mathrm{N\cdot s/m}$
- $F_{max} = 2480\ \mathrm{N}$
- $F_{min} = -4340\ \mathrm{N}$
- Sampling: $dt = 0.02\ \mathrm{s}$

## What changes versus the the linear plant described before

- Mass increases from $1000$ kg to $1240$ kg.
- Force is no longer unlimited; it is clipped to $[-4340,\ 2480]$ N.
- Limits are asymmetric: braking authority magnitude is larger than acceleration authority.
- Plant is linear only inside limits; with clipping it behaves as a constrained piecewise-linear system.

## Useful acceleration interpretation

At speed $v$, net acceleration is:

$$
a(v) = \frac{u_{act} - b v}{m}
$$

At $v=0$:

- Maximum acceleration: $2480/1240 = +2.0\ \mathrm{m/s^2}$
- Maximum deceleration command: $-4340/1240 = -3.5\ \mathrm{m/s^2}$

At higher speed, drag ($bv$) reduces positive acceleration and increases deceleration magnitude for fixed force limits.
