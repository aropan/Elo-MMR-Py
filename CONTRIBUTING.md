# Contributing to Elo-MMR-Py

Thank you for improving Elo-MMR-Py. Keep algorithm changes separate from binding,
packaging, and documentation changes so exact-rating parity is easy to review.

## Setup

Follow the canonical [development environment and check instructions](docs/development.md).
Do not update `Cargo.lock` or `uv.lock` incidentally; update them only with the
corresponding manifest change.

## Pull requests

- Add a focused regression test for behavior changes.
- Preserve the exact default `mmr` golden history unless an algorithm change is
  explicitly proposed and justified.
- Add or update type annotations and user-facing documentation with API changes.
- Run the checks listed in the development guide linked above.
- Benchmark performance-sensitive changes in a release build on the same machine
  as the baseline.
- Keep checkpoints backward-readable unless the change is documented as a new
  format version and includes a migration path.

## Commit and changelog style

Use focused commits with imperative subjects. Add user-visible changes to the
`Unreleased` section of `CHANGELOG.md`. Do not include generated build artifacts,
benchmark output, or virtual environments.

By contributing, you agree that your contribution is licensed under the MIT
license in this repository.
