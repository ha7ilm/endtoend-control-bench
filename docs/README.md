# Documentation

Start with [`REPRODUCTION.md`](../REPRODUCTION.md) for the end-to-end procedure.
These pages are reference documentation for understanding, auditing, and
debugging a reproduction:

- [Experiment reference](experiment-reference.md): setup matrix, constraints,
  objectives, prompts, models, and orchestration identifiers.
- [Architecture and protocol](architecture.md): agent/server isolation,
  feedback-loop sequence, wire messages, and determinism boundary.
- [Sandbox wrappers](sandbox-wrappers.md): sanitized `codexs` and `claudes`
  Bubblewrap launchers used to enforce the agent information boundary.
- [Artifacts and analysis](artifacts-and-analysis.md): directory layouts, file
  schemas, matching rules, analysis tools, and generated outputs.
- [Developments since paper](docs/developments-since-paper.md): documenting main changes since our [paper](https://research.retzler.hu/bench_llm_ctl_2026/) has been published. 
- [Troubleshooting](troubleshooting.md): symptoms, causes, diagnostics, and safe
  recovery guidance.

The source of truth remains the executable code. In particular:

- setup dynamics and sampling: `controlserver/setups/` and
  `controlserver/setup_variants.py`;
- feasibility and objective formulas: `dashes/parse_kpis.py`;
- prompt composition: `promptcomp/` and `orchexp/prepdirs.py`;
- persisted run schema: `controlserver/session.py`;
- public installed client: `src/urletra/controlclient/`.
