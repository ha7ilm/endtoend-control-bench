# Troubleshooting reproduction runs

Run diagnostics from the repository root unless a section says otherwise.

## `prepdirs.py` says it did nothing

**Message:** `results/current_run/wp already exists; prepdirs did nothing.`

This is intentional protection against overwriting attempts. Inspect the tree:

```bash
find results/current_run/wp -maxdepth 4 -type d | sort | sed -n '1,120p'
```

Use a clean result root for a new experiment. If the existing tree is an incomplete run you want to preserve, move the whole `results/current_run/` directory to a clearly named archive before generating new workspaces. Use `--onlynew` only when adding missing attempt directories to the same experiment; it also rewrites `run_all_auto.sh` to include only newly created attempts.

Avoid `orchexp/reprepdirs` unless deletion of the current workspace tree is explicitly intended.

## `codexs` or `claudes`: command not found

These are the experiment's Bubblewrap launcher names and are not installed by the Python package. Confirm the official tools exist:

```bash
command -v codex
command -v claude
```

Then install the sanitized definitions from [Sandbox wrappers](sandbox-wrappers.md), or implement and archive equivalent isolation wrappers. Do not use direct aliases for a reproduction: they remove the information boundary that prevents agents from reading simulator code and existing solutions. Shell aliases are also unreliable because generated launch scripts run non-interactively.

## Authentication or model-not-found errors

Run each official CLI directly and complete its login flow. Confirm the exact paper model names are still available to the account. Hosted model aliases and entitlements change over time; if a provider retires a model, use a dated model snapshot if offered or report the replacement model as a new benchmark rather than an exact reproduction.

Inspect the raw event stream under the attempt's `.codex/` or `.claude/` directory. Provider errors may not appear in the simulator log because the agent failed before connecting.

## Port 9000 is already in use

Identify the owner before stopping anything:

```bash
fuser -v 9000/tcp
```

Paper launchers assume exclusive use of port 9000 and kill its listener on exit. Do not run the generated attempts concurrently on that port. If another application owns it, stop that application.

## Server reports a setup mismatch

The controller's `MachineClient(setup="...")` string differs from the server's `--setup`. Compare the rendered `problem_description.md`, the controller source, and the generated launcher's `--setup` value. Names are exact and case-sensitive.

## Controller run hangs or times out

The `MachineClient` socket timeout is 30 seconds. Common causes are:

- the controller read one sample but failed to send a finite `control` value;
- the controller crashed inside its feedback loop;
- it sent the wrong protocol message type;
- a high-rate setup performs too much computation between samples;
- the server process exited and the client is waiting on a broken session.

Inspect both the agent transcript and matching server log. Run the relevant
`controller_N.py` manually against a fresh debug server to get an uncropped
traceback. A controller must call `read()`, check `done`, and otherwise call
`write({"control": finite_scalar})` once per sample.

## `Session failed` in a server log

Typical messages and meanings:

| Message fragment                                 | Likely cause                                         |
| ------------------------------------------------ | ---------------------------------------------------- |
| `First message must have type='client_hello'`    | client did not use `MachineClient` protocol          |
| `setup ... does not match server setup`          | wrong controller setup identifier                    |
| `Controller output missing 'control'`            | write payload omitted the scalar command             |
| `must be finite`                                 | NaN or infinity in controller output/signal          |
| `Connection closed while reading protocol frame` | controller process crashed or exited early           |
| `signal type changed` / `keys changed`           | malformed custom client or inconsistent setup output |
