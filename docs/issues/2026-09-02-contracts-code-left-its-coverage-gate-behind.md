---
Status: open
Owner: CT
Created: 2026-09-02
Last verified: 2026-11-07
Kind: issue
---

# Extracted code left its coverage gate behind

## Agent Index

- **Kind:** issue
- **Status:** open
- **Owner:** CT
- **Last verified:** 2026-11-07
- **Read when:** adding a coverage gate here, or moving tests out of `pdomain-book-tools`.
- **Search terms:** coverage, test ownership, extraction, 87 percent floor, site-packages.

## Summary

About 13,000 lines moved out of `pdomain-book-tools`, which enforces an 87 percent coverage
floor, into this repository, which has no coverage gate at all. The tests did not move with
the code, so nothing measures or enforces coverage of it any more.

## Impact

A change here can drop the tested surface of the shared contracts with no signal. The number
that looks like it covers this code, book-tools' 89.84 percent, does not include a line of
it.

Book-tools exercises these contracts through re-export shims. Its September run had
2,918 tests. That count does not establish coverage of every contract. The gap is in
measurement and enforcement.

## Environment / versions

`pdomain-book-contracts` v0.1.0, `pdomain-book-tools` v0.27.0, measured 2026-09-02.

## Evidence

Verified on 2026-11-07:

- `uv run pytest -q` passed all 34 tests in this repository.
- This repository's `pyproject.toml` and Makefile configure no coverage measurement or floor.
- Book-tools' `pyproject.toml` measures only `pdomain_book_tools` and sets an 87 percent floor.
  Its `.coveragerc.cpu` also measures only that package and excludes `*/site-packages/*`.
- Book-tools' `geometry/point.py` still re-exports the contracts `Point` type.

The measurements below are from 2026-09-02. Coverage was not remeasured, and the
book-tools suite was not rerun during the November check.

| what | number |
| --- | ---: |
| this package's own tests | 12 |
| coverage from those tests alone | 36 percent |
| statements in this package | 6,193 |
| book-tools coverage, unchanged | 89.84 percent over 9,753 statements |

The book-tools run reports 9,753 statements and mentions no file from this package. Its
pytest `addopts` names `--cov=pdomain_book_tools` and nothing else.

The 36 percent is flattering. Much of it is class and constant definitions executed at
import time by the lightness test, not behaviour anyone asserted here.

## Root-cause hypotheses

The extraction moved code without moving the tests that covered it, and coverage
configuration in both repositories names packages explicitly, so neither repository noticed.
Book-tools kept measuring only itself, and this repository never had a floor to lose.

## Defects to fix

- This package enforces no coverage floor.
- The September baseline was 12 tests reaching 36 percent, much of it import-time
  execution. The current 34-test suite has no measured coverage baseline.
- Book-tools' coverage figure excludes this package while appearing to cover the moved code.

## What is NOT broken

The September book-tools run passed 2,918 tests. This issue records a coverage gap,
not a demonstrated consumer failure or defective release. A passing suite alone
does not establish that every moved contract is tested.

## Dependencies

Moving tests out of book-tools depends on separating tests that exercise contracts alone
from those that exercise contracts and the OCR engine together. That separation does not
exist yet.

## Outcome / acceptance criteria

This package enforces its own coverage floor over tests that live here, and the floor is
set from a measured baseline rather than chosen to pass.

## Next steps

1. Decide whether this package owns its own tests.
2. If it does, move the contracts-only tests out of book-tools and leave the ones that
   genuinely span both.
3. Set a floor here once enough tests have moved for the number to mean something. Setting
   one now would either fail immediately or be set so low it asserts nothing.

## Resolution

Open. Nothing was changed in either repository.

Adding `pdomain_book_contracts` to book-tools' coverage sources was tried and rejected.
Measured that way the combined suite reports 88.2 percent, above the floor, but
`.coveragerc.cpu` omits `*/site-packages/*` and this package is now an installed wheel
there, so the omit would have to go and take every third-party dependency's exclusion with
it. It is also the wrong shape: book-tools consumes this package as a released dependency,
and a consumer measuring its dependency's coverage produces a number that moves when the
consumer's tests change.
