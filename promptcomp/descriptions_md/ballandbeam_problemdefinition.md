# Ball & Beam: System Modeling and Performance Specifications

## Physical setup

A ball is placed on a beam, see figure below, where it is allowed to roll with 1 degree of freedom along the length of the beam. A lever arm is attached to the beam at one end and a servo gear at the other. As the servo gear turns by an angle $\theta$, the lever changes the angle of the beam by $\alpha$. When the angle is changed from the horizontal position, gravity causes the ball to roll along the beam. A controller will be designed for this system so that the ball's position can be manipulated.

## System parameters

For this problem, we will assume that the ball rolls without slipping and friction between the beam and ball is negligible. The constants and variables are defined as follows:

* (m)      mass of the ball              0.11 kg
* (R)      radius of the ball            0.015 m
* (d)      lever arm offset              0.03 m
* (g)      gravitational acceleration    9.8 m/s^2
* (L)      length of the beam            1.0 m
* (J)      ball's moment of inertia      9.99e-6 kg.m^2
* (r)      ball position coordinate	
* (alpha)  beam angle coordinate	
* (theta)  servo gear angle

## Design criteria

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

### Transfer function

Taking the Laplace transform of the equation above, the following equation is found:

$$ \left(\frac{J}{R^2}+m\right) R(s) s^2 = - m g \frac{d}{L} \Theta(s) $$

Rearranging we find the transfer function from the gear angle ($\Theta(s)$) to the ball position ($R(s)$).

$$ P(s) = \frac{R(s)}{\Theta(s)} = -\frac{mgd}{L \left(\frac{J}{R^2}+m\right)} \frac{1}{s^2} \qquad [ \frac{m}{rad} ]$$
