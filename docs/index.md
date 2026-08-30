# Elo-MMR-Py

Elo-MMR-Py exposes the Elo-MMR multiplayer rating algorithms through a small,
typed Python API backed by Rust. See [Installation](https://github.com/aropan/Elo-MMR-Py#installation)
for the package command and supported wheel platforms.

## Complete leaderboard example

The following file is included verbatim and executed by the test suite:

<!-- fmt: off -->
```python
--8<-- "examples/leaderboard.py"
```
<!-- fmt: on -->

Output:

```text
1. Ada: 1705 ±171 (1 contest)
2. Grace: 1500 ±171 (1 contest)
3. Linus: 1295 ±171 (1 contest)
```

The [Concepts guide](concepts.md#full-history-versus-latest-state) explains which
rating API to use; the generated [API reference](api.md) is authoritative for
signatures and return types.
