## Physical setup

Automatic *cruise control* is an excellent example of a feedback control system found in many modern vehicles. The purpose of the cruise control system is to maintain a constant vehicle speed despite external *disturbances*, such as changes in wind or road grade. This is accomplished by measuring the vehicle speed, comparing it to the desired or *reference* speed, and automatically adjusting the throttle according to a *control law*. We consider here a simple model of the vehicle dynamics.
The vehicle, of mass $m$, is acted on by a control force, $u$. The force $u$ represents the force generated at the road/tire interface. 

For this simplified model we will assume that we can control this force directly and will neglect the dynamics of the powertrain, tires, etc., that go into generating the force. The resistive forces, $b \cdot v$, due to rolling resistance and wind drag, are assumed to vary linearly with the vehicle velocity, $v$, and act in the direction opposite the vehicle's motion.

## System equations

The controller sends a traction-force command $u$, and the plant applies a clipped force $u_{act}$:

$$
u_{act} = \mathrm{clip}(u,\ F_{min},\ F_{max})
$$

The vehicle speed dynamics are:

$$
m \dot{v} + b v = u_{act}
$$

or equivalently:

$$
\dot v = -\frac{b}{m}v + \frac{1}{m}u_{act}
$$

The measured output is speed:

$$
y = v
$$

## System parameters

Use the following parameters:

- $m = 1240\ \mathrm{kg}$
- $b = 50\ \mathrm{N\cdot s/m}$
- $F_{max} = 2480\ \mathrm{N}$
- $F_{min} = -4340\ \mathrm{N}$
- Sampling time: $dt = 0.02\ \mathrm{s}$

## Input limits and operating behavior

- Positive traction is limited to $2480\ \mathrm{N}$.
- Braking command is limited to $-4340\ \mathrm{N}$.
- Limits are asymmetric: braking authority magnitude is larger than acceleration authority.

## Performance specifications

Use the following design criteria for the closed-loop speed step response:

* Rise time < 5 s
* Overshoot < 10%
* Steady-state error < 2%

## Acceleration interpretation

At speed $v$, net acceleration is:

$$
a(v) = \frac{u_{act} - b v}{m}
$$

At $v=0$:

- Maximum acceleration: $2480/1240 = +2.0\ \mathrm{m/s^2}$
- Maximum deceleration command: $-4340/1240 = -3.5\ \mathrm{m/s^2}$

At higher speed, drag ($bv$) reduces positive acceleration and increases deceleration magnitude for fixed force limits.

## Control interface

Connect to the plant with `MachineClient(setup="cruisecontrol_dt_lim_hondajazz", ...)`.

### Signal mapping

| Symbol | Role | Command | Unit |
| --- | --- | --- | --- |
| - | reference | `machine_msg["ref"]` | m/s |
| $v$ | measurement | `machine_msg["meas"]` | m/s |
| $u$ | control command | `control_msg["control"]` | N |

### KPI mapping

| Design requirement | KPI command | Unit |
| --- | --- | --- |
| Rise time | `machine_msg["kpis"]["rise_time_sec"]` | s |
| Overshoot | `machine_msg["kpis"]["overshoot_pct"]` | % |
| Steady-state error | `machine_msg["kpis"]["steady_state_error_pct"]` | % |
