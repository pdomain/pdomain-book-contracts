# Lint-rule Deviations — pdomain-book-contracts

## Agent Index

- **Kind:** process
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-11-06
- **Provenance:** agent-verified against the current suppression inventory.
- **Disposition:** Retained as current intent or process guidance.

This file records standing lint-rule suppressions and per-file overrides.
Each entry names the rule, tool, affected files, and justification. Update
this file whenever a suppression changes.

## Suppressions matched on 2026-11-06

Standing suppressions live in `pyproject.toml`. This list matches that file
on 2026-11-06.

Ruff ignores these rules for the whole package: D100, D104, D105, D107,
D203, D205, D212, E501, PLR2004, TRY003, PLR0911, PLR0912, PLR0913, PLR0915,
and PLC0415.

The file does not comment D100, D104, D105, D107, D203, D205, D212, E501,
PLR2004, or TRY003. PLR2004 is the magic-value comparison rule. TRY003 is
the long exception-message rule.

The commented complexity budget is only PLR0911, PLR0912, PLR0913, and
PLR0915. That budget is for moved functions that already exceed those
limits.

PLC0415 keeps deferred imports, including the version check that picks
`override`.

Ruff per-file ignores:

- `tests/**/*.py`: ANN, D, PLR2004, S101, S108. Tests skip annotation,
  docstring, and assert-style rules.
- `pdomain_book_contracts/geometry/bounding_box.py`: D102, N802. Public
  names such as `minX` stay as they shipped.
- `pdomain_book_contracts/geometry/point.py`: D102, N806. The local name
  `EPS` stays.
- `pdomain_book_contracts/matching/character_groups.py`: RUF012. Enum
  members hold lists.
- `pdomain_book_contracts/sources/pgdp/rounds.py`: D101, D102. Pre-strict
  classes have no docstrings.
- `pdomain_book_contracts/layout/types.py`: D102.
- `pdomain_book_contracts/layout/regions.py`: N806. LTRB locals stay
  uppercase.
- `pdomain_book_contracts/ocr/review.py`: D102.

basedpyright sets `reportUnusedCallResult` to `none`.

Ruff `noqa` comments:

- S603 on `subprocess.run` in `tests/test_torch_free_import.py` and
  `tests/test_bounding_box_image_ops.py`. The argv is a fixed interpreter
  invocation, not a shell command.

Inline `# pyright: ignore` comments:

- `reportUnreachable` on the Python 3.11 `typing_extensions` import in:
  - `pdomain_book_contracts/geometry/point.py`
  - `pdomain_book_contracts/geometry/bounding_box.py`
  - `pdomain_book_contracts/typography/records.py`
  - `pdomain_book_contracts/typography/book_manifest.py`
  - `pdomain_book_contracts/matching/models.py`
  - `pdomain_book_contracts/matching/pgdp_continuations.py`
- `reportAssignmentType` on `RegionType.title` in
  `pdomain_book_contracts/layout/types.py`.
- `reportConstantRedefinition` on the LTRB fields in
  `pdomain_book_contracts/layout/types.py`.
- `reportUnnecessaryIsInstance` in
  `pdomain_book_contracts/ocr/provenance.py`.
- `reportAssignmentType` on `RegionRole.TITLE` in
  `pdomain_book_contracts/annotation/roles.py`.
