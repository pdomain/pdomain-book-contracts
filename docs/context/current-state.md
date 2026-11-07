# Current state

## Agent Index

- **Kind:** process
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-11-06
- **Read when:** starting repository work or checking current operational
  status.
- **Search terms:** current state, coverage floor, remaining work.

## What matters now

The package holds the shared contracts. The layout and the dependency
boundary are in the
[architecture overview](../architecture/00-overview.md).

## In-flight work

One item is open.

- This package has no coverage floor.
  [Extracted code left its coverage gate behind](../issues/2026-09-02-contracts-code-left-its-coverage-gate-behind.md).

This repository has no plan files.

The index of open issues is
[docs/issues/README.md](../issues/README.md).

## Test health

On 2026-11-06, `uv run pytest` collected 34 tests in `tests/`. They passed.
`make test` runs that same pytest command.

`pyproject.toml` has no coverage setting. The Makefile does not pass a
coverage floor.

Those 34 tests cover:

- the import boundary
- the package version
- bounding-box image-op dispatch
- annotation vocabularies
- region-role mapping
- review metadata

## Current risks

A change in this repository can shrink the tested surface without a coverage
failure here. The open issue is that gap.

This pass did not re-run the `pdomain-book-tools` suite.
