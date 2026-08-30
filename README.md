# Elo-MMR-Py

[![CI](https://github.com/aropan/Elo-MMR-Py/actions/workflows/ci.yml/badge.svg)](https://github.com/aropan/Elo-MMR-Py/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue.svg)](https://aropan.github.io/Elo-MMR-Py/)
[![PyPI](https://img.shields.io/pypi/v/Elo-MMR-Py.svg)](https://pypi.org/project/Elo-MMR-Py/)
[![Python](https://img.shields.io/pypi/pyversions/Elo-MMR-Py.svg)](https://pypi.org/project/Elo-MMR-Py/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Fast Python bindings for [Elo-MMR](https://github.com/EbTech/Elo-MMR), a
multiplayer rating method designed for contests with many participants. The
rating calculation runs in Rust and releases Python's GIL, while the public API
uses ordinary Python objects and precise type information.

The exact `mmr` algorithm is the default. The approximate `mmr-fast` variant
remains an explicit choice.

## Installation

```bash
python -m pip install Elo-MMR-Py
```

Binary ABI3 wheels support standard CPython 3.11 and newer on Linux x86_64 and
aarch64, macOS x86_64 and arm64, and Windows x86_64. PyPy, free-threaded CPython,
and 32-bit platforms do not have prebuilt wheels.

## Quickstart

Use `rate_latest()` for leaderboards and services. It creates one immutable
`PlayerRating` per participant instead of one Python object per historical event.

```python
from elo_mmr_py import Contest, rate_latest

contests = [
    Contest(
        standings=[('Ada', 0, 0), ('Grace', 1, 1), ('Linus', 2, 2)],
        name='Example final',
        time_seconds=1_700_000_000,
    )
]

leaderboard = sorted(rate_latest(contests).values(), key=lambda player: -player.rating)
for player in leaderboard:
    print(player.name, player.rating, player.rating_sig, player.contests_played)
```

Use `rate()` when you need every historical rating event:

```python
from elo_mmr_py import rate

players = rate(contests)  # system='mmr' is the exact default
ada_history = players['Ada'].events
```

Long-running services can retain state with `Rater`, and advanced Elo-MMR users
can pass an immutable `EloMmrConfig`. Their canonical interfaces and executable
example are in the [API documentation](https://aropan.github.io/Elo-MMR-Py/api/).

## Standings and ties

A standing is `(name, low_rank, high_rank)`. Ranks are zero-based and inclusive.
An ordinary result has `low_rank == high_rank`; tied participants repeat the
same interval. See [Contest representation](https://aropan.github.io/Elo-MMR-Py/concepts/#contest-representation)
for a tie example and the complete ordering rules.

## Rating systems

`mmr` is the recommended exact default. `mmr-fast` is an explicit approximation
whose benefit depends on the workload. See [Rating systems](https://aropan.github.io/Elo-MMR-Py/rating-systems/)
for every supported mode and its constraints.

## Checkpoints

Both APIs accept `str | os.PathLike[str]` checkpoint paths and can atomically
save or resume rating state. The [checkpoint guide](https://aropan.github.io/Elo-MMR-Py/checkpoints/)
is the canonical reference for the schema, migration, compatibility, file
permissions, symlinks, and failure behavior.

## Documentation and development

The complete guide covers [concepts](https://aropan.github.io/Elo-MMR-Py/concepts/),
[API details](https://aropan.github.io/Elo-MMR-Py/api/), checkpoints,
performance, errors, development, and releasing. Source setup and all required
checks live in the [development guide](https://aropan.github.io/Elo-MMR-Py/development/);
see [CONTRIBUTING.md](CONTRIBUTING.md) for contribution policy.
