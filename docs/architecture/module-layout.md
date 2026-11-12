---
Status: active
Owner: CT
Created: 2026-11-12
Last verified: 2026-11-12
Kind: architecture
---

# Module layout

## Agent Index

- **Kind:** architecture
- **Status:** active
- **Owner:** CT
- **Created:** 2026-11-12
- **Last verified:** 2026-11-12
- **Read when:** deciding which subpackage owns a new contract, or checking an import edge.
- **Search terms:** module layout, import direction, subpackages, dependency boundary.

The package is one distribution with nine areas. The import edges below were read from the Python source on 2026-11-12.

A few package docstrings still name older edges. Those docstrings are listed at the end.

Runtime dependencies come from `pyproject.toml`:

- `pydantic>=2.13,<3`
- `pydantic-core>=2.46,<3`
- `regex>=2024.11.6,<2025.0.0`
- `shapely>=2.1,<3`
- `typing-extensions>=4.16,<5`

Python is `>=3.11,<3.14`.

## What each area owns

```text
pdomain_book_contracts/
    geometry/        point.py, bounding_box.py
    text/            label_normalization.py, text_normalize.py
    annotation/      roles.py, page_kind.py, provenance.py, mappings.py
    typography/      labels.py, spans.py, normalization.py, records.py,
                     annotations.py, exchange.py, book_manifest.py, review.py
    matching/        alignment.py, engine.py, models.py, legacy_projection.py,
                     pgdp_continuations.py, pgdp_bounded.py, pgdp_visible.py,
                     pgdp_layout_projection.py, match_type.py,
                     character_groups.py
    ocr/             character.py, glyph_annotations.py, provenance.py,
                     review.py, gt_orphans.py, blob_protocol.py
    layout/          types.py, regions.py, text_hints.py
    sources/pgdp/    rounds.py, offsets.py,
                     f2/{tokens,parser,project_rules,warnings,structure}.py
    data/            spdx_licenses.json
    licensing.py
    _schemas.py
```

`data` has no runtime code. `licensing.py` reads `data/spdx_licenses.json` through `importlib.resources`.

`_schemas.py` holds shared pydantic-core schema fragments. It is not a public API.

`geometry` is the only code that imports shapely. `bounding_box.py` imports `numpy.ndarray` only under `TYPE_CHECKING`.

`text` imports the standard library only.

`layout` does not import `geometry`.

A `LayoutRegion` stores pixel edges as plain integers named `L`, `R`, `T`, and `B`.

`annotation` owns the shared words:

- 34 `RegionRole` values
- 8 aliases
- 14 `PageKind` values
- the provenance enums `LabelSource`, `KnowledgeState`, and `ConfidenceTier`

`mappings.py` is the one-way map from a detector `RegionType` to a `RegionRole`.

`typography` owns the labeling records, the review and exchange bundles, and grapheme segmentation.

`normalization.py` stays here. It uses typography's own labels and spans. An earlier move into `text` created an import cycle.

`matching` owns token alignment, the match graph, and the legacy page projection. Four modules are PGDP-specific: `pgdp_continuations.py`, `pgdp_bounded.py`, `pgdp_visible.py`, and `pgdp_layout_projection.py`.

`ocr` owns OCR result values: a character, glyph annotations, provenance, review metadata, ground-truth orphans, and the blob-store protocol.

`sources/pgdp` owns the round container and the F2 markup reader. There is no `p3` module. P3 text has no markup, so the shared container is enough.

## How the areas import each other

These edges are imports from one area to another. Imports inside an area are left out.

```text
_schemas, text, layout     no other area
licensing                  reads data/spdx_licenses.json, no Python import of another area
geometry                   _schemas
annotation                 layout
typography                 geometry, annotation
ocr                        _schemas, geometry, text, annotation
sources/pgdp               layout, typography
matching                   geometry, layout, typography, sources/pgdp
```

`annotation/__init__.py` imports `mappings.py`, and `mappings.py` imports `layout.types`. Importing `annotation` or `annotation.roles` therefore loads `layout`.

On 2026-11-12 that import did not load shapely or numpy.

`sources/pgdp/__init__.py` imports `f2`. Importing `PGDPExport` from `rounds.py` therefore loads the F2 parser, the typography package, `geometry`, shapely, and numpy. That was measured on 2026-11-12 by importing `pdomain_book_contracts.sources.pgdp.rounds`.

`rounds.py` itself imports `regex` only.

`matching` reaches `sources/pgdp` from `pgdp_visible.py`, which imports `tokenize_f2`.

`matching` reaches `layout` from `pgdp_layout_projection.py`, which imports `LayoutTextHint`.

The package root imports the version and nothing else. Importing `pdomain_book_contracts` does not load the areas above.

## What layout and matching do not export

`layout/__init__.py` exports region types and region helpers. Text-hint types are imported from `pdomain_book_contracts.layout.text_hints`.

`matching/__init__.py` exports the engine, the match models, alignment, legacy projection, and PGDP continuations. `pgdp_bounded`, `pgdp_visible`, and `pgdp_layout_projection` are imported from their own modules.

## Docstrings that name the wrong edges

The code above is the source of truth. These package docstrings still describe an older graph.

- `layout/__init__.py` says the package depends only on `geometry`. It does not import `geometry`.
- `typography/__init__.py` says the package depends only on `geometry` and `_schemas`. The live edges are `geometry` and `annotation`. Nothing under `typography/` imports `_schemas`.
- `matching/__init__.py` says the package depends on `geometry`, `text`, and `typography`. The live edges add `layout` and `sources/pgdp`. No file under `matching/` imports `text`.
- `ocr/__init__.py` says the package depends on `geometry` and `text`. It also imports `_schemas` and `annotation`.
- `sources/pgdp/__init__.py` and `sources/pgdp/f2/__init__.py` say the readers depend on `typography` and `text`. The live edges are `layout` and `typography`. No file under `sources/` imports `text`.
- `annotation/__init__.py` says the vocabulary knows nothing about the page model. `mappings.py` imports `RegionType`.
- `tests/test_torch_free_import.py` says only `geometry` needs shapely. It names `typography`, `matching`, `ocr`, and `sources.pgdp` among the subpackages that do not import it. Those four load shapely when imported on their own, because they reach `geometry`. The test still passes. It imports `geometry` in the same process, so it cannot see which later import would have loaded shapely by itself.
