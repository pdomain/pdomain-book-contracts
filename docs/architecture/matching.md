---
Status: active
Owner: CT
Created: 2026-11-12
Last verified: 2026-11-12
Kind: architecture
---

# Matching

## Agent Index

- **Kind:** architecture
- **Status:** active
- **Owner:** CT
- **Created:** 2026-11-12
- **Last verified:** 2026-11-12
- **Read when:** changing the match graph, alignment, legacy projection, or a PGDP matching adapter.
- **Search terms:** matching, MatchGraph, alignment, MatchType, PGDP bounded match, layout projection.

Matching aligns two texts into a `MatchGraph`.

The match models do not import PGDP types. The engine does. `match_documents` takes `pgdp_continuations`. `engine.py` imports `PgdpContinuation` and `build_pgdp_surface_document` from `pgdp_continuations.py`.

Four modules know PGDP markup. `matching/__init__.py` exports the continuation decoder. It does not export the other three.

`pdomain-book-tools` re-exports this package. The tools package does not own a second matcher.

## Match graph and engine

`models.py` is the graph: documents, pages, lines, tokens, relations, operations, policy, quarantine reasons, and search evidence.

`engine.py` exposes `match_documents`. The continuation argument defaults to an empty tuple. The graph model stays free of PGDP types. The engine file itself is not free of them.

`alignment.py` exposes `align_tokens` and the projection of style spans and token ranges onto the aligned text. `AlignmentConfig` lives here, not under `typography`.

`alignment.py` and `legacy_projection.py` do not import the PGDP modules.

`legacy_projection.py` turns a legacy page into a match document and projects a graph back onto that page. It does not import `Block`, `Page`, or `Word` from `pdomain-book-tools`. Those names stay behind the tools package. The projection uses module-private protocols so this package type-checks alone.

`character_groups.py` is matching vocabulary.

`match_type.py` is the older line and word classification.

## Match types that are absent

`MatchType` has nine members:

- `WORD_EXACTLY_EQUAL`
- `LINE_EQUAL`
- `LINE_REPLACE`
- `LINE_DELETE`
- `LINE_INSERT`
- `LINE_REPLACE_WORD_REPLACE`
- `LINE_REPLACE_WORD_REPLACE_COMBINED`
- `LINE_REPLACE_WORD_DELETE`
- `LINE_REPLACE_WORD_INSERT`

`WORD_NEARLY_EQUAL_DUE_TO_PUNCTUATION` and `LINE_REPLACE_WORD_EQUAL` are not members. Comments in `match_type.py` say each was removed because nothing in the pipeline assigned it.

Restoring either one is an owner decision, recorded in the [roadmap](../plans/roadmap.md).

## PGDP adapters

These four modules sit in `matching` because they produce or consume a `MatchGraph`. They are the part of this package that knows PGDP rounds.

`pgdp_continuations.py` decodes words split across a page break. `matching/__init__.py` exports `decode_pgdp_continuations` and `build_pgdp_surface_document`.

`pgdp_visible.py` builds a match document from visible PGDP or OCR words. It keeps physical words and the original source slices. It imports `tokenize_f2`. This is the matching module that depends on `sources/pgdp`.

`pgdp_bounded.py` matches long pages by anchors instead of one unbounded comparison. Unique exact anchors bound the work. Repeated text is not an anchor.

A residual that runs out of budget stays explicit.

`pgdp_layout_projection.py` composes F2, P3, and OCR matches and projects F2 formatting onto the composed graphemes. Formatting is projected only for exact composed graphemes. It imports `LayoutTextHint`.

Import `pgdp_bounded`, `pgdp_visible`, and `pgdp_layout_projection` from their modules. They are not in `matching/__init__.py`.

`pgdp_bounded.py` calls `match_documents`. `engine.py` does not import `pgdp_bounded.py`.
