# Cruise Control: System Modeling and Performance Specifications

## Physical setup

Automatic *cruise control* is an excellent example of a feedback control system found in many modern vehicles. The purpose of the cruise control system is to maintain a constant vehicle speed despite external *disturbances*, such as changes in wind or road grade. This is accomplished by measuring the vehicle speed, comparing it to the desired or *reference* speed, and automatically adjusting the throttle according to a *control law*. We consider here a simple model of the vehicle dynamics.
The vehicle, of mass m, is acted on by a control force, u. The force u represents the force generated at the road/tire interface. 

For this simplified model we will assume that we can control this force directly and will neglect the dynamics of the powertrain, tires, etc., that go into generating the force. The resistive forces, bv, due to rolling resistance and wind drag, are assumed to vary linearly with the vehicle velocity, v, and act in the direction opposite the vehicle's motion.

## System equations

With these assumptions we are left with a first-order mass-damper system. Summing forces in the x-direction and applying Newton's 2nd law, we arrive at the following system equation:

$$ m \dot{v} + b v = u $$

Since we are interested in controlling the speed of the vehicle, the output equation is chosen as follows

$$ y = v $$

## System parameters

Let's assume that the parameters of the system are:

* (m)   vehicle mass          1000 kg
* (b)   damping coefficient   50 N.s/m

## State-space model

First-order systems have only a single energy storage mode, in this case the kinetic energy of the car, and therefore only one state variable is needed, the velocity. The state-space representation is therefore:

$$ \dot{\mathbf{x}}=[\dot{v}]=\left[\frac{-b}{m}\right][v]+\left[\frac{1}{m}\right][u] $$

$$ y=[1][v] $$

## Transfer function model

Taking the Laplace transform of the governing differential equation and assuming zero initial conditions, we find the transfer function of the cruise control system to be:

$$ P(s) = \frac{V(s)}{U(s)} = \frac{1}{ms+b}  \qquad  [ \frac{m/s}{N} ] $$

## Performance specifications

The next step is to come up with some *design criteria* that the compensated system should achieve. When the engine gives a 500 Newton force, the car will reach a maximum velocity of 10 m/s (22 mph). An automobile should be able to accelerate up to that speed in less than 5 seconds. In this application, a 10% overshoot and 2% steady-state error on the velocity are sufficient. Keeping the above in mind, we have proposed the following design criteria for this problem:

* Rise time < 5 s
* Overshoot < 10%
* Steady-state error < 2%
