# Software definition: cruisecontrol_dt_lim_hondajazz

## Simulation configuration

| Parameter | Value |
| --- | --- |
| Sample period | 0.02 s |
| Simulation horizon | 10.0 s |
| Warmup samples | 2 (the step reference is applied after 2 sample instants) |
| Step reference | 10.0 m/s |

## Signal interface

| Channel | Display name | Unit |
| --- | --- | --- |
| `ref` | Speed reference | m/s |
| `meas` | Measured speed | m/s |
| `control` | Traction force | N |

## KPIs

The following step-response KPIs are computed automatically:

- `overshoot_pct`
- `rise_time_sec`
- `settling_time_sec`
- `steady_state_error_pct`
- `settled_within_horizon`
- `simulation_horizon_sec`
