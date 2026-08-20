# Ball & Beam: System Modeling and Performance Specifications

## Physical setup

A ball is placed on a beam, where it is allowed to roll with 1 degree of freedom along the length of the beam. A lever arm is attached to the beam at one end and a servo gear at the other. As the servo gear turns by an angle $\theta$, the lever changes the angle of the beam by $\alpha$. When the angle is changed from the horizontal position, gravity causes the ball to roll along the beam. A controller will be designed for this system so that the ball's position can be manipulated.

## System parameters

For this problem, we will assume that the ball rolls without slipping and friction between the beam and ball is negligible. The constants and variables are defined as follows:

* (m)      mass of the ball              0.111 kg
* (R)      radius of the ball            0.015 m
* (d)      lever arm offset              0.03 m
* (g)      gravitational acceleration    9.8 m/s^2
* (L)      length of the beam            1.0 m
* (J)      ball's moment of inertia      9.99e-6 kg.m^2
* (r)      ball position coordinate	
* (alpha)  beam angle coordinate	
* (theta)  servo gear angle

## Sample time

The controller operates at a fixed sample period of $T_s = 0.02$ s (50 Hz). At each sample instant the plant provides a new measurement and expects a new control command.

## Design criteria

For step response:
* Settling time < 3 seconds
* Overshoot < 5%

## System equations

The second derivative of the input angle $\alpha$ actually affects the second derivative of $r$. However, we will ignore this contribution. The Lagrangian equation of motion for the ball is then given by the following:

$$ 0 = \left(\frac{J}{R^2}+m\right) \ddot{r} + m g \sin{\alpha} - m r \dot{\alpha}^2 $$

Linearization of this equation about the beam angle, $\alpha = 0$, gives us the following linear approximation of the system:

$$ \left(\frac{J}{R^2}+m\right) \ddot{r} = - m g \alpha $$ 

The equation which relates the beam angle to the angle of the gear can be approximated as linear by the equation below:

$$ \alpha = \frac{d}{L}\theta $$

Substituting this into the previous equation, we get:

$$ \left(\frac{J}{R^2}+m\right) \ddot{r} = - m g \frac{d}{L} \theta $$

## Control interface

Connect to the plant with `MachineClient(setup="ballandbeam_dt", ...)`.

### Signal mapping

| Symbol | Role | Command | Unit |
| --- | --- | --- | --- |
| - | reference | `machine_msg["ref"]` | m |
| $r$ | measurement | `machine_msg["meas"]` | m |
| $\theta$ | control command | `control_msg["control"]` | rad |

### KPI mapping

| Design requirement | KPI command | Unit |
| --- | --- | --- |
| Settling time | `machine_msg["kpis"]["settling_time_sec"]` | s |
| Overshoot | `machine_msg["kpis"]["overshoot_pct"]` | % |
