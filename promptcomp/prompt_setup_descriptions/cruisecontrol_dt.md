# Cruise Control: System Modeling and Performance Specifications

## Physical setup

Automatic *cruise control* is an excellent example of a feedback control system found in many modern vehicles. The purpose of the cruise control system is to maintain a constant vehicle speed despite external *disturbances*, such as changes in wind or road grade. This is accomplished by measuring the vehicle speed, comparing it to the desired or *reference* speed, and automatically adjusting the throttle according to a *control law*. We consider here a simple model of the vehicle dynamics.
The vehicle, of mass $m$, is acted on by a control force, $u$. The force $u$ represents the force generated at the road/tire interface. 

For this simplified model we will assume that we can control this force directly and will neglect the dynamics of the powertrain, tires, etc., that go into generating the force. The resistive forces, $b \cdot v$, due to rolling resistance and wind drag, are assumed to vary linearly with the vehicle velocity, $v$, and act in the direction opposite the vehicle's motion.

## Sample time

The controller operates at a fixed sample period of $T_s = 0.02$ s (50 Hz). At each sample instant the plant provides a new measurement and expects a new control command.

## System equations

With these assumptions we are left with a first-order mass-damper system. Summing forces in the x-direction and applying Newton's 2nd law, we arrive at the following system equation:

$$ m \dot{v} + b v = u $$

Since we are interested in controlling the speed of the vehicle, the output equation is chosen as follows

$$ y = v $$

## System parameters

Let's assume that the parameters of the system are:

* $m$:   vehicle mass          1000 kg
* $b$ :  damping coefficient   50 N.s/m

## Performance specifications

The next step is to come up with some *design criteria* that the compensated system should achieve. When the engine gives a 500 Newton force, the car will reach a steady-state velocity of 10 m/s (22 mph). An automobile should be able to accelerate up to that speed in less than 5 seconds. In this application, a 10% overshoot and 2% steady-state error on the velocity are sufficient. Keeping the above in mind, we have proposed the following design criteria for this problem:

* Rise time < 5 s
* Overshoot < 10%
* Steady-state error < 2%

## Control interface

Connect to the plant with `MachineClient(setup="cruisecontrol_dt", ...)`.

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
