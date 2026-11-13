# Intent map

## Agent Index

- **Kind:** process
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-11-13
- **Read when:** checking whether a change is planned, deferred, or rejected
  before starting new work.
- **Search terms:** intent map, deferred work, needs owner decision,
  coverage floor, match type.

The [roadmap](../plans/roadmap.md) is the list. This page names the bets.
It does not repeat the branch measurements.

## Active work

None recorded.

The coverage and geometry branch merged in `175078d`. Its branch-review
handoff is retired; the [geometry architecture](../architecture/geometry-and-validation.md)
holds the shipped behavior. Retirement closes those resume instructions,
not the deferred work or owner decisions below.

## Deferred work

- A separate repository for the PGDP readers. `sources/` alone would cycle,
  because it imports `typography` and `layout` while `pgdp_visible.py` would
  import the new package. Moving the four PGDP matching modules as well would
  also cycle. The trigger and the one-way cut are in the roadmap.
- Lazy imports in `sources/pgdp/__init__.py`, so `PGDPExport` does not load
  shapely. Not started. Prefer this before any new repository.

## Needs owner decision

- Whether `Point` should reject infinity as it now rejects NaN. Infinity is
  still accepted, and `BoundingBox.has_usable_coordinates` exists to catch it.
  A saved `+inf` coordinate also serializes as non-standard JSON.
- Whether to fix two more places that weaken the `is_normalized` rule.
  `BoundingBox.get_four_point_scaled_polygon_list` scales a pixel box as if it
  were normalized. `BoundingBox.from_points` drops the flag of `Point` inputs,
  so two pixel points inside the unit square make a normalized box.
- Whether to move the contracts-only tests out of `pdomain-book-tools`. The
  [retired coverage issue](../issues/2026-09-02-contracts-code-left-its-coverage-gate-behind.md)
  left this open, and the coverage floor did not need it.
- Whether to put back `MatchType.WORD_NEARLY_EQUAL_DUE_TO_PUNCTUATION` and
  `MatchType.LINE_REPLACE_WORD_EQUAL`. Both were removed because nothing in
  the matching pipeline assigned them. The comments in
  `pdomain_book_contracts/matching/match_type.py` say to restore each one
  only when the matching behavior that would assign it exists. No issue
  tracks that work.

## Rejected for now

Do not split out annotation, geometry, licensing, text normalization, the
match graph, or the OCR result types. The engine imports PGDP continuations,
so it is not a separable core. The roadmap says why.

## Legacy-unverified sweep

On 2026-11-06 the docgraph issue list had no `legacy_unverified` findings.

Untouched docs were `stale` because their last verified date was 2026-09-02.
