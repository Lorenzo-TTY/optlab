# Algorithm Policy

OptLab v1 now separates two use cases:

- Automated evaluator jobs keep the existing evolutionary path: GA for one objective, NSGA-II for two to three objectives, NSGA-III for four to six objectives, with RVEA available explicitly for four to six objective many-objective runs.
- Human or engineering-loop optimization uses an ask/tell advisor. User-entered observations are the primary dataset; advisor suggestions are optional editable references. The advisor first proposes Latin-hypercube candidates; after the initial design is observed, it switches to a ParEGO-style random Chebyshev scalarization ranked by an inverse-distance surrogate and diversity penalty.

The ask/tell interface is intentionally stateless. Each request sends the complete `ProblemSpec`, current saved observations, batch size, and seed to `/api/advisor/suggest`. The user may add any number of manual rows between suggestion requests; unsaved rows are not sent to the advisor. This keeps refresh/recovery simple and makes deterministic replay testable.

Research-aligned roadmap:

- BoTorch qLogNEHVI is the target optional backend for expensive noisy multi-objective engineering loops once `torch/gpytorch/botorch` are added as optional dependencies.
- qLogNParEGO is the preferred fallback for higher objective counts or cheaper scalarized BO batches.
- Legacy qEHVI/qNEHVI are retained as citations and conceptual ancestors, not the preferred future implementation, because the log-EI family addresses numerical vanishing in EI/EHVI variants.
- AGE-MOEA2 is not enabled by default in this environment because the local pymoo import requires `numba`; RVEA is available without adding that dependency.

Sources used for this policy:

- BoTorch multi-objective docs: https://botorch.org/docs/v0.16.0/multi_objective
- BoTorch acquisition API: https://botorch.readthedocs.io/en/stable/acquisition.html
- qNEHVI paper: https://papers.nips.cc/paper/2021/hash/11704817e347269b7254e744b5e22dac-Abstract.html
- qEHVI paper: https://arxiv.org/abs/2006.05078
- LogEI paper: https://arxiv.org/abs/2310.20708
- pymoo RVEA docs: https://pymoo.org/algorithms/moo/rvea.html
- pymoo algorithm catalog: https://pymoo.org/index.html
