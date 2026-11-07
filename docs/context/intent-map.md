# Intent map

## Agent Index

- **Kind:** process
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-11-06
- **Read when:** checking whether a change is planned, deferred, or rejected
  before starting new work.
- **Search terms:** intent map, deferred work, needs owner decision,
  coverage floor, match type.

## Active work

- This package has no coverage floor. The tests that live here do not
  replace the `pdomain-book-tools` suite. That suite exercises these
  contracts. It does not measure their coverage.
  [Extracted code left its coverage gate behind](../issues/2026-09-02-contracts-code-left-its-coverage-gate-behind.md).

## Deferred work

None recorded.

This repository has no plan files.

## Needs owner decision

- Whether to put back `MatchType.WORD_NEARLY_EQUAL_DUE_TO_PUNCTUATION` and
  `MatchType.LINE_REPLACE_WORD_EQUAL`. Both were removed because nothing in
  the matching pipeline assigned them. The comments in
  `pdomain_book_contracts/matching/match_type.py` say to restore each one
  only when the matching behavior that would assign it exists. No issue
  tracks that work. No plan tracks that work.

## Legacy-unverified sweep

On 2026-11-06 the docgraph issue list had no `legacy_unverified` findings.

Untouched docs were `stale` because their last verified date was 2026-09-02.
