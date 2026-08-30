# Rating systems

## Recommended modes

| Name | Mode | Guidance |
| --- | --- | --- |
| `mmr` | Exact logistic Elo-MMR | Default; use when result parity and precision matter |
| `mmr-fast` | Approximate logistic Elo-MMR | Opt in for large contests after benchmarking your data |
| `mmx` | Exact Gaussian Elo-MMR | Alternative upstream model |
| `mmx-fast` | Approximate Gaussian Elo-MMR | Subsampled Gaussian alternative |

`mmr-fast` is not silently selected and there is no universal speedup promise.
Participant count, history shape, CPU, and the upstream subsampling threshold all
affect the result. See the [benchmark methodology](performance.md).

## Other supported upstream systems

The bindings also expose `bar`, `glicko`, `cfsys`, `tcsys`, `trueskill`, and
`mmr-simple`. They are included for comparison and compatibility and have smoke
coverage in CI.

`endure` is not supported. The upstream implementation can panic on ordinary
inputs, so the bindings reject it with `ValueError` instead of advertising a
non-working mode.

`elo_mmr_py.SUPPORTED_SYSTEMS` is the runtime source for the complete string
set; its type-level counterpart is `RatingSystemName`.

## Custom Elo-MMR configuration

Pass an immutable `EloMmrConfig` wherever the `system` argument is accepted:

```python
from elo_mmr_py import EloMmrConfig, rate_latest

config = EloMmrConfig(
    'mmr',
    weight_limit=0.25,
    noob_delay=[0.5, 0.75],
    sig_limit=70.0,
    drift_per_day=5.0,
    split_ties=True,
    subsample_size=200,
    subsample_bucket=1.0,
)
ratings = rate_latest(contests, system=config)
```

`weight_limit`, `sig_limit`, and `subsample_bucket` must be finite and positive.
`drift_per_day` must be finite and non-negative. Every `noob_delay` multiplier
must lie in `(0, 1]`; `subsample_size` is either a positive integer or `None`.
`None` selects the chosen mode's default: unlimited for exact modes and 100 for
fast modes. An omitted `subsample_bucket` similarly resolves to `0.00001` or
`2.0` respectively.

The resolved configuration is stored in checkpoints. Continuation with a
different value is rejected before rating begins.

## Per-contest parameters

`Contest(weight=...)` changes the relative update weight. `perf_ceiling=...`
caps the performance measured by that contest; `None` leaves it unlimited.
`weight` must be finite and greater than zero; `perf_ceiling` must be `None` or
finite. See the constructor in the [API reference](api.md#elo_mmr_py.Contest).

## Initial rating

`mu_noob` is the initial mean for a new participant and must be finite.
`sig_noob` is the initial uncertainty and must be finite and greater than zero.
The defaults are 1500 and 350. Checkpoint continuation requires the same values.
