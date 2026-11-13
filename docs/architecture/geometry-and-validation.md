---
Status: active
Owner: CT
Created: 2026-11-13
Last verified: 2026-11-13
Kind: architecture
---

# Geometry and input validation

## Agent Index

- **Kind:** architecture
- **Status:** active
- **Owner:** CT
- **Created:** 2026-11-13
- **Last verified:** 2026-11-13
- **Read when:** consuming geometry contracts or validating saved typography records.
- **Search terms:** coordinates, NaN, infinity, artifact path, page key, validation.

Geometry contracts preserve coordinate systems and reject NaN. Typography
contracts validate artifact paths and F2 page keys before accepting saved data.
These checks are part of the shared contracts, not an imaging implementation.

## Coordinate systems remain explicit

`BoundingBox.center` returns a `Point` with the box's `is_normalized` flag.
A pixel box inside the unit square still produces a pixel point.

`BoundingBox.contains_point` raises `ValueError` when the point and box use
different coordinate systems. It includes boundary points when the systems match.
Consumers must supply matching coordinates or handle that exception.

`Point` rejects NaN coordinates during construction and model validation.
Loading a saved document containing a NaN point therefore fails validation.
This check does not reject infinity. An infinite corner can still be constructed;
`BoundingBox.has_usable_coordinates` reports it as unusable.

Two flag problems remain unresolved. `get_four_point_scaled_polygon_list`
scales pixel coordinates as though they were normalized. `from_points` does
not infer its flag from supplied `Point` objects. The
[intent map](../context/intent-map.md) retains these owner decisions and the
question of rejecting infinity.

## Artifact paths and page keys fail validation early

`ArtifactReference` in `typography/exchange.py` rejects raw dot segments such as `./a` and
`a/./b`. Validation checks the input segments before path normalization can
discard them.

Typography records reject a non-string F2 page key with a Pydantic validation error. It does not escape
model validation as an unhandled `TypeError`.

## Evidence

- Code: `pdomain_book_contracts/geometry/point.py`,
  `geometry/bounding_box.py`, `typography/exchange.py`, and
  `typography/records.py` under `pdomain_book_contracts/`.
- Tests: `tests/geometry/test_geometry_bounding_box.py` covers both center
  flags, both mixed-coordinate directions, boundary inclusion, and unusable
  infinite corners. `tests/geometry/test_geometry_point.py` covers NaN
  construction and wire validation. `tests/typography/test_typography_exchange.py`
  covers raw dot segments; `tests/typography/test_typography_records.py`
  covers non-string F2 page keys.
- Commits: `0f1f9c5` preserves the center flag; `88b2cc7` rejects mixed
  coordinates; `c379be3` rejects NaN; `27e1438` rejects dot segments;
  `00c88ae` validates page keys. Merge `175078d` landed this work.
  Regression `b170f54` covers a pixel point on a normalized box.
- Artifacts: no separate data artifact is required by these contracts.
- Verified: source and test inspection on 2026-11-13; baseline
  `uv run pytest -n auto --cov` at `1b1605a` passed 1,324 tests with
  96.92 percent branch coverage. No external consumer suite was run.
