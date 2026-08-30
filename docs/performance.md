# Performance

## Runtime behavior

Argument conversion happens at the Python boundary, then `rate()`,
`rate_latest()`, and `Rater` operations detach Rust work from the interpreter.
Other Python threads can run while Elo-MMR computes.

There is no JSON or whole-input string bridge. Constructing `Contest` converts
the Python standings tuples directly into the native Rust `Contest`; rating
calls receive those PyO3 objects and move owned Rust values into the detached
calculation. JSON serialization is used only for checkpoint files.

The two stateless APIs run the same rating algorithm:

- `rate()` converts every stored event into a Python `PlayerEvent`.
- `rate_latest()` converts only one `PlayerRating` per participant.

For long histories, the latter reduces returned Python objects from `O(events)`
to `O(players)`. It is the preferred service and leaderboard API.
`Rater` additionally retains state in Rust, so repeated updates do not parse a
checkpoint or replay old contests.

## Reproducible benchmark

The repository benchmark creates deterministic histories for 100, 500, and
1,000 participants, with 100 contests per history. It compares exact `mmr` with
opt-in `mmr-fast`, all-at-once APIs with `Rater.add()`/`Rater.extend()`, and
checkpoint read/write throughput:

```bash
uv sync --locked
uv run python benchmarks/benchmark.py --verify --output .benchmarks/current.json
```

It performs a warm-up, reports the median of 32 repetitions across four fully
counterbalanced cycles, and records Python peak memory with `tracemalloc`.
Paired forward/reverse rotations make every rating combination occupy every
execution position equally. Checkpoint measurements use five repetitions by
default. Checksums guard against accidental work elimination, while `--verify`
also requires `rate_latest()` to use less Python peak memory than `rate()` and,
for checkpoints at least 5 MiB large, write throughput of at least 20 MiB/s.
The deliberately coarse checkpoint floor catches severe serialization
regressions without treating ordinary runner timing as a stable benchmark. To
create a 1.0.3 regression baseline, run the same script and dataset on the same
machine with `--apis rate --skip-checkpoints` and the old package installed.
Accept 2.0 only when exact `rate()` is no more than 10% slower in that controlled
comparison.

## Reference run (2026-08-22)

These medians came from the documented release build on arm64 macOS 26.6 with
CPython 3.11.9. They are illustrative results, not cross-machine guarantees.

| Players | System | API | Median seconds | Python peak MiB |
| ---: | --- | --- | ---: | ---: |
| 100 | `mmr` | `rate` | 0.0331 | 0.56 |
| 100 | `mmr` | `rate_latest` | 0.0294 | 0.01 |
| 100 | `mmr-fast` | `rate` | 0.0271 | 0.56 |
| 100 | `mmr-fast` | `rate_latest` | 0.0245 | 0.01 |
| 500 | `mmr` | `rate` | 0.4060 | 2.81 |
| 500 | `mmr` | `rate_latest` | 0.3713 | 0.07 |
| 500 | `mmr-fast` | `rate` | 0.1179 | 2.81 |
| 500 | `mmr-fast` | `rate_latest` | 0.1037 | 0.07 |
| 1,000 | `mmr` | `rate` | 1.3813 | 5.62 |
| 1,000 | `mmr` | `rate_latest` | 1.2629 | 0.14 |
| 1,000 | `mmr-fast` | `rate` | 0.2410 | 5.62 |
| 1,000 | `mmr-fast` | `rate_latest` | 0.2174 | 0.14 |

On the 1,000 × 100 history, `rate_latest()` used about 40 times less Python peak
memory and was about 9% faster than `rate()` in exact mode. The opt-in fast mode
was about 5.7 times faster with `rate()` and 5.8 times faster with
`rate_latest()` in this particular dataset.

The weekly and manually dispatched Performance workflow runs a shorter release
build matrix and uploads its JSON report. Rating wall-time and checkpoint read
time remain informational because hosted-runner speed is not stable enough for
a universal hard gate; only the coarse write-throughput floor above is enforced.

## Checkpoint reference (2026-08-26)

On the same arm64 macOS/CPython setup, a release-build `mmr-fast` history of
1,000 players × 100 contests produced a 16.30 MiB compact checkpoint. Median
write time was 0.0500 seconds and median load-plus-snapshot time was 0.0288
seconds across three repetitions. Treat these as same-machine reference values,
not filesystem-independent guarantees.

## Version 1.0.3 regression check

The same machine also ran `--apis rate --repeat 7` against a clean 1.0.3 source
build. Negative change means 2.0 was faster:

| Players | System | 1.0.3 seconds | 2.0.0 seconds | Change |
| ---: | --- | ---: | ---: | ---: |
| 100 | `mmr` | 0.0274 | 0.0261 | -4.7% |
| 100 | `mmr-fast` | 0.0223 | 0.0224 | +0.4% |
| 500 | `mmr` | 0.2661 | 0.2813 | +5.7% |
| 500 | `mmr-fast` | 0.0857 | 0.0863 | +0.7% |
| 1,000 | `mmr` | 1.0149 | 0.8910 | -12.2% |
| 1,000 | `mmr-fast` | 0.1827 | 0.1814 | -0.7% |

The largest measured 2.0 regression was 5.7%, within the 10% acceptance limit.

## Interpreting results

Compare builds on the same CPU, power profile, Python version, Rust target, and
background load. `mmr-fast` often helps on large contests but can have little
effect below its subsampling threshold. Benchmark your real contest-size and
history distributions instead of treating one published ratio as a guarantee.
