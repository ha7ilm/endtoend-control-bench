# How to Use the Control Client in a Feedback Loop

`urletra-controlclient` is already installed and available as `urletra.controlclient`.

## API surface

Use `MachineClient` to connect to the machine to be feedback controlled.

- Constructor: `MachineClient(setup: str, description: str, why: str)`
	- `setup`: needs to match the name given in the problem definition.
	- `description`: a short, max. one-sentence description of the controller that you are implementing, e.g., what type is it, what are the parameters (if there's not more than 3 parameters). 
	- `why`: a description of the reason why this controller is implemented, and what are the differences between this and the last run. 
- `read() -> dict`: blocks until one controller input message arrives.
- `write({"control": ...})`: sends one controller output message.

`read()` returns a dictionary with at least:
- `done`: `False` during loop steps, `True` on the final message
- `ref`: reference signal (scalar or signal map)
- `meas`: measured signal (scalar or signal map)

When `done` is `True`, the final message contains:
- `kpis`: run KPIs from the server
- `output_files`: paths of generated run output files.

## Generic feedback-loop skeleton

```python
from urletra.controlclient import MachineClient


def compute_control(ref, meas):
    # Insert your custom controller logic here.
    # Return a scalar control command.
    raise NotImplementedError


with MachineClient(
    setup="<setup name>",
    description="<short controller summary>",
    why="<design rationale>",
) as machine:
    while True:
        machine_msg = machine.read()

        if machine_msg["done"]:
            kpis = machine_msg["kpis"]
            output_files = machine_msg.get("output_files", {})
            print("KPIs:", kpis)
            print("Output files:", output_files)
            break

        control_value = compute_control(
            ref=machine_msg["ref"],
            meas=machine_msg["meas"],
        )
		
		control_msg = {"control": control_value}
        machine.write(control_msg)
```

## Run output files

For each completed run, the client writes two files relative to the current working directory:

- `run_outputs/run_response_timeseries_<timestamp>.csv`
- `run_outputs/run_kpis_<timestamp>.json`

The CSV contains time-series controller I/O (`step_index`, references, measurements, control).  
The JSON contains the final KPI payload.
