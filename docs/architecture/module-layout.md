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

The package is one distribution with nine areas. This page is the layout description. The same writeup still sits in `pdomain-ops` at `docs/specs/2026-09-02-book-contracts-module-layout.md`. That copy is the 2026-09-02 extraction design, rechecked there on 2026-11-07. The tree and the import edges here were read again from the Python source on 2026-11-12.

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

## Why the areas are split this way

The extraction grouped each module by what it is responsible for. The spec measured 12,998 lines then. It did not group files by the package that had held them.

Four moves were deliberate. Everything else kept its name.

Alignment lives in `matching`. `typography/alignment.py` was 812 lines, and it aligns two texts, so it moved beside the matching engine. It had sat in `typography` only because typography was its first consumer. `match_type.py` and `character_groups.py` came from `ocr` with it. They are matching vocabulary, not OCR results.

`text` holds transformations that import only the standard library. `ocr/text_normalize.py` and `ocr/label_normalization.py` moved there.

`typography/normalization.py` stayed. An earlier draft moved it to `text` on the grounds that it was not about typography specifically. That was wrong. The move created an import cycle that failed at run time with a partially initialized module. `normalization.py` imports `KnowledgeState` and `StyleLabel` from `typography/labels.py`. It also imports `CanonicalModel`, `StyleSpan`, and `split_graphemes` from `typography/spans.py`. `typography/records.py` imports `ComparisonOperation` back from it. The module is built from typography vocabulary, so it stays in `typography`.

The round container is separate from F2 markup. `offsets.py` contains no F2 markup. It reads the round JSON, a JSON object that maps page keys to page text, and it tracks byte offsets into that text. Every PGDP round shares that container. Only the markup inside differs. When the spec was written, `pdomain-source-data` already read P3 with `read_lexical_f2_index` and `read_lexical_f2_page`, then compared the two rounds to decode words split across a page break. The functions were named for F2 and used for P3. `offsets.py` now sits beside `rounds.py`. The functions are `read_lexical_index`, `read_lexical_page`, and `read_lexical_json`. The types are still named `LexicalF2Index` and `LexicalF2Document`. `f2/` keeps tokens, the markup parser, project rules, warnings, and `structure.py`. A later round parser, or another source with its own container, would sit beside `f2/`. `pgdp_results.py` became `rounds.py` because it reads any round, not a thing called a result.

Two renames avoid a name clash. `layout/geometry.py` became `layout/regions.py` because it describes page regions, and `geometry` already means the spatial value types one level up. `schemas/_helpers.py` became `_schemas.py` at the package root, because one shared pydantic constant does not need a package. `typography/review.py` and `ocr/review.py` kept their names. They are different things in different packages, and the package prefix distinguishes them.

## What stays outside this package

`matching/legacy_projection.py` used to refer to `Block`, `Page`, and `Word` under `TYPE_CHECKING`. Those classes stay in `pdomain-book-tools`. The matching step replaced them with three module-private structural protocols, so this package type-checks alone. The surface stayed narrow: three attributes and one method for words, three attributes and one method for lines, and three attributes for pages. The line and page protocols are generic in the word type. `Block.remove_item` accepts `Word | Block` rather than `object`, which no non-generic protocol parameter can satisfy. That showed up when book-tools type-checked against the concrete classes. This package's own tests could not catch it.

`BoundingBox.refine`, `BoundingBox.crop_top`, and `BoundingBox.crop_bottom` need cv2, so their implementations stay in book-tools. The first attempt imported `pdomain_book_tools.geometry.image_ops` at call time. That is the forbidden direction, and the three methods raised `ImportError` for anyone who installed this package alone. They now dispatch through a provider registry. `image_ops.py` registers itself when it is imported. An unregistered call raises `ImageOpsUnavailableError`. Registration stays in `image_ops.py` rather than `pdomain_book_tools/geometry/__init__.py`. Putting it in that package init would pull cv2 into every `import pdomain_book_tools.geometry`, which is the weight the extraction plan's step 5 exists to remove.

`ocr/ground_truth_matching.py` stayed in book-tools. The extraction spec counted 1,297 lines. Its docstring calls it a legacy shim superseded by `matching/engine.py`. It was not part of the extraction. Retiring it is separate work.

## How a reorganisation commit was checked

Each reorganisation commit followed a verbatim move. The check was:

1. Every file present before is present after, under its new path.
2. Line counts match per file. A reorganisation renames and re-imports. It does not edit bodies.
3. The only content changes are import statements and `__init__` exports.
4. Both repositories pass their gates.
5. The dependency direction still holds.

On 2026-11-07 a source review at commit `37fa7ec` found two stale claims in the ops copy. The package now includes `annotation/`, and the dependency list had omitted that package's edges plus geometry's dependency on `_schemas`. That review ran thirteen tests in `tests/test_package.py`, `tests/test_torch_free_import.py`, and `tests/test_bounding_box_image_ops.py`. It did not replay every historical move commit, remeasure the 12,998-line count, or run every consumer's full gate. The review recorded that the extraction plan in `pdomain-ops` was still open, because data rescue and retirement had not been established.

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

The 2026-11-07 reading at `37fa7ec` still said typography depends on `_schemas`, matching depends only on geometry and typography, and `sources/pgdp` depends only on typography. The list above replaces that reading.

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
