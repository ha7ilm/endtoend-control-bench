# Software definition: aircraftpitch_dt

## Simulation configuration

| Parameter | Value |
| --- | --- |
| Sample period | 0.01 s |
| Simulation horizon | 10.0 s |
| Warmup samples | 2 (the step reference is applied after 2 sample instants) |
| Step reference | 0.2 rad |

## Signal interface

| Channel | Display name | Unit |
| --- | --- | --- |
| `ref` | Pitch reference | rad |
| `meas` | Measured pitch angle | rad |
| `control` | Elevator deflection | rad |

## KPIs

The following step-response KPIs are computed automatically:

- `overshoot_pct`
- `rise_time_sec`
- `settling_time_sec`
- `steady_state_error_pct`
- `settled_within_horizon`
- `simulation_horizon_sec`
