# `motorspeed_dt_lim_maxonre30` Addendum

In this task, you are designing a controller for the plant `motorspeed_dt_lim_maxonre30`, which differs from the linear plant described before, in the following ways.

Compared with the regular motor-speed baseline, this setup keeps the same 2-state DC motor structure but changes motor constants to a Maxon RE 30-based parameterization, adds a wider but finite voltage limit, and uses much faster sampling.

## State, input, and output

- State: $x = [\omega,\ i]$
- Commanded input: $v_{cmd}$ (armature voltage command)
- Applied voltage: $v_{act}$
- Output: $y = \omega$

## Equations

Voltage limit:

$$
v_{act} = \mathrm{clip}(v_{cmd},\ -V_{max},\ +V_{max})
$$

Motor dynamics:

$$
\dot\omega = -\frac{b}{J}\omega + \frac{K}{J}i
$$

$$
\dot i = -\frac{K}{L}\omega - \frac{R}{L}i + \frac{1}{L}v_{act}
$$

## Parameters for `motorspeed_dt_lim_maxonre30`

- $J = 8.331\times10^{-5}\ \mathrm{kg\cdot m^2}$ (rotor + reflected payload inertia)
- $b = 4.6899385838143515\times10^{-6}\ \mathrm{N\cdot m\cdot s/rad}$
- $K = 0.0398\ \mathrm{N\cdot m/A}$
- $R = 1.43\ \Omega$
- $L = 0.281\times10^{-3}\ \mathrm{H}$
- $V_{max} = 36\ \mathrm{V}$
- Sampling: $dt = 0.001\ \mathrm{s}$, horizon $5.0\ \mathrm{s}$

## What changes versus the linear plant described before

- Same model order and equations, but very different parameter magnitudes.
- Voltage is constrained to $\pm 36$ V (baseline `motorspeed_dt` has no voltage clamp).
- Sample time changes from $0.05$ s to $0.001$ s.
- Mechanical and electrical time scales are much faster.
