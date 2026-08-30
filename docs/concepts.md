# Concepts

## What Elo-MMR estimates

Elo-MMR models each participant with a rating mean and uncertainty. After a
ranked multiplayer contest, it infers a performance and updates every entrant's
posterior rating. Unlike pairwise-only Elo adaptations, it handles one ordered
standing directly.

Ratings are estimates, not probabilities or guarantees. A participant with a
high uncertainty can move farther after the next result than an established
participant.

## Contest representation

Rating input is ordered chronologically by each `Contest.time_seconds`. Every
contest also contains a list of `(name, low_rank, high_rank)` tuples. Ranks are
zero-based and inclusive.

```python
from elo_mmr_py import Contest

contest = Contest(
    [
        ('alice', 0, 0),
        ('bob', 1, 2),
        ('carol', 1, 2),
        ('dave', 3, 3),
    ],
    time_seconds=1_700_000_000,
)
```

This means Alice won, Bob and Carol tied for ranks 1–2, and Dave finished last.
Every name must be unique and every tie member must repeat the same interval.

Empty contests and contests in which everyone ties are outcome-free. They do
not create player events, but they still occupy a global contest index and
advance checkpoint time.

## Full history versus latest state

`rate()` returns a `Player` with every `PlayerEvent`. This is useful for plots,
audits, and historical analysis. Returning the history requires `O(events)`
Python objects.

`rate_latest()` returns one immutable `PlayerRating` per participant. The Rust
algorithm still uses its internal history, but historical Python objects are not
materialized; the returned object count is `O(players)`.
