# Architecture and protocol

## Components

The experiment separates controller generation/execution from plant simulation:

```text
agent workspace                         repository-side simulator

controller_N.py
  -> urletra.controlclient.MachineClient
  -> TCP 127.0.0.1:9000
                                        controlserver.server
                                          -> setup dynamics
                                          -> KPI calculation
                                          -> runN.npy persistence
  <- sample reference and measurement
  -> scalar control command
  <- final KPI payload
```

The installed distribution is `urletra-controlclient`. Its public surface is
`urletra.controlclient.MachineClient`. `controlserver` is intentionally a local
repository module rather than part of the installed public API.

## Agent boundary

The intended method gives an agent only:

- `problem_description.md` with plant equations, parameters, signal mapping,
  and requirements;
- `howto_for_control_loop_software.md` with the `MachineClient` API;
- permission to create controller scripts and local supporting files;
- network access to the simulator TCP endpoint.

The agent should not read `controlserver/`, other attempts, existing results, or handwritten example controllers. This prevents it from inspecting simulator internals or copying solutions. The paper environment used commands named `codexs` and `claudes`, which start the underlying tools inside Linux Bubblewrap. Sanitized definitions are provided in [Sandbox wrappers](sandbox-wrappers.md). The checked-in Codex template also requests CLI `workspace-write` sandboxing. The checked-in Claude template bypasses Claude Code permissions and therefore relies especially on the outer Bubblewrap boundary.

As of 2026 Q1, when the experiments were run, Codex's default host-level file visibility allowed it to inspect other files readable by the user. Claude Code's default behavior did not allow the same unrestricted reading outside the launched project. Explicit wrappers were nevertheless used for both tools to enforce one common experimental condition and ensure neither agent could search the simulator implementation or existing controller solutions.

For a faithful new run, use the documented wrappers or equivalent OS-, container-, or harness-level confinement whose only writable project path is the current attempt's `lwp/rlwp/`. It must still expose the Python interpreter/client installation, CLI runtime and credentials, and loopback TCP port 9000. Record the containment configuration alongside the result archive.

## Server lifecycle

Each generated automatic launcher:

1. resolves the Git repository root;
2. starts `python -m controlserver.server` in the repository root;
3. binds `127.0.0.1:9000` for one setup/case/attempt;
4. changes into the agent's `lwp/rlwp/` directory;
5. starts one agent and records its event stream;
6. uses an exit trap with `fuser -k 9000/tcp` to stop the server.

The server accepts multiple controller connections until it is stopped. One controller execution normally opens one connection and produces one simulation run. The server is single-session: it completes one connection before accepting the next.

The launch templates do not explicitly wait for server readiness. Agents normally spend enough time reading and writing the first controller for startup to complete, but an immediate custom client can race the server. See [Troubleshooting](troubleshooting.md#connection-refused).

## Run indexing

The server increments its connection counter immediately after `accept()` and uses `run_index = connection_count - 1`. A protocol error or controller crash after connection acceptance consumes that index without writing a `runN.npy`. Consequently run filenames can contain gaps and a later `controller_N.py` may not map to `run(N-1).npy`. The matching utility can recover an unambiguous shift of up to three positions using exact `why` metadata.

Do not restart a launcher in an existing attempt directory if clean provenance matters: a restarted server begins its connection counter at zero and can overwrite existing `run0.npy`, `run1.npy`, and so on.

## Wire framing

Messages are MessagePack maps prefixed by a four-byte, unsigned, big-endian payload length. Empty payloads and frames larger than 8 MiB are rejected. Canonical framing is implemented in `src/urletra/_common/protocol.py`; the server's `controlserver/protocol.py` is a compatibility import wrapper.
## Message sequence

### 1. Client hello

The client sends once after connecting:

```python
{
    "type": "client_hello",
    "setup": "motorspeed_dt",
    "description": "PI controller, Kp=..., Ki=...",
    "why": "Design to meet specifications: initial model-based design.",
}
```

`setup` must exactly equal the running server setup. All three text fields must
be strings; the server requires them to be non-empty after stripping.

### 2. Sample exchange

For each sample the server sends:

```python
{
    "type": "controller_input",
    "done": False,
    "ref": 1.0,        # scalar or a string-keyed map
    "meas": 0.42,      # scalar or a string-keyed map
}
```

The controller replies:

```python
{"type": "controller_output", "control": 2.5}
```

`MachineClient.write({"control": value})` adds the message type. Control must be scalar, numeric, and finite. Reference and measurement map layouts must not change within a run. Inverted-pendulum messages use `x_cart` and `phi_angle` channels; the controller output remains scalar.

### 3. Completion

After the last control sample, the server sends:

```python
{
    "type": "controller_input",
    "done": True,
    "kpis": {...},
}
```

When local logging is enabled, `MachineClient.read()` adds an `output_files` map after writing the response CSV and KPI JSON. No further controller output is sent for the completion message.

## Client configuration

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `URLETRA_MACHINE_HOST` | `127.0.0.1` | Simulator host; blank also selects the default |
| `URLETRA_MACHINE_PORT` | `9000` | Simulator port; invalid/blank values warn and fall back to 9000 |
| `URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES` | enabled | Exact value `0` disables client-side CSV/JSON logging; all other values enable it |

The socket timeout is 30 seconds. The server result is always written after a successful run; the last variable controls only client-side `run_outputs/`.

## Simulation determinism

For fixed source, setup, and controller outputs, the plant simulation and KPI calculation are deterministic. Each setup starts from the same initial state, uses a fixed sample period and horizon, and numerically integrates its continuous dynamics one sample at a time.

The overall benchmark is not deterministic because the agents generate and select controller programs without a seed or fixed stopping rule.
