# Software definition: invertedpendulum_dt

## Simulation configuration

| Parameter | Value |
| --- | --- |
| Sample period | 0.01 s |
| Simulation horizon | 5.0 s |
| Warmup samples | 2 (the step reference is applied after 2 sample instants) |
| Step reference | 0.2 m (cart position) |

## Signal interface

This is a SIMO (single-input, multi-output) system. The reference and measurement channels carry dictionaries with keys `"x_cart"` and `"phi_angle"`, not scalar values.

| Channel | Display name | Unit | Dict keys |
| --- | --- | --- | --- |
| `ref` | Cart/Pendulum reference | mixed | `"x_cart"` (m), `"phi_angle"` (rad) |
| `meas` | Cart/Pendulum measurement | mixed | `"x_cart"` (m), `"phi_angle"` (rad) |
| `control` | Cart force | N | — |

### Naming note

The description document uses $\theta$ for the pendulum angle measured from the downward vertical (CTMS textbook convention). The software interface exposes $\phi = \theta - \pi$ (deviation from upright) as **`"phi_angle"`**. Controllers must read and write `"phi_angle"`. The reference for `"phi_angle"` is always 0 (keep the pendulum upright).

## KPIs

Separate KPIs are computed for the cart (`x_cart`) and pendulum (`phi_angle`) channels:

**Cart KPIs** (standard step-response metrics on the `"x_cart"` channel):
- `overshoot_pct`
- `rise_time_sec`
- `settling_time_sec`
- `steady_state_error_pct`
- `settled_within_horizon`
- `simulation_horizon_sec`

**Pendulum KPIs** (regulation metrics on the `"phi_angle"` channel):
- `overshoot_pct`
- `settling_time_sec`
- `steady_state_error_pct`
- `settled_within_horizon`
- `max_abs_rad` — peak absolute pendulum angle during the run
