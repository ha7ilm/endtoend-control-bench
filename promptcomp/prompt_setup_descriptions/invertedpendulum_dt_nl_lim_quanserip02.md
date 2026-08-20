# Inverted Pendulum: System Modeling and Performance Specifications

The system consists of an inverted pendulum mounted to a motorized cart. An inverted pendulum is unstable without control, that is, the pendulum will simply fall over if the cart isn't moved to balance it. Additionally, the dynamics of the system are nonlinear. The objective of the control system is to balance the inverted pendulum by applying a force to the cart that the pendulum is attached to. A real-world example that relates directly to this inverted pendulum system is the attitude control of a booster rocket at takeoff.  

In this case we will consider a two-dimensional problem where the pendulum is constrained to move in the vertical plane. For this system, the control input is the force $F$ that moves the cart horizontally and the outputs are the angular position of the pendulum $\theta$ and the horizontal position of the cart $x$.

Let's assume the following quantities:

| Symbol | Value | Units | Description |
| --- | ---: | --- | --- |
| $M$ | 0.57 | kg | Cart mass |
| $m$ | 0.230 | kg | Pendulum mass |
| $b$ | 5.4 | N s/m | Cart viscous friction |
| $l$ | 0.3302 | m | Pivot to pendulum center of mass |
| $I$ | $7.88\times10^{-3}$ | kg m$^2$ | Pendulum inertia about center of mass |
| $g$ | 9.81 | m/s$^2$ | Gravitational acceleration |
| $F_{\max}$ | 13.44 | N | Actuator force magnitude limit |
| $dt$ | 0.01 | s | Controller sampling period |

## Performance specifications

In our case, the inverted pendulum system is single-input, multi-output (SIMO). We will attempt to control both the pendulum's angle and the cart's position. To make the design more challenging in this section, we will command a 0.2-meter step in the cart's desired position. Under these conditions, it is desired that the cart achieve its commanded position within 5 seconds and have a rise time under 0.8 seconds. It is also desired that the pendulum settle to its vertical position in under 5 seconds, and further, that the pendulum angle not travel more than 20 degrees (0.35 radians) away from the vertically upward position.

In summary, the design requirements for the inverted pendulum are: 

* Settling time for $x$ and $\theta$ of less than 5 seconds
* Rise time for $x$ of less than 0.8 seconds
* Pendulum angle $\theta$ never more than 20 degrees (0.35 radians) from
the vertical
* Steady-state error of less than 2% for $x$ and $\theta$

## Force analysis and system equations

This setup uses nonlinear cart-pendulum dynamics with a symmetric force-limited actuator.

## State, input, and outputs

- State vector: $s = [x,\ \dot x,\ \theta,\ \dot\theta]$
- Controller command: $u$ (requested cart force)
- Actuator output: $u_{act} = \mathrm{clip}(u,\ -F_{max},\ +F_{max})$
- Applied force (including disturbance): $F = u_{act} + d$
- Outputs: cart position $x$ and pendulum angle deviation $\phi$

Summing the forces in the horizontal direction, you get the following equation of motion.

$$ M\ddot{x}+b\dot{x}+N = F $$
 
Note that you can also sum the forces in the vertical direction for the cart, but no useful information would be gained.

Summing the forces in the horizontal direction, you get the following expression for the
reaction force $N$.

$$ N= m\ddot{x}+ml\ddot{\theta}\cos\theta-ml\dot{\theta}^2\sin\theta $$
 
If you substitute this equation into the first equation, you get one of the two governing equations for this system.

$$(M+m)\ddot{x}+b\dot{x}+ml\ddot{\theta}\cos\theta-ml\dot{\theta}^2\sin\theta=F $$

To get the second equation of motion for this system, sum the forces perpendicular to the pendulum. Solving the system along this axis greatly simplifies the mathematics. You should get the following equation.

$$P\sin\theta+N\cos\theta-mg\sin\theta=ml\ddot{\theta}+m\ddot{x}\cos\theta$$
 
To get rid of the $P$ and $N$ terms in the equation above, sum the moments about the centroid of the pendulum to get the following equation.

$$-Pl\sin\theta-Nl\cos\theta=I\ddot{\theta}$$
 
Combining these last two expressions, you get the second governing equation.
 
$$(I+ml^2)\ddot{\theta}+mgl\sin\theta=-ml\ddot{x}\cos\theta $$

The two acceleration equations are solved together at each simulation step, and the controller is updated every $dt = 0.01\ \mathrm{s}$.

## Control interface

Connect to the plant with `MachineClient(setup="invertedpendulum_dt_nl_lim_quanserip02", ...)`.

### Signal mapping

This is a SIMO system. The `ref` and `meas` channels carry dictionaries with keys `"x_cart"` and `"phi_angle"`.

| Symbol | Role | Command | Unit |
| --- | --- | --- | --- |
| - | cart position reference | `machine_msg["ref"]["x_cart"]` | m |
| - | pendulum angle reference | `machine_msg["ref"]["phi_angle"]` | rad |
| $x$ | cart position measurement | `machine_msg["meas"]["x_cart"]` | m |
| $\phi$ | pendulum angle measurement | `machine_msg["meas"]["phi_angle"]` | rad |
| $u$ | control command | `control_msg["control"]` | N |

**Naming note.** The equations above use $\theta$ measured from the downward vertical. The software interface exposes $\phi = \theta - \pi$ (deviation from upright) as `"phi_angle"`. The reference for `"phi_angle"` is always 0 (keep the pendulum upright).

### KPI mapping

**Cart** (`x_cart`):

| Design requirement | KPI command | Unit |
| --- | --- | --- |
| Settling time | `machine_msg["kpis"]["channels"]["x_cart"]["settling_time_sec"]` | s |
| Rise time | `machine_msg["kpis"]["channels"]["x_cart"]["rise_time_sec"]` | s |
| Steady-state error | `machine_msg["kpis"]["channels"]["x_cart"]["steady_state_error_pct"]` | % |

**Pendulum** (`phi_angle`):

| Design requirement | KPI command                                                              | Unit |
| ------------------ | ------------------------------------------------------------------------ | ---- |
| Settling time      | `machine_msg["kpis"]["channels"]["phi_angle"]["settling_time_sec"]`      | s    |
| Peak angle         | `machine_msg["kpis"]["channels"]["phi_angle"]["max_abs_rad"]`            | rad  |
| Steady-state error | `machine_msg["kpis"]["channels"]["phi_angle"]["steady_state_error_pct"]` | %    |
