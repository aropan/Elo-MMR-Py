# API

All public names are exported through `elo_mmr_py.__all__`, and the distribution
contains `py.typed` plus a stub for the native module.

::: elo_mmr_py.rate

::: elo_mmr_py.rate_latest

::: elo_mmr_py.Rater

All operations on one `Rater` instance are serialized. In particular,
`ratings` waits for an in-progress `add()` or `extend()` to finish before it
builds a consistent snapshot; two simultaneous snapshot reads also run one at
a time. Separate `Rater` instances can compute in parallel.

The complete executable example is included from its tested source file:

<!-- fmt: off -->
```python
--8<-- "examples/incremental_service.py"
```
<!-- fmt: on -->

::: elo_mmr_py.Player

::: elo_mmr_py.Contest

Tie and ordering rules are explained in
[Contest representation](concepts.md#contest-representation).

::: elo_mmr_py.EloMmrConfig

Defaults and validation are defined in the canonical
[rating-system configuration](rating-systems.md#custom-elo-mmr-configuration)
guide.

::: elo_mmr_py.PlayerEvent

::: elo_mmr_py.PlayerRating

`contest_index` is global across checkpoint batches. `rating`, `rating_mu`,
`rating_sig`, and `perf_score` are rounded integer presentation values.
`mu` and `sig` expose the corresponding full-precision posterior values.
