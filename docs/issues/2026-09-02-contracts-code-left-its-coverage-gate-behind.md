---
Status: open
Owner: CT
Created: 2026-09-02
Last verified: 2026-09-02
Kind: issue
---

# Extracted code left its coverage gate behind

## Agent Index

- **Kind:** issue
- **Status:** open
- **Owner:** CT
- **Last verified:** 2026-09-02
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

The code is still exercised. Book-tools runs 2,918 tests against it through the re-export
shims on every gate. This is a gap in enforcement and measurement, not evidence of untested
code.

## Environment / versions

`pdomain-book-contracts` v0.1.0, `pdomain-book-tools` v0.27.0, measured 2026-09-02.

## Evidence

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
- Its 12 tests reach 36 percent, most of it import-time execution rather than asserted
  behaviour.
- Book-tools' coverage figure excludes this package while appearing to cover the moved code.

## What is NOT broken

Nothing is untested as a result of this. The moved code passes 2,918 tests on every
book-tools gate run. No consumer is affected, and no released artifact is wrong.

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
