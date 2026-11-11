# Current state

## Agent Index

- **Kind:** process
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-11-10
- **Read when:** starting repository work or checking current operational
  status.
- **Search terms:** current state, coverage floor, remaining work.

## What matters now

The package holds the shared contracts. The layout and the dependency
boundary are in the
[architecture overview](../architecture/00-overview.md).

## In-flight work

No issue is open. The coverage floor is in place, which closed
[Extracted code left its coverage gate behind](../issues/2026-09-02-contracts-code-left-its-coverage-gate-behind.md).

This repository has no plan files.

The index of issues is
[docs/issues/README.md](../issues/README.md).

## Test health

On 2026-11-10, `make test` ran 1,323 tests in `tests/` on Python 3.13. They
passed and measured 96.92 percent with branch coverage.

`make test` runs `pytest --cov`. `pyproject.toml` sets the floor at 95 percent,
so the command fails below that. The tests cover behaviour in every module.

## Current risks

Coverage can fall from 96.92 percent to the 95 percent floor without a failure.

`BoundingBox.contains_point` now raises `ValueError` when the point and the box
are in different coordinate systems. The `pdomain-book-tools` test
`test_bounding_box_contains_point` passes a pixel point to a normalized box, so
it will fail once that repository takes this change.

`Point` now rejects NaN, so a saved document with a NaN coordinate fails to load.

This pass did not re-run the `pdomain-book-tools` suite.
