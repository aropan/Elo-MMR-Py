# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] - 2026-08-30

### Added

- `rate_latest()` and immutable `PlayerRating` values for `O(players)` Python
  result objects.
- Rust-backed incremental `Rater`, exact `PlayerRating.mu`/`sig` values and
  update timestamps, per-contest weight/ceiling controls, and immutable
  `EloMmrConfig` values.
- Versioned, atomic checkpoints with automatic 1.x migration, global contest
  indices, and compatibility validation.
- Typed native stubs, `py.typed`, explicit exports, and package `__version__`.
- Deterministic performance benchmarks, MkDocs documentation, expanded tests,
  on-demand performance reports, separate Rust coverage, and complete CI, wheel,
  source-distribution, documentation, and release flows.

### Changed

- The Rust calculation releases the GIL through PyO3's detached execution API.
- Stateless and incremental APIs now share a direct `simulate_contest` state
  engine. Compact, buffered checkpoint writes avoid cloning player state and
  store the fully resolved Elo-MMR configuration.
- Packaging uses Maturin 1.14.1, PyO3 0.29.2, Python 3.11 ABI3, Rust 1.97.1,
  edition 2024, locked dependencies, thin LTO, one codegen unit, and stripped
  release binaries. uv owns editable environment synchronization and invokes
  the pinned Maturin backend when Rust or Cargo cache inputs change.
- Static type checking uses the pinned `ty` checker; `mypy.stubtest` remains as
  the runtime parity gate for the native PyO3 module and its `.pyi` declarations.
- `Cargo.toml` is the single source for the package version; Maturin derives the
  Python distribution version and the native module reuses it for checkpoints
  and `__version__`.
- GitHub Actions reads the pinned uv version from `pyproject.toml` instead of
  repeating it in each workflow.
- Wheel workflows read their Maturin and Rust pins from `pyproject.toml` and
  `rust-toolchain.toml` instead of repeating those versions in workflow YAML.
- The upstream Elo-MMR core is pinned to
  `f6f83bb2c54bf173e60a9e8614065e8d168a349b` without local algorithm changes.
- Input, checkpoint, and panic failures now have stable Python exception types.
- Validation is intentionally stricter than in 1.0.3: duplicate participant
  names, malformed or unsorted tie groups, decreasing timestamps, out-of-range
  integers, non-finite `mu_noob`, and non-positive or non-finite `sig_noob` now
  raise `ValueError`. Inputs previously accepted despite violating these
  invariants must be corrected before upgrading.
- Atomic checkpoint replacement copies an existing regular file's POSIX mode
  bits on Unix. New checkpoint files use owner-only mode (`0600`) on Unix, and
  the parent directory is synchronized after replacement. ACLs, extended
  attributes, ownership, and custom Windows DACLs are outside the preservation
  guarantee.

### Security

- GitHub Actions checkouts do not persist credentials. Documentation is built
  once without Pages/OIDC write permissions and deployed only after every CI
  gate succeeds; only the deploy job receives those permissions.
- Release tags must point to a commit contained in `main` with a successful
  push-triggered CI run before any artifacts can be built or published.
- RustSec vulnerabilities and new warnings are blocking. The audit policy has
  one documented exception for an unmaintained crate reachable only through the
  pinned upstream dependency tree.

### Fixed

- Checkpoint JSON parsing preserves every finite `f64` bit, so save/load cycles
  do not introduce one-ULP posterior drift. `PlayerRating` equality now includes
  `mu`, `sig`, and `update_time_seconds` instead of hiding state differences.
- Manylinux wheel builds install the OpenSSL headers required by the pinned
  upstream dependency tree.

### Removed

- The non-working `endure` system.
- Python 3.10, PyPy, free-threaded, and 32-bit wheel support. Standard CPython
  3.11+ remains supported through one ABI3 wheel per architecture.

## [1.0.3] - 2024-01-28

- Last release from the setuptools-rust/cibuildwheel packaging line.

[Unreleased]: https://github.com/aropan/Elo-MMR-Py/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/aropan/Elo-MMR-Py/compare/v1.0.3...v2.0.0
[1.0.3]: https://github.com/aropan/Elo-MMR-Py/releases/tag/v1.0.3
