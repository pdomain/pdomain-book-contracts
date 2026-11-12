# Intent map

## Agent Index

- **Kind:** process
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-11-12
- **Read when:** checking whether a change is planned, deferred, or rejected
  before starting new work.
- **Search terms:** intent map, deferred work, needs owner decision,
  coverage floor, match type.

The [roadmap](../plans/roadmap.md) is the list. This page names the bets.
It does not repeat the branch measurements.

## Active work

- This package has no coverage floor. The tests that live here do not
  replace the `pdomain-book-tools` suite. That suite exercises these
  contracts. It does not measure their coverage.
  [Extracted code left its coverage gate behind](../issues/2026-09-02-contracts-code-left-its-coverage-gate-behind.md).
- `feat/coverage-floor` is the unmerged attempt. Do not start another one
  on master.

## Deferred work

- A separate repository for the PGDP readers. `sources/` alone would cycle,
  because it imports `typography` and `layout` while `pgdp_visible.py` would
  import the new package. Moving the four PGDP matching modules as well would
  also cycle. The trigger and the one-way cut are in the roadmap.
- Lazy imports in `sources/pgdp/__init__.py`, so `PGDPExport` does not load
  shapely. Not started. Prefer this before any new repository.

## Needs owner decision

- Whether to put back `MatchType.WORD_NEARLY_EQUAL_DUE_TO_PUNCTUATION` and
  `MatchType.LINE_REPLACE_WORD_EQUAL`. Both were removed because nothing in
  the matching pipeline assigned them. The comments in
  `pdomain_book_contracts/matching/match_type.py` say to restore each one
  only when the matching behavior that would assign it exists. No issue
  tracks that work.
- Whether to move the contracts-only tests out of `pdomain-book-tools`.
- On `feat/coverage-floor`, whether `Point` should also reject infinity,
  and whether to fix `get_four_point_scaled_polygon_list` and `from_points`.
  Those three are recorded in the branch handoff. They are not decisions
  on master.

## Rejected for now

Do not split out annotation, geometry, licensing, text normalization, the
match graph, or the OCR result types. The engine imports PGDP continuations,
so it is not a separable core. The roadmap says why.

## Legacy-unverified sweep

On 2026-11-06 the docgraph issue list had no `legacy_unverified` findings.

Untouched docs were `stale` because their last verified date was 2026-09-02.
