---
kind: archive
status: retired
created_at: "2026-11-11T04:37:40Z"
owner: "CT"
branch: "feat/coverage-floor"
scope: "coverage-floor"
worktree: "/mnt/work/projects/pdomain/pdomain-book-contracts/.worktrees/coverage-floor"
base_commit: "5f5022cfbb367ff58b4db5c85bb5fc0a04fda516"
supersedes: "2026-11-11-032241-coverage-tests-committed-floor-left-at-a-probe-value.md"
handoff_reason: "stopping"
host: "claude-code"
created: "2026-11-11"
last_verified: "2026-11-13"
---

# Coverage floor and geometry fixes committed, branch awaits owner review

> **Retired — shipped behavior is in [Geometry and input validation](../../architecture/geometry-and-validation.md).**

## Goal

Enforce a coverage floor in `make test`, close theme C3 from `pdomain-book-tools`, and find out whether `Point` accepting NaN is a real defect.

## Done

- `47347a6` sets the floor at 95 percent. A deliberately narrow `make test` exited 2 at 28.11 percent, so the floor does fail below 95.
- `0f1f9c5` makes `BoundingBox.center` keep the box's coordinate flag.
- `88b2cc7` makes `BoundingBox.contains_point` raise `ValueError` when the point and box are in different coordinate systems.
- `c379be3` makes `Point` reject NaN. NaN was a real defect: it passed the non-negative check, was labelled pixel, made every `BoundingBox` ordering check pass, and serialized as non-standard JSON. Every other float contract in this package already rejects non-finite values.
- `5f5022c` retires the coverage issue and updates current state, the intent map, the architecture overview, `README.md`, `AGENTS.md` and `CONVENTIONS.md`.
- The fixes were written test-first. One independent review of the geometry changes returned no findings. The readability editor reviewed the changed prose and changed nothing.

## Not done

- `pdomain-book-tools` issue `docs/issues/2026-07-21-geometry-primitive-flag-hygiene.md` is still open, because this session worked only in this repository. Retire it after book-tools takes this change.
- `pdomain-book-tools` test `test_bounding_box_contains_point` passes a pixel point to a normalized box. It will fail once book-tools takes this change, and must then use a normalized point or expect `ValueError`.
- The `pdomain-book-tools` suite was not run against these changes.
- Nothing has been pushed, merged, tagged, released or deployed.

## Failed approaches

- `git commit` in this worktree fails with `pre-commit not found` outside the virtualenv. `uv run git commit` runs the hooks.
- The docgraph MCP handoff tools read the main checkout unless `repo` names the worktree.

## Decisions

Owner decisions, recorded in `docs/context/intent-map.md` and skipped:

- Whether `Point` should also reject infinity. It stays accepted because `test_infinite_corner_is_not_usable` constructs an infinite corner and the task covered NaN only.
- Whether to fix two more `is_normalized` weaknesses found by the audit the book-tools issue asked for. `get_four_point_scaled_polygon_list` scales a pixel box as if it were normalized. `from_points` drops the flag of `Point` inputs.
- Whether to move the contracts-only tests out of `pdomain-book-tools`.

Decisions taken here, for the owner to check at review:

- The coverage issue was kept in place with status `retired`, not deleted, because `CONVENTIONS.md` links to its 2026-09-02 measurement.
- `CONVENTIONS.md` lost the instruction not to add a floor until enough tests lived here, because that condition is now met. The edit is inside the `workspace-conventions` block, so a later sync of that block could undo it.
- `Point` rejecting NaN means a saved document with a NaN coordinate now fails to load. Stored data was not scanned for NaN. The fix is alone in `c379be3`, so it can be reverted by itself.

## State

Ten commits ahead of master on `feat/coverage-floor` before this handoff commit, with a clean tree. `make ci AI=1` exited 0 on `5f5022c`, measured directly and not through a pipe: 1,323 tests passed on Python 3.13 at 96.92 percent. `docgraph check --strict` printed one advisory about `CODEX.md`. Only Python 3.13 was run this session. All work ran on CPU with the GPU hidden.

## Pointers

- `docs/context/intent-map.md`
- `docs/context/current-state.md`
- `docs/issues/2026-09-02-contracts-code-left-its-coverage-gate-behind.md`
- `pdomain_book_contracts/geometry/bounding_box.py`
- `pdomain_book_contracts/geometry/point.py`
- `tests/geometry/test_geometry_bounding_box.py`
- `tests/geometry/test_geometry_point.py`

## Resume steps

1. Review the commits on `feat/coverage-floor` and merge them when satisfied.
2. Answer the three owner decisions in `docs/context/intent-map.md`.
3. After a contracts release, update `test_bounding_box_contains_point` in `pdomain-book-tools`, run that suite, and retire its geometry issue.
