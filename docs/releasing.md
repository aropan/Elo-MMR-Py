# Releasing

Releases use a tag-only GitHub Actions workflow and PyPI Trusted Publishing.
There is no manual workflow-dispatch publishing path and no long-lived PyPI
token.

## One-time repository setup

1. In GitHub Pages settings, select **GitHub Actions** as the source.
2. In PyPI, register this repository, the release workflow filename, and the
   `pypi` environment as a Trusted Publisher.
3. Restrict the `pypi` environment deployment policy to release tags matching
   `v*.*.*`.

## Release checklist

1. Update the package version in `Cargo.toml`; Python package metadata derives
   it through Maturin. Move the relevant changelog entries from `Unreleased`
   into exactly one `## [X.Y.Z] - YYYY-MM-DD` section and update the comparison
   links.
2. Run all commands from [Development](development.md#required-checks).
3. Review the deterministic benchmark against the previous release on the same
   machine.
4. Merge the release preparation to `main` and wait for the CI workflow,
   including documentation deployment, to succeed.
5. Create and push an annotated `vX.Y.Z` tag.

The workflow first requires the tagged commit to be contained in `main` and to
have a successful push-triggered CI run for the exact same SHA. It compares the
tag with the canonical Cargo version and rejects a missing or duplicate dated
changelog section, an invalid date, or a future date. It builds five ABI3
wheels plus one source distribution, installs and tests each artifact on its
native runner, and publishes only after every build passes. The PyPI job
authenticates with GitHub OIDC.

CPython 3.11–3.14 wheel compatibility is part of regular CI. A scheduled workflow
checks the latest CPython 3.15 prerelease separately so prerelease availability
cannot block ordinary changes.
