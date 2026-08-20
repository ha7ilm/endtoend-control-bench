# Software definition: motorspeed_dt

## Simulation configuration

| Parameter | Value |
| --- | --- |
| Sample period | 0.05 s |
| Simulation horizon | 8.0 s |
| Warmup samples | 2 (the step reference is applied after 2 sample instants) |
| Step reference | 1.0 rad/sec |

## Signal interface

| Channel | Display name | Unit |
| --- | --- | --- |
| `ref` | Speed reference | rad/sec |
| `meas` | Measured speed | rad/sec |
| `control` | Armature voltage | V |

## KPIs

The following step-response KPIs are computed automatically:

- `overshoot_pct`
- `rise_time_sec`
- `settling_time_sec`
- `steady_state_error_pct`
- `settled_within_horizon`
- `simulation_horizon_sec`
