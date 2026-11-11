# Intent map

## Agent Index

- **Kind:** process
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-11-10
- **Read when:** checking whether a change is planned, deferred, or rejected
  before starting new work.
- **Search terms:** intent map, deferred work, needs owner decision,
  coverage floor, match type.

## Active work

None recorded.

## Deferred work

None recorded.

This repository has no plan files.

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
  tracks that work. No plan tracks that work.

## Legacy-unverified sweep

On 2026-11-06 the docgraph issue list had no `legacy_unverified` findings.

Untouched docs were `stale` because their last verified date was 2026-09-02.
