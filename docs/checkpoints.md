# Checkpoints and migration

## Saving and resuming

Checkpoints keep the full Rust state needed to resume without replaying old
contests. Save after a batch and load before the next one:

```python
from pathlib import Path

from elo_mmr_py import rate_latest

path = Path('ratings.json')
rate_latest(first_batch, save_checkpoint=path)
ratings = rate_latest(
    second_batch,
    load_checkpoint=path,
    save_checkpoint=path,
)
```

For a long-running service, `Rater` keeps the same state in Rust and avoids a
checkpoint read and write between ordinary updates. Its tested example lives in
the [API reference](api.md#elo_mmr_py.Rater).

The save is written to a temporary file in the destination directory, flushed,
and atomically renamed over the target. On Unix, the parent directory is also
synchronized after the rename so the directory entry survives a power loss.
On Unix, the replacement copies an existing regular file's POSIX mode bits; a
new checkpoint is owner-only (`0600`). It does not copy ACLs, extended
attributes, or ownership. No promise is made to retain custom Windows DACLs;
protect the destination directory with the access policy required by your
deployment.

Saving to a symbolic-link path replaces the link itself with a new regular
checkpoint and leaves the former link target untouched. Pass the resolved target
path instead if that target is the file you intend to replace.

A write or rename failure raises `OSError` and never exposes a partially
serialized target file. If the final parent-directory synchronization fails,
the complete replacement may already be visible even though `OSError` is
raised; callers should inspect or retry the checkpoint before continuing.

## Version 2 schema

The top-level JSON object is:

```json
{
  "format_version": 2,
  "package_version": "<installed package version>",
  "system": "mmr",
  "system_config": {
    "weight_limit": 0.2,
    "noob_delay": [],
    "sig_limit": 80.0,
    "drift_per_day": 0.0,
    "split_ties": false,
    "subsample_size": null,
    "subsample_bucket": 0.00001
  },
  "mu_noob": 1500.0,
  "sig_noob": 350.0,
  "contests_processed": 42,
  "last_time_seconds": 1700000000,
  "players": {}
}
```

`players` contains the serialized upstream state. Treat it as implementation
data. The system, resolved configuration, initial parameters, timeline, and
player state are validated before calculation begins. `package_version` records
which package wrote the file; it is metadata, not a compatibility check.
Checkpoints are compact JSON terminated by one newline. `system_config` is the
fully resolved Elo-MMR configuration, or `null` for other system families.
With the same package version and inputs, continuing from a canonical v2
checkpoint preserves finite floating-point state bit-for-bit and produces the
same result as processing the contests in one uninterrupted run.

The v2 envelope is intentionally strict: missing required fields and unknown
fields are rejected instead of being silently ignored. A future schema change
that old readers cannot validate safely must increment `format_version`; no
forward-compatibility promise is made from an older package to a newer format.

`contests_processed` is the next global event offset. Ignored outcome-free
contests count toward it, so later `PlayerEvent.contest_index` values remain
stable across batches. `last_time_seconds` enforces chronology across calls.

## Migrating version 1.x

Version 1.x wrote only the player map. Version 2 recognizes that shape, infers
the offset as `max(contest_index) + 1`, and infers the last timestamp from player
state. The next successful save writes the v2 envelope automatically.

Because a legacy file has no system or initial-parameter metadata, those values
cannot be verified while reading it. Once migrated, every continuation must use
the stored system, `mu_noob`, and `sig_noob`. Packages from the 1.x line are not
expected to read v2 checkpoints.

`Rater.load()` intentionally accepts canonical v2 only. Use `rate()` or
`rate_latest()` once to load and resave a legacy file before opening it through
`Rater`.

Exception categories for malformed data and filesystem failures are defined in
the [Errors reference](errors.md).
