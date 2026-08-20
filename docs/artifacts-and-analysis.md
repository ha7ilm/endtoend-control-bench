# Artifacts and analysis

## Result tree

The complete experiment is split between agent workspaces and simulator data:

```text
results/current_run/
  wp/
    <setup>/<prompt>_<model>/attemptN/
      prompt.md
      start_llm_auto.sh
      start_llm_interactive.sh
      lwp/rlwp/
        problem_description.md
        howto_for_control_loop_software.md
        controller_1.py
        controller_2.py
        ...
        best.txt
        summary.md
        run_outputs/
        .codex/ or .claude/
  sim/
    <setup>/<prompt>_<model>/attemptN/runN.npy
  server_logs/
  npy_match.csv
  analysis_artifacts/
    figures/
    tables/
  site/
  tests/
```


## Attempt workspace files

| Artifact | Producer | Meaning |
| --- | --- | --- |
| `prompt.md` | `prepdirs.py` | Rendered top-level task given on agent stdin |
| `problem_description.md` | `prepdirs.py` | Setup-specific equations, parameters, requirements, and KPI paths |
| `howto_for_control_loop_software.md` | `prepdirs.py` | Public `MachineClient` usage contract |
| `controller_N.py` | agent | One executable controller evaluation; numbering is requested to start at 1 |
| `best.txt` | agent | Exact filename of the selected `controller_N.py` |
| `summary.md` | agent | Agent's narrative of its design and tuning process |
| `run_outputs/*.csv` | `MachineClient` | Client-observed reference, measurement, and control samples |
| `run_outputs/*.json` | `MachineClient` | Final KPI payload for one client run |
| `.codex/*.log` | Codex launcher | Codex CLI JSON event stream |
| `.claude/*.jsonl` | Claude launcher | Claude Code stream-JSON transcript |

Client-side CSV files use `step_index`, then `ref`/`meas` columns, then
`control`. Map-valued signals become columns such as `ref_x_cart` and
`meas_phi_angle`. Filenames use a millisecond timestamp and are not the
authoritative controller-to-run key.

## Server `runN.npy` schema

Each file is a NumPy-pickled scalar dictionary. Load only trusted result files:

```python
import numpy as np

payload = np.load("path/to/run0.npy", allow_pickle=True).item()
```

The dictionary contains:

| Key | Type | Meaning |
| --- | --- | --- |
| `setup` | string | Concrete setup identifier |
| `llm_said` | dictionary | `setup`, `description`, and `why` copied from the client hello |
| `time_sec` | 1-D NumPy array | Sample timestamps |
| `ref` | 1-D array or dictionary of arrays | Reference trace |
| `meas` | 1-D array or dictionary of arrays | Measurement trace |
| `control` | 1-D NumPy array | Commanded controller output, before any setup-side actuator clipping |
| `disturbance` | 1-D NumPy array | Applied disturbance trace |
| `kpis` | dictionary | Scalar or per-channel KPI payload |

The filename index is based on accepted TCP connections, not controller source
names. See [Run indexing](architecture.md#run-indexing).

## Controller-to-run mapping

Run:

```bash
python -m orchexp.match_runnpy_controllerpy
```

Primary mapping is `controller_N.py -> run(N-1).npy`. The utility parses the
first `MachineClient` call in controller source and compares its `why` and
`description` against `llm_said` in the result.

If the primary index does not match, the utility searches offsets `-1`, `+1`, `-2`, `+2`, `-3`, `+3` for an exact `why` match. A dynamically constructed description can pass using a statically resolvable prefix of at least 20 characters.

`results/current_run/npy_match.csv` columns are:

- `status`: `PASS`, `WARN`, or `FAIL`;
- `run_path` and `controller_path`, relative to `results/current_run/`;
- `note`, including shifted-match or parse details;
- `.npy` and `.py` versions of `why` and `description`.

`PASS` is an exact normal match. `WARN` is usable but requires review, commonly
because an index was shifted or only a description prefix could be resolved.
`FAIL` is excluded by analysis. The matcher exits 2 when any failures exist.

### Required manual spreadsheet review

Treat `npy_match.csv` as a review worksheet rather than automatically accepted ground truth. Before generating tables or figures, open it in a spreadsheet editor and manually evaluate the mappings.

Review every `WARN` and `FAIL` row. For each one, compare:

- `controller_path` and `run_path`;
- the controller's `MachineClient` `description` and `why` values;
- the persisted `npy_description` and `npy_why` values;
- neighboring run indices, especially when the note reports a shift.


## Analysis command reference

All commands below are run from the repository root.

| Command | Inputs | Principal outputs |
| --- | --- | --- |
| `python -m dashes.tables --folder results/current_run` | `sim/`, `wp/`, `npy_match.csv`, setup/model maps | HTML and LaTeX success, comparison, and unified tables plus audit text in `analysis_artifacts/tables/` |
| `python -m dashes.figure_cumulative_minimums --folder results/current_run` | matched feasible tuning runs | interactive HTML and three PDFs in `analysis_artifacts/figures/` |
| `python -m dashes.figure_specific_step_responses --folder results/current_run` | fixed original run paths | three selected-response PDFs used by the paper |
| `python -m dashes.figure_specific_step_responses_smaller --folder results/current_run` | same fixed original paths | alternate compact/type-3-oriented rendering |
| `python -m dashes.view_sim_step_responses --folder results/current_run/sim` | `sim/`, optionally `wp/` and mapping | Dash run browser on port 8201 |
| `python -m orchexp.mkresultsexplorer --source results/current_run` | workspaces, transcripts, simulation runs, mapping | static site, default `results/current_run/site/` |
| `python -m dashes.list_all_inline_python ...` | agent transcript paths | inspection of inline Python executed during agent reasoning; see `--help` |

## Table selection rules

The table generator:

1. assumes the generated mapping has already passed the required manual
   spreadsheet review;
2. discovers setup/model/attempt directories matching the selected prompt;
3. loads only usable controller/run mappings;
4. evaluates constraints with `dashes.parse_kpis.meets_design_spec`;
5. resolves each attempt's agent-selected `best.txt` controller;
6. compares the objective of feasible selections across attempts;
7. derives technique summaries from agent text.

Certain files in `analysis_artifacts/tables/` explain the underlying constraint
and objective calculations. 

## Cumulative-minimum figure

The cumulative plot identifies tuning runs by a case-insensitive `Tuning:` prefix in `llm_said["why"]`. Only feasible runs contribute. For every attempt, the plotted sequence is the running minimum of the setup objective over tuning iterations. A malformed or missing phase prefix prevents correct classification.

Outputs are:

- `cumulative_minimums.html` for interactive browsing;
- `cumulative_minimums_col1.pdf` and `cumulative_minimums_col2.pdf`;
- `cumulative_minimums_onecol.pdf`, used in the paper.

## Fixed selected-response figures

`dashes/figure_specific_step_responses.py` embeds the exact original selectors:

- CTMS cruise control, Codex attempt 0, runs 0-4;
- realistic cruise control, Opus attempt 0 run 4 and Codex attempt 0 run 6;
- realistic motor speed, the first feasible checkpoint runs selected from all three attempts of both models.

These selectors explain particular paper observations. 

## Static results explorer

`orchexp/mkresultsexplorer.py` combines controller source, run data, prompt files, summaries, and agent event streams into a static site. Important flags:

- `--out PATH`: choose an output other than `<source>/site`;
- `--clean`: delete the output directory before rebuilding;
- `--sanitize-config FILE`: apply additional literal replacements to exported
  text;
- `--exclude-agent NAME`: omit a named agent directory; repeat as needed.

Agent transcripts and generated controllers can contain local paths, account metadata, or other environment details. Review the built site's `data/build_issues.json` and sanitize the archive before publication.