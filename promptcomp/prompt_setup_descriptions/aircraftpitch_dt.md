# Aircraft Pitch: System Modeling and Performance Specifications

## Physical setup and system equations

The equations governing the motion of an aircraft are a very complicated set of six nonlinear coupled differential equations. However, under certain assumptions, they can be decoupled and linearized into longitudinal and lateral equations. Aircraft pitch is governed by the longitudinal dynamics. In this project we will design an autopilot that controls the pitch of an aircraft. We will assume that the aircraft is in steady-cruise at constant altitude and velocity; thus, the thrust, drag, weight and lift forces balance each other in the _x_- and _y_-directions. We will also assume that a change in pitch angle will not change the speed of the aircraft under any circumstance (unrealistic but simplifies the problem a bit). Under these assumptions, the longitudinal equations of motion for the aircraft can be written as follows. 

$$ \dot{\alpha} = \mu\Omega\sigma [-(C_L+C_D)\alpha+\frac{1}{(\mu-C_L)}q-(C_W \sin\gamma)\theta+C_L] $$

$$ \dot{q}=\frac{\mu \Omega}{2 i_{y y}}\left[\left[C_M-\eta\left(C_L+C_D\right)\right] \alpha+\left[C_M+\sigma C_M\left(1-\mu C_L\right)\right] q+\left(\eta C_W \sin \gamma\right) \delta\right] $$                                                          

$$ \dot\theta = \Omega q $$

A further explanation of what each variable represents:

* $\alpha$ = Angle of attack.
* $q$ = Pitch rate.
* $\theta$ = Pitch angle.
* $\delta$ = Elevator deflection angle.
* $\mu = \frac{\rho S \bar{c}}{4 m}$.
* $\rho$ = Density of air.
* $S$ = Platform area of the wing.
* $\bar{c}$ = Average chord length.
* $m$ = Mass of the aircraft.
* $\Omega = \frac{2 U}{\bar{c}}$.
* $U$ = Equilibrium flight speed.
* $C_T$ = Coefficient of thrust.
* $C_D$ = Coefficient of drag.
* $C_L$ = Coefficient of lift.
* $C_W$ = Coefficient of weight.
* $C_M$ = Coefficient of pitch moment.
* $\gamma$ = Flight path angle.
* $\sigma=\frac{1}{1+\mu C_L}$ = Constant. 
* $i_{yy}$ = Normalized moment of inertia.
* $\eta=\mu \sigma C_M$ = Constant.

For this system, the input will be the elevator deflection angle $\delta$ and the output will be the pitch angle $\theta$ of the aircraft.

## Sample time

The controller operates at a fixed sample period of $T_s = 0.01$ s (100 Hz). At each sample instant the plant provides a new measurement and expects a new control command.

## Modeling equations with numerical values

Before finding the transfer function and state-space models, let's plug in the numerical values to simplify the modeling equations shown above:

$$\dot\alpha = -0.313\alpha+56.7q+0.232\delta $$

$$\dot q = -0.0139\alpha-0.426q+0.0203\delta $$

$$\dot\theta = 56.7q $$

## Design requirements

The next step is to choose some design criteria. In this project we will design a feedback controller so that in response to a step command of pitch angle the actual pitch angle overshoots less than 10%, has a rise time of less than 2 seconds, a settling time of less than 10 seconds, and a steady-state error of less than 2%. For example, if the reference is 0.2 radians (11.5 degrees), then the pitch angle will not exceed approximately 0.22 rad, will rise from 0.02 rad to 0.18 rad within 2 seconds, will settle to within 2% of its steady-state value within 10 seconds, and will settle between 0.196 and 0.204 radians in steady-state. 

In summary, the design requirements are the following.

* Overshoot less than 10%
* Rise time less than 2 seconds
* Settling time less than 10 seconds
* Steady-state error less than 2%

## Control interface

Connect to the plant with `MachineClient(setup="aircraftpitch_dt", ...)`.

### Signal mapping

| Symbol | Role | Command | Unit |
| --- | --- | --- | --- |
| - | reference | `machine_msg["ref"]` | rad |
| $\theta$ | measurement | `machine_msg["meas"]` | rad |
| $\delta$ | control command | `control_msg["control"]` | rad |

### KPI mapping

| Design requirement | KPI command | Unit |
| --- | --- | --- |
| Overshoot | `machine_msg["kpis"]["overshoot_pct"]` | % |
| Rise time | `machine_msg["kpis"]["rise_time_sec"]` | s |
| Settling time | `machine_msg["kpis"]["settling_time_sec"]` | s |
| Steady-state error | `machine_msg["kpis"]["steady_state_error_pct"]` | % |
