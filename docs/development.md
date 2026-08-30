# Development

## Prerequisites

- [uv](https://docs.astral.sh/uv/); `pyproject.toml` is the source of truth for
  the required uv release
- a standard CPython 3.11 or newer
- rustup; `rust-toolchain.toml` is the source of truth for the Rust toolchain and
  required components
- cargo-audit; install the version recorded in `.cargo/audit-version`

## Environment

```bash
git clone https://github.com/aropan/Elo-MMR-Py.git
cd Elo-MMR-Py
uv sync --all-groups --locked
```

The mixed Maturin layout keeps Python in `src/elo_mmr_py` and the PyO3 extension
in `src/rust/lib.rs`. `uv sync` installs the project in editable mode through
the configured Maturin build backend. The uv cache keys in `pyproject.toml`
trigger a rebuild when Rust sources or Cargo configuration change. `Cargo.lock`
and `uv.lock` are committed; use `--locked` for environment synchronization.

## Required checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python -m mypy.stubtest --ignore-disjoint-bases elo_mmr_py.elo_mmr_python_bindings
uv run pytest --cov=elo_mmr_py --cov-report=term-missing --cov-report=xml
cargo fmt --all --check
cargo clippy --all-targets --all-features --locked -- -D warnings
cargo test --locked
cargo audit --deny warnings
uv run mkdocs build --strict
uv audit --locked
export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)
uv build --sdist --out-dir dist
uv build --wheel --out-dir dist
```

Ruff handles linting and formatting, while `ty` performs semantic type checking
across Python sources, tests, benchmarks, and examples. `mypy` is installed only
for `mypy.stubtest`, which imports the native extension and verifies that its
runtime API matches the shipped `.pyi` declarations.

`.cargo/audit.toml` keeps vulnerabilities and new RustSec warnings blocking. A
specific advisory may be ignored only when its transitive path, runtime
relevance, accepted risk, and the lack of an upstream removal mechanism are
documented next to the exception.

The CI `rust-coverage` job is the canonical instrumented-coverage procedure: it
reads the cargo-llvm-cov pin from `.cargo/llvm-cov-version`, combines Rust unit
tests with calls through the Python extension, and uploads LCOV without an
arbitrary first-release percentage gate.

Documentation examples are the real files in `examples/` and are executed by
pytest. On pushes to `main`, the same strict documentation artifact
is deployed only after all other CI jobs succeed.

## Benchmarking

The [Performance guide](performance.md) is the canonical source for benchmark
commands, comparison controls, reference results, and acceptance rules.
