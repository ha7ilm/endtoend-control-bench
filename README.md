# endtoend-control-bench

Companion repository for the paper *Benchmarking end-to-end control design
with LLM coding agents should be a continuous effort* by András Retzler, Tom
Lefebvre, and Guillaume Crevecoeur, prepared for the 23rd IFAC World Congress
(2026).

This project investigates whether contemporary LLM coding agents can carry out
control-system design end to end: interpreting plant equations and engineering
requirements, choosing a controller structure, implementing it against a
sample-by-sample simulated machine, and iteratively tuning it toward an
objective. By comparing frontier agents across well-known and more realistic
plant variants, the research asks not only whether an agent can produce a
numerically feasible controller, but also what techniques it chooses when left
free to design, how reliably it recognizes physically meaningful behavior, and
where apparently successful optimization still demands expert human oversight.

- [🌍 Project website](https://research.retzler.hu/bench_llm_ctl_2026/)
- [🔍 Results explorer](https://research.retzler.hu/bench_llm_ctl_2026/results_explorer/)
- Read [REPRODUCTION.md](REPRODUCTION.md) to reproduce the paper.
