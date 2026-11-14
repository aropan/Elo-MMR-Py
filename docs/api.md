# API

All public names are exported through `elo_mmr_py.__all__`, and the distribution
contains `py.typed` plus a stub for the native module.

::: elo_mmr_py.rate

::: elo_mmr_py.rate_latest

::: elo_mmr_py.Rater

All operations on one `Rater` instance are serialized. In particular,
`ratings` and `ratings_for(names)` wait for an in-progress `add()` or `extend()`
to finish before building a consistent snapshot; two simultaneous snapshot
reads also run one at a time. Separate `Rater` instances can compute in parallel.

Use `rater.ratings_for(names)` after each contest to retrieve only its participants.
It performs direct native lookups in `O(len(names))` time and returns the same
immutable `PlayerRating` values as the corresponding entries in `rater.ratings`,
without scanning or exporting the full population. Unknown names are omitted,
duplicates collapse to one result, and an empty sequence returns `{}`. Pass a
sequence of strings, such as a list or tuple, rather than a single string.
Reading a snapshot does not update ratings or checkpoint state.

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
    options:
      filters:
        - "!^_"

::: elo_mmr_py.PlayerRating
    options:
      filters:
        - "!^_"

`contest_index` is global across checkpoint batches. `rating`, `rating_mu`,
`rating_sig`, and `perf_score` are rounded integer presentation values.
`mu` and `sig` expose the corresponding full-precision posterior values.
