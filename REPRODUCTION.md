# Reproducing the paper experiments

This document reproduces the experiments in the paper [Benchmarking end-to-end control design with LLM coding agents should be a continuous effort](https://research.retzler.hu/bench_llm_ctl_2026/). It is the linear runbook; the [`docs/`](docs/README.md) directory contains reference material for the setup matrix, protocol, artifacts, analysis tools, and troubleshooting.

*⚠ The benchmark is simulation-only. Do not deploy an agent-generated controller on physical equipment. The paper deliberately contains examples that satisfy the numerical objective while being physically unreasonable or visibly unstable.*

**Reference platform:** the research was run and tested on Ubuntu 24.04 LTS. Linux is required for the supplied Bubblewrap isolation. (Other Linux distributions may work, but were not the reference environment.)

The commit associated with the paper is `🔴`. New developments to be implemented, in order to apply the benchmark to recent versions of coding agents, will be  recorded under [Developments since the paper](docs/developments-since-paper.md).

## How the reproduction relates to the paper

The paper asks whether a coding agent can perform a complete control-design workflow rather than merely answer a textbook question: read a plant and its requirements, choose a controller structure, implement it, evaluate it against a simulator, interpret the feedback, and improve it. The reproduction therefore preserves more than the final KPI values. It preserves the prompt, every controller iteration, the simulator traces, the agent's own explanations,
and the mapping between them.

The generated artifacts support four distinct parts of the paper's argument:

- **Feasibility:** the success-rate tables ask whether the controller selected by each attempt satisfies every stated step-response constraint.
- **Design behavior:** controller sources and summaries show what control techniques the agents chose when no controller family was prescribed. 
- **Optimization behavior:** cumulative feasible-minimum curves show how the objective improved over successive tuning runs.
- **Engineering judgement:** step responses, control signals, and full traces expose behavior that a compact objective can miss. This is essential to the paper's warnings about physically unreasonable optimization, unnoticed oscillation, and the continuing need for expert review. One of the paper's findings is that an agent can satisfy the supplied metrics while making a poor engineering choice.

## What can be reproduced

There are three useful levels of reproduction:

1. **Test suite**: `pytest` validation of the simulator, protocol, KPI calculations, analysis rules, and packaged client. This checks that the experimental apparatus behaves as specified; it does not rerun the agents or reproduce the paper's empirical results.

2. **A fresh benchmark rerun** gives the prompt and simulator to the two coding-agent configurations for 54 independent design attempts. Outputs go under `results/current_run/`. This reproduces the method and permits a new comparison of agent behavior.

*Note: Because the agents are hosted, stochastic services without a seed, controller code, iteration counts, and objective values will be different from that of the paper, but the overall tendencies are expected to be the same.*

3. **Paper artifact and Results Explorer regeneration** builds tables and
   figures from a completed `results/current_run/` tree. Use a fresh result from
   level 2. (🔴 the paper's archived data will be available to download later).

## Experimental design

The paper evaluated:

- nine discrete-time simulation setups: five CTMS-derived models and four altered, more realistic variants;
- two agents:
	- GPT-5.3 Codex through Codex CLI at `xhigh` reasoning effort;
	- Claude Opus 4.6 through Claude Code;
- three independent attempts for every setup/model pair;
- one prompt, `customctlchoice`, which lets the agent select the controller structure.

This gives `9 setups x 2 agents x 3 attempts = 54` agent sessions. Each session first designs until all strict KPI constraints are met, then minimizes a setup-specific objective, writes one `controller_N.py` per evaluated controller, and selects a controller in `best.txt`. The paper reports 1,349 evaluated controllers. There was intentionally no numeric stopping condition for the tuning phase.

![Pasted image 20260818173029](docs/Assets/Pasted%20image%2020260818173029.png)


The five CTMS-derived setups make the benchmark recognizable and comparable to standard control-design exercises. The four adjusted setups change parameters and add nonlinearities or actuator limits based on real products. The paper uses that second group to reduce the chance that success comes only from prior familiarity with well-known CTMS solutions and to test whether conclusions survive more physical constraints.

Three attempts per setup/model pair are needed because hosted agents are stochastic and expose no reproducible sampling seed. An attempt is a fresh design session, whereas the many `controller_N.py` files inside it are the iterations of one design process. The two-phase prompt separates the ability to find any feasible controller from the ability to improve a stated objective. Leaving the controller family and stopping point open is also deliberate: it lets the paper study technique choice and agent persistence, but means raw iteration counts are observations rather than a controlled compute budget.

The exact setup identifiers, limits, objectives, sample periods, and horizons are listed in [Experiment reference](docs/experiment-reference.md).

## 1. Prepare the environment

The launch scripts assume Linux, Bash, Git, Bubblewrap (`bwrap`), `fuser` (normally from the `psmisc` package), Python 3.12.2, and authenticated Codex CLI and Claude Code installations. Running all 54 sessions requires network access, LLM provider accounts, and can potentially incur substantial LLM usage cost.

Environment reproduction matters here for two reasons. First, numerical and plotting libraries participate in simulation, KPI calculation, and figure generation. Second, the agent CLI version, model identifier, reasoning setting, and sandbox determine what the agent can do and what information it can see. Changing either layer can define a materially different benchmark even when the prompt text is unchanged.

On Ubuntu 24.04 LTS, install the required operating-system packages with:

```bash
sudo apt update
sudo apt install bash bubblewrap ca-certificates git psmisc  
```

`psmisc` provides `fuser`, which the generated launchers use to stop the local simulation server. Codex CLI, Claude Code, and Anaconda are not installed by the command above; install and authenticate those separately. Anaconda's Python will be used. 

### Reproduce the Conda environment

The reference machine used **Anaconda Distribution 2024.06-1**, **Conda 24.9.2**, and **Python 3.12.2**. The  [`environment.yml`](environment.yml) records, among others, the exact Python package versions used for reproduction. To reproduce the environment, run from the repository root:

```bash
conda env create --file environment.yml
conda activate endtoend-control-bench
```

### Sandboxed agent commands

Some shell scripts call `codexs` and `claudes`. These are Bubblewrap launchers for `codex` and `claude`, respectively. They make the current attempt workspace the agent's only writable project directory while exposing the authenticated LLM agent CLI, and the active Python environment with the installed `urletra` client. Install the sanitized wrappers from [Sandbox wrappers](docs/sandbox-wrappers.md) somewhere on `PATH` before generating or running attempts.

The underlying invocations and model settings are preserved in:

- `promptcomp/prompt_agent_commands/codex53xhigh/start_llm_auto.sh`
- `promptcomp/prompt_agent_commands/opus46high/start_llm_auto.sh`

It is not suggested to replace these wrappers with direct CLI aliases for reproducing the results of the paper. Codex's default file visibility at the time of the research could expose other host files readable by the user. Sandbox wrappers prevents either agent from looking for solutions in `controlserver/`, or other attempts. See [Architecture and protocol](docs/architecture.md#agent-boundary).

This boundary is part of the experimental treatment, not only a host-security measure. If one agent can inspect simulator internals, reference controllers, or another attempt's work, the experiment no longer measures design from the information stated in the prompt and the comparison between agents is unfair.

## 2. Smoke tests (optional)

You can run the full test suite (before starting to spend model credits):

```bash
pytest -q
```

This is the cheapest point at which to detect an incompatible environment. A test failure should be resolved before interpreting any later failure as an agent limitation.

During the experiment, the LLM communicates with the plant to be controlled through a TCP client/server architecture. For a manual smoke test for this, use two terminals with the Conda environment active. In terminal 1:

```bash
python -m controlserver.server \
  --port 9000 \
  --setup motorspeed_dt \
  --experiment_id smoke \
  --design_attempt 0
```

In terminal 2:

```bash
python -m controlclient.examples.dt.motorspeed_digital_trial3_modified_pid
```

Stop the server with `Ctrl-C`. The server-side result should be `results/current_run/sim/motorspeed_dt/smoke/attempt0/run0.npy`; the client also
writes CSV and JSON files under its current directory's `run_outputs/`, which you can delete afterwards with:

```sh
rm -rf run_outputs
```

## 3. Prepare the 54 agent workspaces

You can prepare the agent workspaces with the following command: 

```bash
python -m orchexp.prepdirs --attempts 3
```

This creates:

```text
results/current_run/wp/
  <setup>/
    customctlchoice_<model>/
      attempt0/
      attempt1/
      attempt2/
  run_all_auto.sh
```

Each attempt receives the rendered prompt, a plant description, the public client-interface description, and generated launch scripts. The agent works in `lwp/rlwp/`; controller code and `best.txt` are expected there. The outer attempt directory stores the rendered prompt and launcher; `lwp/rlwp/` is the restricted working directory visible to the agent. Keeping attempts separate prevents one session's controller code or conclusions from becoming unintended input to another.

*Note: if there are existing results in the `results/current_run/` folder, `orchexp.prepdirs` will deliberately do nothing. This protects evidence from a previous or partially completed experiment from silent replacement.*

Optionally, feel free to inspect some rendered prompts and scripts: 
```bash
cat results/current_run/wp/ballandbeam_dt/customctlchoice_codex53xhigh/attempt0/prompt.md
cat  results/current_run/wp/ballandbeam_dt/customctlchoice_codex53xhigh/attempt0/start_llm_auto.sh
```

## 4. Run the agents

### Smoke testing the agent (optional)

Start with one attempt:

```bash
cd results/current_run/wp/ballandbeam_dt/customctlchoice_codex53xhigh/attempt0
./start_llm_auto.sh
```

Return to the repository root afterward. A launch script starts the appropriate simulator on `127.0.0.1:9000`, runs one agent in the prepared workspace, streams the agent log through a terminal viewer, and stops the server on exit.

Starting with one attempt verifies credentials, wrapper paths, model access, logging, and cleanup. The paper studies agent design behavior, so a launcher or account failure should not be counted as an unsuccessful control-design attempt.

After confirming one attempt works, delete `results/current_run` and regenerate with `python -m orchexp.prepdirs`, before proceeding to the full sweep.

### Run full sweep

Launch the paper-sized sweep from the repository root:

```bash
bash results/current_run/wp/run_all_auto.sh
```

The generated script is sequential because all attempts use port 9000.

*⚠️ The `customctlchoice` prompt has no tuning budget or fixed iteration count. Agents decide themselves when to stop with the design. Running two agents 54 times can incur significant costs.*

## 5. Check experiment completeness

Every completed agent session should contain `best.txt` and `summary.md`:

```bash
find results/current_run/wp -path '*/lwp/rlwp/best.txt' | wc -l
find results/current_run/wp -path '*/lwp/rlwp/summary.md' | wc -l
find results/current_run/sim -name 'run*.npy' | wc -l
```

The first two counts should be 54. The last count is agent-dependent; the paper
reports 1,349 evaluated controllers. 

*⚠️ See [Troubleshooting](docs/troubleshooting.md) before rerunning an attempt. Rerunning into an existing attempt can mix old and new artifacts and shift run indices.*

## 6. Match controllers to simulator runs

Controller names and simulator-run names come from independent sequences. The agent chooses the one-based source filename (`controller_1.py`, `controller_2.py`, ...), while the server assigns the zero-based run index from its count of accepted TCP connections. Therefore `controller_N.py -> run(N-1).npy` holds only when each controller is executed
exactly once, in filename order, against one uninterrupted server process.

The correspondence can shift or become ambiguous for reasons beyond the one-based/zero-based convention:

- a connection can be accepted and then fail during setup validation, protocol exchange, or controller execution; this consumes a run index without writing the corresponding `runN.npy`;
- the same controller can be executed more than once, producing extra runs without creating another controller source file;
- a controller file can be created but never executed, or controllers can be executed out of filename order;
- restarting the server or rerunning into the same attempt directory resets the connection counter and can mix or overwrite earlier runs.

Build and validate the mapping rather than inferring it from the indices:

```bash
python -m orchexp.match_runnpy_controllerpy
```

The command writes `results/current_run/npy_match.csv`. It first tests the `N-1` candidate by comparing the controller's `MachineClient` `why` and `description` with the run's persisted `llm_said` metadata. If that fails, it searches up to three run indices in either direction for an exact `why` match. The statuses mean:

- `PASS`: the `N-1` candidate has matching `why` and description metadata;
- `WARN`: the mapping is usable after review, typically because a nearby
  shifted run was recovered, or because the description could only be checked
  by a static prefix while `why` matched exactly;
- `FAIL`: no usable mapping was established because the source/run was missing
  or unreadable, metadata did not agree, or any shift was outside the recovery
  window.

The matcher exits with status 2 if any rows are `FAIL`; the CSV is still written
so those rows can be investigated.

Downstream consumers use the reviewed CSV as follows:

- `dashes.tables` follows the `best.txt` controller through a `PASS` or `WARN` row to load that run's KPIs. A `FAIL` or missing mapping prevents that attempt from contributing a feasible success or objective candidate, although the attempt remains in the success-rate denominator.
- `dashes.view_sim_step_responses` displays runs independently of the CSV, but uses only `PASS` and `WARN` rows to link controller sources and mark the `best.txt`-selected run. A `FAIL` mapping provides neither attribution nor a best-run marker.
- `orchexp.mkresultsexplorer` exports runs independently of the CSV, but uses only `PASS` and `WARN` rows to attach controller source/metadata and identify the selected best run. A `FAIL` mapping is ignored for those purposes.

No other analysis command reads `npy_match.csv` directly. In particular,
`dashes.figure_cumulative_minimums` reads the saved runs and KPIs themselves;
it does not use the controller-to-run mapping.

**Manual review of this CSV is required before analysis.** Open `results/current_run/npy_match.csv` in a spreadsheet editor and:

1. inspect every `WARN` and `FAIL` row against the referenced controller source, the `.npy` file's `llm_said` metadata, and, when needed, the agent/server logs;
2. confirm that every shifted `WARN` points to the controller execution that actually produced that run;
3. spot-check `PASS` rows from every setup/model pair, including the first run, the design-to-tuning transition, and the controller named by `best.txt`;
4. record and resolve unexplained mismatches before using the aggregate tables or figures.

The script is an automated matching aid, not a substitute for this manual provenance check. Do not assume that `controller_N.py` belongs to `run(N-1).npy` merely because the indices line up.

## 7. Generate aggregate analysis

This stage turns the raw experiment tree into the three quantitative views used by the paper:

- success rates answer whether repeated independent attempts ended with a feasible selected controller;
- best feasible objectives compare the agents' selected outcomes across the three attempts for each setup;
- cumulative feasible minima show the path through tuning and make differences in convergence speed and persistence visible.

### list_of_all_controllers.csv

The unified comparison table can optionally include a manually curated list of the control techniques tried by each model for each setup. To include those columns, review the generated controller sources and the attempt summaries under `results/<selected_run>/wp/`, then create `results/<selected_run>/list_of_all_controllers.csv` with this format:
```csv
setup,model,"control techniques applied (as claimed by the agent)"
motorspeed_dt,codex53xhigh,"P, PI, PID, LQI"
motorspeed_dt,opus46high,"PI, PID, deadbeat"
```

Use the setup and model identifiers from the result directory names, write one
row per setup/model pair, and combine the techniques claimed across that pair's
attempts. This file is optional: if it is absent, `dashes.tables` prints a
warning, leaves the technique columns empty, and still generates all tables.
The selected run is the directory passed to `--folder`, which defaults to
`results/current_run`.

### Commands to generate the tables and figures

These commands work for both the original result archive and a fresh rerun:

```bash
python -m dashes.tables --folder results/current_run
python -m dashes.figure_cumulative_minimums --folder results/current_run
```

They create:

- `results/current_run/analysis_artifacts/tables/unified.{html,tex}` and
  supporting tables/audit text;
- `results/current_run/analysis_artifacts/figures/cumulative_minimums.html`;
- one- and two-column PDF versions of the cumulative-minimum figure.

The table audit text records the constraint checks, objective terms, and excluded selections behind the compact presentation.

The cumulative plot scans all saved runs in execution-index order and allows only feasible runs to improve the running best objective. Before the first feasible controller the curve has no value; under the prompt protocol, that first feasible point ends design and later iterations are tuning. The plotting script does not infer phase from `why` text. The curves complement the endpoint table: two agents can reach similar final values while taking very different numbers of iterations or following different search trajectories. The paper's judgement about which agent converged better was informed by these curves, not by final objective values alone.

Browse individual runs interactively with:

```bash
python -m dashes.view_sim_step_responses --folder results/current_run/sim
```

Then open `http://127.0.0.1:8201/`.

Use the viewer to inspect the reference, measured response, control signal, disturbance, KPIs, and agent metadata together. This is where an engineer can notice oscillation, saturation, excessive control effort, or a misleadingly good scalar objective.

### ⭐ Main output: *Results Explorer* static site 

Generate a Results Explorer static site to be published online:

```bash
python -m orchexp.mkresultsexplorer \
  --source results/current_run \
  --out results/current_run/site-reproduced
```

Use `--vendor` if the explorer must bundle its browser libraries; that option downloads them from the network. `--clean` removes the selected output directory before rebuilding it.

The generated `index.html` cannot be just opened from the browser though: the site only opens through a local web server. You can start one with:
```
python -m http.server -b 127.0.0.1  8192
```
...and then browse to: http://127.0.0.1:8192/ 

*Warning: Agent transcripts may include absolute paths, tool/account metadata, or copied environment content. Build into a separate output path, review `data/build_issues.json`, inspect the resulting text/JSON, and use `--sanitize-config` for known literal replacements. Do not publish the raw site until that review is complete.*

## 8. Regenerate the remaining three graphs in the paper

These figures are case studies rather than additional aggregate metrics, justifying specific observations. Ideally with the original paper result tree in `results/current_run/`, run:

```bash
python -m dashes.figure_specific_step_responses --folder results/current_run
```

This writes the following files under
`results/current_run/analysis_artifacts/figures/`:

- `cruisecontrol_dt_codex.pdf`
- `cruisecontrol_hondajazz_wiggle.pdf`
- `motorspeed_dt_lim_maxonre30_proper.pdf`

The script intentionally hard-codes the setup, model, attempt, and run indices used by the paper. 

## Reproducibility limitations to report

The paper argues that this benchmark should be repeated as models and agent tools evolve. For that comparison to be meaningful, a new report must separate changes in model capability from changes in prompts, budgets, dependencies, sandbox access, or analysis rules. Record deviations even when they appear to make the experiment easier or more reliable.

Hosted model behavior can change even when a model name is the set the same; neither launcher exposes a sampling seed. The simulator is deterministic for a fixed controller, but the controller generation process is not.