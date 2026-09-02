# Current state

## Agent Index

- **Kind:** process
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-09-02
- **Read when:** starting repository work or checking current operational
  status.
- **Search terms:** current state, skeleton, empty package, gate status.

## What matters now

The repository is a freshly created skeleton. It holds the package layout,
gate configuration (Ruff, basedpyright, pytest), and the lightness test, but
no contract has moved here yet. See
[`docs/architecture/00-overview.md`](../architecture/00-overview.md) for the
module layout.

## In-flight work

No contract code has moved. The move is a later task of the `pdomain-ops`
extraction plan
(`docs/plans/2026-09-01-extract-book-contracts-and-retire-pd-repos.md`), which
this repository does not carry a local copy of — read it in `pdomain-ops`.

## Test health

At repository creation, `make ci` passes: Ruff, basedpyright in strict mode,
and the lightness test in `tests/test_torch_free_import.py`. No other tests
exist yet.

## Current risks

None recorded. The package carries no code, so it carries no runtime risk.
