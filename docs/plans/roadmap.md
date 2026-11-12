---
Status: active
Owner: CT
Created: 2026-11-12
Last verified: 2026-11-12
Kind: plan
---

# Roadmap

## Agent Index

- **Kind:** plan
- **Status:** active
- **Owner:** CT
- **Created:** 2026-11-12
- **Last verified:** 2026-11-12
- **Read when:** choosing the next change, or deciding whether a behavior belongs in a new repository.
- **Search terms:** roadmap, coverage floor, MatchType, separate repository, PGDP readers.

Shipped behavior is an architecture doc. Open work is one line plus its issue or branch.

No new repository in the list below should be created from this page alone.

## Shipped

- [Overview and dependency boundary](../architecture/00-overview.md)
- [Module layout](../architecture/module-layout.md)
- [Layout contracts](../architecture/layout-contracts.md)
- [Matching](../architecture/matching.md)
- [PGDP readers](../architecture/pgdp-readers.md)
- Coverage floor at 95 percent, the three geometry fixes, and the PGDP N, artifact-path, and F2 page-key fixes from `feat/coverage-floor` (`2bd0bcb` through `673e5d9`). The handoff recorded `make ci AI=1` exiting 0 on `5f5022c`, and 1,323 tests at 96.92 percent on Python 3.13. On 2026-11-12, after this merge, `uv run pytest --cov` exited 0 and reported 96.92 percent. The collector listed 1,323 tests.

## Open on master

- Whether this package should take the contracts-only tests out of `pdomain-book-tools` is still an owner decision. The retired coverage issue says that separation does not exist yet. The floor did not need that move.
- `WORD_NEARLY_EQUAL_DUE_TO_PUNCTUATION` and `LINE_REPLACE_WORD_EQUAL` are absent from `MatchType`. Comments in `pdomain_book_contracts/matching/match_type.py` say to restore each one only when the pipeline would assign it. No issue tracks that work.
- Seven package docstrings name import edges the source does not have: `layout`, `typography`, `matching`, `ocr`, `sources/pgdp`, `sources/pgdp/f2`, and `annotation`. The docstring on `test_numpy_loads_only_via_shapely` does too. The corrected graph is the [module layout](../architecture/module-layout.md). The docstrings themselves are still the old text.
- Importing `PGDPExport` loads shapely, because `sources/pgdp/__init__.py` imports the F2 parser and that parser reaches `BoundingBox`. The measurement is in the [PGDP readers](../architecture/pgdp-readers.md) doc. A lazy package init would fix the import without a new repository. That change is not started.

The NaN rejection, the center flag, and the mixed-coordinate check are on master. Three owner decisions from that work remain open.

`Point` still accepts infinity, because a test builds an infinite corner and the NaN fix did not cover infinity.

`get_four_point_scaled_polygon_list` scales a pixel box as if it were normalized. `from_points` drops the flag of `Point` inputs. Neither of those two is fixed.

After a contracts release, `pdomain-book-tools` test `test_bounding_box_contains_point` passes a pixel point to a normalized box. It will fail until it expects `ValueError` or uses a normalized point. The book-tools geometry issue stays open until that suite is updated.

## Consider a separate repository later

These are candidates. None of them should be started until the trigger named with that candidate is true.

**PGDP readers and the four PGDP matching modules.** `sources/` is 2,493 lines. `matching/pgdp_continuations.py`, `pgdp_bounded.py`, `pgdp_visible.py`, and `pgdp_layout_projection.py` are 2,947 lines. Together that is 5,440 of the package's 16,083 Python lines, counted on 2026-11-12, excluding `__pycache__`.

That code is the F2 parser, the round container, and the match adapters that know F2 and P3.

`pgdp_visible.py` is the one that imports `tokenize_f2`. `engine.py` imports `pgdp_continuations.py`. `pgdp_bounded.py` calls `match_documents`.

Moving all four matching modules out would make this package and the new one depend on each other.

Moving only `sources/` is also a cycle. The new package would import `typography` and `layout` from this one. `pgdp_visible.py` would import the new package.

`sources/` does not import `matching`. The match models do not import PGDP types. The engine does, so moving the readers does not make the engine source-neutral.

A one-way cut needs `pgdp_visible.py` to move with the readers. It also needs `pgdp_continuations.py` to stay with `engine.py`.

Do not put that code in `pdomain-pgdp-api-client` or `pdomain-pgdp-measure`. The client is a network mirror. The measure repository is measurement.

On 2026-11-12 the only Python import of this package in the api client was `PGDPExport`.

The trigger is a second source under `sources/`, or a consumer that must install the contracts without the F2 parser. Until then, the cheaper change is the lazy package init in the open list.

A new repository would still load shapely if its parser imports `typography.records`. That load happens because that module imports `BoundingBox` and the typography package init loads the rest.

Python import lines found on 2026-11-12, outside this repository:

- `pdomain-ocr-labeler-spa` uses annotation, layout, geometry, matching, typography, ocr, and sources.
- `pdomain-book-tools` uses sources, typography, matching, ocr, layout, geometry, annotation, text, licensing, and `_schemas`.
- `pdomain-source-data` uses matching, layout, and sources.
- `pdomain-ocr-simple-gui` uses layout.
- `pdomain-ocr-training` uses annotation and layout.
- `pdomain-pgdp-api-client` uses sources, and that import is only `PGDPExport`.

The other consumers that import sources also import another area of this package.

## Do not split these out

- Annotation vocabularies. Importing them loads `layout`. It does not load shapely. The labeler and the training app already import layout as well. No consumer found on 2026-11-12 imports annotation alone.
- Geometry by itself. Typography records, OCR characters, and the match graph use boxes. Those consumers would still depend on shapely through this package or through a geometry package. The pin would be new. The install would not get lighter.
- Licensing and the SPDX file. `licensing.py` is 73 lines. One external import line was found, in `pdomain-book-tools`.
- Text normalization. It is a standard-library leaf of `label_normalization.py` and `text_normalize.py`, already its own subpackage.
- The match graph, alignment, and legacy projection. `models.py`, `alignment.py`, and `legacy_projection.py` do not import the PGDP modules. `engine.py` does, through `pgdp_continuations.py`, so the engine is not a separable source-neutral core. The extraction put these algorithms in this package on purpose.
- OCR result types. `pdomain-book-tools` is the engine that fills them. They stay here so that engine depends on this package in one direction.

## Goal

Keep one list of unfinished work for this package. Point shipped behavior at `docs/architecture/` instead of repeating it. Name which ideas are new repositories, and which are not.

## Architecture

The open items stay inside `pdomain_book_contracts`. The coverage floor and the geometry fixes are on master. The docstring corrections and a lazy `sources/pgdp` init would land in this repository.

Moving only `sources/` would cycle. That code imports `typography` and `layout` here. `pgdp_visible.py` here would import the new package.

Moving the four PGDP matching modules with the readers would also cycle, because `engine.py` imports `pgdp_continuations.py` and `pgdp_bounded.py` calls `match_documents`.

A one-way cut keeps the continuations with the engine and moves `pgdp_visible.py` with the readers.

The areas in "Do not split these out" stay subpackages.

## Tech Stack

The package remains pure Python. Runtime dependencies stay pydantic, pydantic-core, shapely, regex, and typing-extensions. Tests stay pytest.

The coverage floor is 95 percent, the floor measured on `feat/coverage-floor`.

## Global Constraints

- Do not add torch, doctr, torchvision, cv2, numpy, pandas, matplotlib, transformers, or ipython.
- `CONVENTIONS.md` bans ipython even as a test dependency. The lightness test does not currently name ipython.
- Numpy may load through shapely. It stays off the declared dependency list.
- The coverage floor is the 95 percent floor in `pyproject.toml`. Do not add a second floor.
- Do not create a repository from the candidate list until its trigger is true and the owner accepts it.
- Do not move the PGDP readers into the api client or the measure repository.
