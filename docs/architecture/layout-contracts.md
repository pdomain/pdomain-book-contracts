---
Status: active
Owner: CT
Created: 2026-11-12
Last verified: 2026-11-12
Kind: architecture
---

# Layout contracts

## Agent Index

- **Kind:** architecture
- **Status:** active
- **Owner:** CT
- **Created:** 2026-11-12
- **Last verified:** 2026-11-12
- **Read when:** changing region types, the role map, text hints, or reviewed layout structure.
- **Search terms:** layout, RegionType, LayoutRegion, text hints, LayoutStructure, page number, figure.

A layout region, a text hint, and reviewed structure are not the same object.

A layout region is a detector's pixel rectangle.

A text hint is source evidence that a span might be poetry, a table, or another textual role.

Reviewed structure is a third record. A person has confirmed the role and bound it to word ids.

## Detector regions

`RegionType` has 15 values:

- `text`
- `title`
- `section`
- `list`
- `table`
- `figure`
- `decoration`
- `caption`
- `header`
- `footer`
- `footnote`
- `formula`
- `abandoned`
- `sidenote`
- `page_number`

`LayoutRegion` stores that type, integer edges `L`, `R`, `T`, and `B`, a confidence, and the detector's raw label.

`PageLayout` is the list of regions plus the image size, the detector name, and the inference time.

Coordinates stay in the source image's pixel frame. They are not `Point` or `BoundingBox` values.

`regions.py` is the adjacency helper. It provides `iou`, `contains`, `horizontal_overlap_ratio`, `caption_for_figure`, and `region_reading_order`.

Intersection-over-union is 0 when either rectangle has zero width or zero height, including two identical zero-area boxes.

`layout/__init__.py` exports these region types and helpers. It does not export the text-hint types.

The distribution root, `pdomain_book_contracts/__init__.py`, exports only the version.

## Roles stay separate from detector labels

`annotation/mappings.py` maps each `RegionType` to one `RegionRole`. The map is one way. `RegionType` stays the detector's word. `RegionRole` stays what a person meant.

A page number stays a page number. `page_number` maps to `PAGE_NUMBER`. `footer` maps to `PAGE_FOOTER`.

Figure and illustration stay distinct. `figure` maps to `FIGURE`. Illustration is a role rather than a `RegionType`.

## Text hints and reviewed structure

`layout/text_hints.py` holds both records.

A `LayoutTextHint` is evidence. Its kind is `poetry`, `blockquote`, `table_candidate`, `column_flow`, or `formatted_block`. Its source is `f2` or `gutenberg_html`. It carries the visible text, lines, a source reference, optional grapheme and byte ranges, attributes, table rows, and warnings.

A formatted block is evidence. It is not a confirmed structure.

A `LayoutStructure` is the reviewed form. Its kind is `poetry`, `blockquote`, `table`, or `column_flow`.

A nonempty line or table cell must carry prepared-bundle word ids.

Word signatures are snapshots. They are not extra join keys.

Measured indents must be finite.

This package accepts a hint whose source is `gutenberg_html`. It does not ship a Gutenberg parser.

The F2 producer is `layout_hints_from_tokens` in `sources/pgdp/f2/structure.py`. It reads lossless F2 tokens and emits `LayoutTextHint` values.

A marker that falls inside a grapheme produces no hint.

An unclosed table does not swallow the text that follows it.
