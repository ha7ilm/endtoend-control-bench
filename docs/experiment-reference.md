# Experiment reference

## Sweep dimensions

The paper's sweep is all the combinations over: 

| Dimension | Values |
| --- | --- |
| Setup | 9 setup identifiers listed below |
| Prompt | `customctlchoice` |
| Agent/model | `codex53xhigh`, `opus46high` |
| Attempt | `0`, `1`, `2` |

`orchexp/prepdirs.py` contains these registries as `SETUPS`, `PROMPTS`, and
`MODELS`. The case/experiment identifier is `<prompt>_<model>`, for example
`customctlchoice_codex53xhigh`.

## Setup and KPI matrix

All comparisons are strict (`value < limit`), not inclusive. `dt`, horizon, and
reference values come from `controlserver/setup_variants.py`. Feasibility and
objective formulas come from `dashes/parse_kpis.py` and mirror the rendered
problem descriptions.

| Setup identifier | Kind | `dt` (s) | Horizon (s) | Step reference | Feasibility constraints | Tuning objective |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `aircraftpitch_dt` | CTMS | 0.01 | 10 | 0.2 rad | overshoot < 10%; rise < 2 s; settling < 10 s; SSE < 2% | overshoot + 3 settling |
| `ballandbeam_dt` | CTMS | 0.02 | 5 | 0.25 m | settling < 3 s; overshoot < 5% | overshoot + 3 settling |
| `ballandbeam_dt_nl_act_mg996r` | realistic | 0.02 | 5 | 0.25 m | settling < 3 s; overshoot < 8% | overshoot + 3 settling |
| `cruisecontrol_dt` | CTMS | 0.02 | 10 | 10 m/s | rise < 5 s; overshoot < 10%; SSE < 2% | overshoot + 2 rise |
| `cruisecontrol_dt_lim_hondajazz` | realistic | 0.02 | 10 | 10 m/s | rise < 5 s; overshoot < 10%; SSE < 2% | overshoot + 2 rise |
| `invertedpendulum_dt` | CTMS | 0.01 | 5 | 0.2 m cart | cart settling < 5 s; angle settling < 5 s; cart rise < 0.5 s; max angle < 0.35 rad; cart and angle SSE < 2% | cart settling + 2 cart SSE + angle settling + 2 angle SSE |
| `invertedpendulum_dt_nl_lim_quanserip02` | realistic | 0.01 | 5 | 0.2 m cart | as above, with cart rise < 0.8 s | same inverted-pendulum objective |
| `motorspeed_dt` | CTMS | 0.05 | 8 | 1 rad/s | settling < 2 s; overshoot < 5%; SSE < 1% | overshoot + 3 settling |
| `motorspeed_dt_lim_maxonre30` | realistic | 0.001 | 5 | 100 rad/s | settling < 0.5 s; overshoot < 5%; SSE < 1% | overshoot + 3 settling |

Here “SSE” is steady-state error in percent. Objective terms use the numeric values as returned by the KPI payload, so percent terms are not divided by 100. Missing or non-finite objective terms produce an infinite objective and missing or non-finite constraint values fail feasibility.

The simulator inserts two warm-up samples before the reference step in all nine paper setups. Standard KPI semantics are:

- overshoot relative to the commanded transition;
- 10%-to-90% rise time;
- settling inside a 2% target band for the remainder of the horizon;
- final-sample absolute steady-state error as a percentage of the target scale.

The inverted-pendulum setup overrides KPI computation to return separate `x_cart` and `phi_angle` channels, the other setups use just a single channel.

## Realistic variants

- `motorspeed_dt_lim_maxonre30` models a Maxon RE 30 36 V winding plus payload
  inertia and clips armature voltage to +/-36 V.
- `ballandbeam_dt_nl_act_mg996r` uses nonlinear ball/beam dynamics, a shorter
  beam, and a first-order, position/rate-limited MG996R-like actuator.
- `cruisecontrol_dt_lim_hondajazz` uses a 1,240 kg vehicle and clips traction
  force to `[-4340, 2480]` N.
- `invertedpendulum_dt_nl_lim_quanserip02` uses nonlinear Quanser IP02-like
  dynamics and clips the cart force to approximately +/-13.44 N.

The detailed equations and parameters visible to agents are the Markdown files under `promptcomp/prompt_setup_descriptions/`. The simulator's actual implementation remains under `controlserver/` and should not be visible inside an agent workspace.

## Agent configurations

| ID | Paper label | Template invocation |
| --- | --- | --- |
| `codex53xhigh` | GPT-5.3 Codex (xhigh) | `codexs exec --model gpt-5.3-codex --config model_reasoning_effort="xhigh" --sandbox workspace-write --config sandbox_workspace_write.network_access="true" --skip-git-repo-check --json` |
| `opus46high` | Claude Opus 4.6 | `claudes -p --verbose --model opus --dangerously-skip-permissions --disallowedTools "Bash(rm:*),Bash(curl:*),Bash(git:*),WebFetch,WebSearch" --output-format stream-json` |

`codexs` and `claudes` apply the experiment's Bubblewrap confinement before starting the underlying CLI; sanitized definitions are in [Sandbox wrappers](sandbox-wrappers.md). Claude automatic runs also set `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`. Both launch templates pipe the rendered `prompt.md` on standard input and save the streamed machine-readable transcript beneath `.codex/` or `.claude/` in the agent workspace.

## Prompt contract

`promptcomp/prompt_direct_commands/customctlchoice/prompt.md` defines three
phases:

1. analyze the supplied plant equations, choose a controller structure, and evaluate successive `controller_N.py` scripts until specifications are met;
2. tune further against the setup-specific objective;
3. write `best.txt` containing exactly one `controller_N.py` filename and write
   `summary.md`.

During design, the `MachineClient(..., why=...)` field must start with `Design to meet specifications: `. During tuning it must start with `Tuning: `. Analysis uses these prefixes to identify the design/tuning boundary. The `description` field is intended to be a one-sentence controller summary.

No controller family, iteration cap, time budget, or objective threshold is specified.

## Workspace generation

`python -m orchexp.prepdirs --attempts 3` performs the following for each of the 54 attempts:

- creates `results/current_run/wp/<setup>/<case>/attemptN/lwp/rlwp/`;
- copies the public client instructions as `lwp/rlwp/howto_for_control_loop_software.md`;
- copies the selected setup description as `lwp/rlwp/problem_description.md`;
- resolves setup-conditional `%{setup-list: text}%` blocks in `prompt.md`;
- substitutes `%SETUP%`, `%CASE%`, and `%ATTEMPT%` in launch templates;
- creates executable `start_llm_auto.sh` and `start_llm_interactive.sh` files;
- creates a sequential `results/current_run/wp/run_all_auto.sh`.

Behavior around existing data is deliberate:

- if `wp/` exists and `--onlynew` is absent, the command prints that it did
  nothing and exits successfully;
- with `--onlynew`, existing attempt directories are untouched and only missing attempts are generated; `run_all_auto.sh` is rewritten to contain only the newly created attempts;
- `orchexp/reprepdirs` deletes the entire current `wp/` tree after an interactive
  prompt. It should not be used when preserving experiment data.

## Model comparison semantics

An attempt is counted as successful if at least one matched run meets every setup constraint. The “best objective” comparison considers only feasible runs selected by the agent's `best.txt` across the three attempts for each model. The cumulative-minimum plot considers feasible tuning-phase runs and shows the running best objective per attempt.

The reported technique lists are derived from agent-populated `description` and `why` text, not from independent controller-code classification.
