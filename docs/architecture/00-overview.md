# Overview

## Agent Index

- **Kind:** architecture
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-09-02
- **Read when:** orienting on the package's purpose, dependency boundary, or
  module layout before adding a contract.
- **Search terms:** book contracts, geometry, typography, matching, ocr,
  layout, pgdp, dependency boundary, lightness test.

`pdomain-book-contracts` holds the pure-Python contracts shared across the
`pdomain-*` OCR suite: value types, typography and matching algorithms, OCR
result types, layout contracts, and the PGDP round readers. Its dependency
set is pydantic, pydantic-core, shapely, and regex — nothing that needs an
imaging or ML stack.

## Current status

The package is an empty skeleton. Each subpackage exists with an
`__init__.py` docstring naming what it will own; no contract has moved here
yet. `tests/test_torch_free_import.py` enforces the dependency boundary in a
subprocess, independent of whatever code eventually fills the package.

## Module layout

```text
pdomain_book_contracts/
    geometry/        point.py, bounding_box.py
    text/            normalization.py, label_normalization.py, text_normalize.py
    typography/      labels.py, spans.py, records.py, annotations.py,
                     exchange.py, book_manifest.py, review.py
    matching/        alignment.py, engine.py, models.py, legacy_projection.py,
                     pgdp_continuations.py, match_type.py, character_groups.py
    ocr/             character.py, glyph_annotations.py, provenance.py,
                     review.py, gt_orphans.py, blob_protocol.py
    layout/          types.py, regions.py
    sources/pgdp/    rounds.py, offsets.py,
                     f2/{tokens,parser,project_rules,warnings}.py
    licensing.py
    _schemas.py
```

Dependencies flow one way, top to bottom: `geometry`, `text`, and
`_schemas` depend on nothing internal; `typography` depends on `geometry`,
`text`, and `_schemas`; `matching` depends on `geometry`, `text`, and
`typography`; `ocr` depends on `geometry` and `typography`; `layout`
depends on `geometry`; `sources/pgdp` depends on `typography` and `text`;
`licensing` depends on nothing internal. A module may not import from a
package below it in that order.

The full rationale for this layout lives in the `pdomain-ops` book-contracts
module layout spec
(`docs/specs/2026-09-02-book-contracts-module-layout.md`).

## Dependency direction with `pdomain-book-tools`

`pdomain-book-tools` depends on this package and re-exports its names, so
existing imports through `pdomain-book-tools` keep working after the code
moves. Nothing in this package may depend on `pdomain-book-tools`.
