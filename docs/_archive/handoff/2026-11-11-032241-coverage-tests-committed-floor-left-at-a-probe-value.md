---
kind: archive
status: retired
created_at: "2026-11-11T03:22:38Z"
owner: "CT"
branch: "feat/coverage-floor"
scope: "coverage-floor"
worktree: "/mnt/work/projects/pdomain/pdomain-book-contracts/.worktrees/coverage-floor"
base_commit: "00c88ae9e91f9a2123a54bb5f4442575c46f56c8"
handoff_reason: "user_requested"
host: "claude-code"
created: "2026-11-11"
last_verified: "2026-11-11"
---

# Coverage tests committed, floor left at a probe value

> **Retired — superseded by `docs/handoff/2026-11-11-043740-coverage-floor-and-geometry-fixes-committed.md`.**

The successor is now the [archived merged coverage handoff](2026-11-11-043740-coverage-floor-and-geometry-fixes-committed.md).

## Goal

Add the missing coverage floor so `make test` enforces it.

## Done

- Behaviour tests across every module are committed (`2bd0bcb`). Baseline was 55% from 79 tests. The session measured 96.90% with branch coverage and 1,312 passing tests on Python 3.11 to 3.13.
- Three bugs the tests exposed are fixed test-first: PGDP `N` diacritics (`4f43a82`), dot segments in artifact paths (`27e1438`), and a non-string F2 page key (`00c88ae`).

## Not done

- The floor is uncommitted, in `Makefile`, `pyproject.toml` and `uv.lock`.
- **`fail_under` currently reads 100 in `pyproject.toml`.** The session said it was setting the floor at 95 and checking that `make test` fails below it, and was interrupted during that check. Set it to 95 before committing.
- `make ci AI=1` has no recorded pass with the floor in place.
- The issue is not retired and `docs/context/current-state.md` still has the old test count.
- A session reported that `Point` accepts NaN coordinates and planned to check it. No outcome is recorded.
- `BoundingBox.center` and `contains_point` still weaken the `is_normalized` rule. `pdomain-book-tools` left theme C3 open because the code is here.

## Failed approaches

- Four Python 3.12 test errors came from the `/tmp` quota, not the code.

## Decisions

- A floor of 95, below the measured 96.90%, was the session's choice.

## State

Four commits ahead of master, with three modified files. The owner paused this work on 2026-11-10 and the session's herdr tab is closed. Nothing was pushed, merged, tagged, released or deployed. All work ran on CPU with the GPU hidden. The session's last terminal output is saved in `/mnt/work/projects/pdomain/.artifacts/handoff-20261110/session-output/`. `/tmp` is a shared tmpfs that ran out of quota several times on 2026-11-10 while ten sessions ran gates. If a gate fails with a quota error, point `TMPDIR` at the work drive and rerun before suspecting the code.

## Pointers

- `/mnt/work/projects/pdomain/.artifacts/handoff-20261110/contracts-coverage.patch`
- `docs/issues/2026-09-02-contracts-code-left-its-coverage-gate-behind.md`
- `docs/context/current-state.md`

## Resume steps

1. Set `fail_under = 95`.
2. Confirm `make test` fails when coverage drops below the floor.
3. Run `make ci AI=1` and commit.
4. Retire the issue and update current-state.
