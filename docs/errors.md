# Errors

The native boundary converts failures into stable Python exception categories:

| Exception | Meaning |
| --- | --- |
| `ValueError` | Unknown/removed system, invalid contest or rating configuration, malformed JSON, schema mismatch, incompatible checkpoint metadata |
| `OSError` | Checkpoint open, read, temporary write, sync, or atomic replacement failure |
| `RuntimeError` | An unexpected panic or internal Rust failure |
| `TypeError` | A Python argument has the wrong structural type, such as a bytes checkpoint path |

Validation occurs before the rating calculation. The accepted contest shape is
defined in [Concepts](concepts.md#contest-representation), initial-parameter and
system constraints in [Rating systems](rating-systems.md), and persistence
validation in [Checkpoints](checkpoints.md). Integers outside the supported Rust
range raise `ValueError` rather than a conversion-specific `OverflowError`.

```python
from elo_mmr_py import Contest

try:
    Contest([('alice', 0, 0), ('alice', 1, 1)])
except ValueError as error:
    print(error)
```

An unexpected Rust panic is caught only as a final safety boundary. It is a bug;
report it with a minimal contest/checkpoint reproducer and the package version.
If it occurs during a `Rater` operation, that instance is poisoned and rejects
subsequent access rather than exposing partially updated state.
