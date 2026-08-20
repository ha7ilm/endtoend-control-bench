# Software definition: ballandbeam_dt_nl_act_mg996r

## Simulation configuration

| Parameter | Value |
| --- | --- |
| Sample period | 0.02 s |
| Simulation horizon | 5.0 s |
| Warmup samples | 2 (the step reference is applied after 2 sample instants) |
| Step reference | 0.25 m |

## Signal interface

| Channel | Display name | Unit |
| --- | --- | --- |
| `ref` | Ball position reference | m |
| `meas` | Measured ball position | m |
| `control` | Gear angle command | rad |

## KPIs

The following step-response KPIs are computed automatically:

- `overshoot_pct`
- `rise_time_sec`
- `settling_time_sec`
- `steady_state_error_pct`
- `settled_within_horizon`
- `simulation_horizon_sec`
