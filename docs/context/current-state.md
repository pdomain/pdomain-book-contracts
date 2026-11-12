# Current state

## Agent Index

- **Kind:** process
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-11-12
- **Read when:** starting repository work or checking current operational
  status.
- **Search terms:** current state, coverage floor, remaining work.

## What matters now

The package holds the shared contracts. The layout and the dependency
boundary start at the
[architecture overview](../architecture/00-overview.md).

## In-flight work

Open work is the [roadmap](../plans/roadmap.md). The one open issue is the
missing coverage floor.
[Extracted code left its coverage gate behind](../issues/2026-09-02-contracts-code-left-its-coverage-gate-behind.md).

`feat/coverage-floor` holds an unmerged 95 percent floor and three geometry
fixes. Do not start a second attempt on master. The roadmap has the branch
facts.

The index of open issues is
[docs/issues/README.md](../issues/README.md).

## Test health

On 2026-11-06, `uv run pytest` collected 34 tests in `tests/`. They passed.
On 2026-11-12 the collector listed 79 tests, and `uv run pytest` exited 0.
`make test` runs that same pytest command.

`pyproject.toml` has no coverage setting. The Makefile does not pass a
coverage floor.

The 79 tests cover the 34, plus layout text hints, F2 structure, and the
PGDP matching adapters. The earlier 34 cover:

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
