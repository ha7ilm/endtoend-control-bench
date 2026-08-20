# Suspension: System Modeling and Performance Specifications

## Physical setup

Designing an automotive suspension system is an interesting and challenging control problem. When the suspension system is designed, a 1/4 model (one of the four wheels) is used to simplify the problem to a 1-D multiple spring-damper system. We are considering an active suspension system where an actuator is included that is able to generate the control force U to control the motion of a bus body.

## System parameters

* (M1)    1/4 bus body mass                        2500 kg
* (M2)    suspension mass                          320 kg
---- 
* (K1)    spring constant of suspension system     80,000 N/m
* (K2)    spring constant of wheel and tire        500,000 N/m
* (b1)    damping constant of suspension system    350 N.s/m
----
* (b2)    damping constant of wheel and tire       15,020 N.s/m
* (U)     control force

## Equations of motion

From Newton's law, we can obtain the dynamic equations as the following:

$$ M_1 \ddot{X}_1 = - b_1 (\dot{X}_1 - \dot{X}_2) - K_1 (X_1 - X_2) + U $$

$$ M_2 \ddot{X}_2 = b_1 (\dot{X}_1 - \dot{X}_2) + K_1 (X_1 - X_2) + b_2 (\dot{W} - \dot{X}_2) + K_2 (W - X_2) - U$$

## Transfer function models

Assume that all of the initial conditions are zero, so that these equations represent the situation where the vehicle wheel goes up a bump. The dynamic equations above can be expressed in the form of transfer functions by taking the Laplace Transform. The specific derivation from the above equations to the transfer functions G1(s) and G2(s) is shown below where each transfer function has an output of, X1-X2, and inputs of U and W, respectively.

$$ (M_1 s^2 + b_1 s + K_1) X_1(s) - (b_1 s + K_1) X_2(s) = U(s) $$

$$ -(b_1 s + K_1) X_1(s) + (M_2 s^2 + (b_1 + b_2) s + (K_1 + K_2)) X_2(s) = (b_2 s + K_2) W(s) - U(s)$$

$$ \left[{\begin{array}{cc}(M_1 s^2 + b_1 s + K_1)& -(b_1 s + K_1)\\  -(b_1 s + K_1)& (M_2 s^2 + (b_1 + b_2) s + (K_1 + K_2))\end{array}}\right]  \left[{\begin{array}{c}X_1(s)\\X_2(s)\end{array}}\right] =  \left[{\begin{array}{c}U(s)\\(b_2 s + K_2) W(s) - U(s)\end{array}}\right] $$

$$ A = \left[{\begin{array}{cc}(M_1 s^2 + b_1 s + K_1)& -(b_1 s + K_1)\\  -(b_1 s + K_1)& (M_2 s^2 + (b_1 + b_2) s + (K_1 + K_2))\end{array}}\right]  $$

$$ \Delta = \mathrm{det} \left[{\begin{array}{cc}(M_1 s^2 + b_1 s + K_1)& -(b_1 s + K_1)\\  -(b_1 s + K_1)& (M_2 s^2 + (b_1 + b_2) s + (K_1 + K_2))\end{array}}\right]  $$

or 

$$ \Delta = (M_1 s^2 + b_1 s + K_1) \cdot (M_2 s^2 + (b_1 + b_2) s + (K_1 + K_2)) - (b_1 s + K_1) \cdot (b_1 s + K_1) $$

Find the inverse of matrix A and then multiply with inputs U(s)and W(s) on the righthand side as follows:

$$ \left[{\begin{array}{c}X_1(s)\\X_2(s)\end{array}}\right] = \frac{1}{\Delta} \left[{\begin{array}{cc}(M_2 s^2 + (b_1 + b_2) s + (K_1 + K_2))&(b_1 s + K_1)\\  (b_1 s + K_1)& (M_1 s^2 + b_1 s + K_1)\end{array}}\right] \left[{\begin{array}{c}U(s)\\(b_2 s + K_2) W(s) - U(s)\end{array}}\right] $$

$$ \left[{\begin{array}{c}X_1(s)\\X_2(s)\end{array}}\right] = \frac{1}{\Delta} \left[{\begin{array}{cc}(M_2 s^2 + b_2 s + K_2)& (b_1 b_2 s^2 + (b_1 K_2 + b_2 K_1) s + K_1 K_2) \\  -M_1 s^2& (M_1 b_2 s^3 + (M_1 K_2 + b_1 b_2) s^2 +(b_1 K_2 + b_2 K_1) s + K_1 K_2) \end{array}}\right] \left[{\begin{array}{c}U(s)\\W(s)\end{array}}\right] $$

When we want to consider the control input U(s) only, we set W(s) = 0. Thus we get the transfer function G1(s) as in the following: 

$$ G_1(s) = \frac{X_1(s) - X_2(s)}{U(s)} = \frac{(M_1+M_2) s^2 + b_2 s + K_2}{\Delta} $$

When we want to consider the disturbance input W(s) only, we set U(s) = 0.
Thus we get the transfer function G2(s) as in the following:

$$ G_2(s) = \frac{X_1(s) - X_2(s)}{W(s)} = \frac{-M_1 b_2 s^3 -M_1 K_2 s^2}{\Delta} $$

## Design requirements

A good bus suspension system should have satisfactory road holding ability, while still providing comfort when riding over bumps and holes in the road. When the bus is experiencing any road disturbance (i.e. pot holes, cracks, and uneven pavement),the bus body should not have large oscillations, and the oscillations should dissipate quickly. Since the distance X1-W is very difficult to measure, and the deformation of the tire (X2-W) is negligible, we will use the distance X1-X2 instead of X1-W as the output in our problem. Keep in mind that this is an approximation. The road disturbance (W) in this problem will be simulated by a step input. This step could represent the bus coming out of a pothole. We want to design a feedback controller so that the output (X1-X2) has an overshoot less than 5% and a settling time shorter than 5 seconds. For example, when the bus runs onto a 10-cm step, the bus body will oscillate within a range of +/- 5 mm and return to a smooth ride within 5 seconds.
