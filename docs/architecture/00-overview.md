# Overview

## Agent Index

- **Kind:** architecture
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-11-06
- **Read when:** orienting on the package's purpose, dependency boundary, or
  module layout before adding a contract.
- **Search terms:** book contracts, geometry, typography, matching, ocr,
  layout, annotation, pgdp, dependency boundary, lightness test.

`pdomain-book-contracts` holds the pure-Python contracts shared by the
pdomain OCR suite. A consumer can use these types and algorithms without an
imaging stack or a machine-learning stack.

Runtime dependencies are pydantic, pydantic-core, shapely, regex, and
typing-extensions. Python 3.11 takes `override` from typing-extensions.
Python 3.12 and later take it from the standard library.

## What the package holds

Every subpackage below is implemented. `data` holds the vendored SPDX list
and has no runtime code.

```text
pdomain_book_contracts/
    geometry/        point.py, bounding_box.py
    text/            label_normalization.py, text_normalize.py
    annotation/      roles.py, page_kind.py, provenance.py, mappings.py
    typography/      labels.py, spans.py, normalization.py, records.py,
                     annotations.py, exchange.py, book_manifest.py, review.py
    matching/        alignment.py, engine.py, models.py, legacy_projection.py,
                     pgdp_continuations.py, match_type.py, character_groups.py
    ocr/             character.py, glyph_annotations.py, provenance.py,
                     review.py, gt_orphans.py, blob_protocol.py
    layout/          types.py, regions.py
    sources/pgdp/    rounds.py, offsets.py,
                     f2/{tokens,parser,project_rules,warnings}.py
    data/            spdx_licenses.json
    licensing.py
    _schemas.py
```

`annotation` holds the shared words.

- `RegionRole` has 34 roles.
- `PageKind` names the kind of page.
- `LabelSource`, `KnowledgeState`, and `ConfidenceTier` are the provenance
  enums.

`mappings.py` maps a layout `RegionType` to a `RegionRole`.

- A page number stays a page number. It does not become a footer.
- Figure and illustration stay distinct.

`licensing.py` validates SPDX license identifiers against the vendored list
in `data/spdx_licenses.json`.

## How the modules import each other

These are the imports the modules make.

- `_schemas`, `text`, `layout`, `licensing`, and `data` import nothing else
  in this package.
- `licensing` reads `data/spdx_licenses.json` as package data.
- `geometry` imports `_schemas`.
- `annotation` imports `layout`. That edge is the `RegionType` to
  `RegionRole` map.
- `typography` imports `geometry` and `annotation`.
- `matching` imports `geometry` and `typography`.
- `ocr` imports `_schemas`, `geometry`, `text`, and `annotation`.
- `sources/pgdp` imports `typography`.

Importing the `annotation` package also imports `layout`, because
`annotation/__init__.py` imports the mapping.

## Image operations stay in book-tools

`BoundingBox.refine`, `BoundingBox.crop_top`, and `BoundingBox.crop_bottom`
call a registered `ImageOpsProvider`.

This package does not ship that provider. It does not import
`pdomain-book-tools`.

Importing `pdomain_book_tools.geometry.image_ops` registers the provider.

With no provider registered, those three methods raise
`ImageOpsUnavailableError`.

`pdomain-book-tools` depends on this package and re-exports its names.

Nothing here depends on `pdomain-book-tools`.

## What must not be imported

Numpy is not a declared dependency. Shapely imports it.

`pdomain_book_contracts/geometry/bounding_box.py` imports `numpy.ndarray`
only under `TYPE_CHECKING`, so that name is not loaded at runtime.

The lightness tests block torch, doctr, torchvision, cv2, pandas,
matplotlib, and transformers.

`test_numpy_loads_only_via_shapely` asserts that importing shapely loads
numpy. The same test asserts that importing this package loads both shapely
and numpy. That test does not prove that numpy cannot also load by some
other path.

## Evidence

- Code: `pdomain_book_contracts/` as listed under "What the package holds".
  Image-op dispatch is `register_image_ops` and `ImageOpsUnavailableError`
  in `pdomain_book_contracts/geometry/bounding_box.py`. The dependency list
  is `pyproject.toml`.
- Tests:
  - `tests/test_torch_free_import.py`:
    `test_package_imports_without_heavy_stack`,
    `test_every_subpackage_imports_without_heavy_stack`,
    `test_numpy_loads_only_via_shapely`,
    `test_shapely_itself_is_unaffected_by_the_blocker`.
  - `tests/test_package.py`:
    `test_version_is_exposed`,
    `test_every_subpackage_has_a_docstring`.
  - `tests/test_bounding_box_image_ops.py`:
    `test_refine_dispatches_to_the_registered_provider`,
    `test_crop_top_and_crop_bottom_dispatch_to_the_registered_provider`,
    `test_each_operation_raises_the_named_error_when_nothing_is_registered`,
    `test_refine_raises_the_named_error_with_book_tools_hidden_from_imports`.
  - `tests/test_annotation_vocabularies.py`:
    `test_provenance_enums_import_from_annotation`,
    `test_a_model_can_be_named_as_the_source`,
    `test_the_f2_parser_s_source_is_unchanged`,
    `test_typography_labels_still_re_export_them`,
    `test_the_twenty_shipped_roles_are_unchanged`,
    `test_the_fourteen_additions_are_present`,
    `test_aliases_fold_to_canonical_roles`,
    `test_normalizer_accepts_case_and_separator_variants`,
    `test_unknown_role_raises`,
    `test_page_kind_covers_the_body_and_front_matter_cases`,
    `test_page_kind_has_an_explicit_unknown`,
    `test_page_kind_normalizer_folds_variants`,
    `test_page_kind_rejects_a_packaging_value`.
  - `tests/test_annotation_mappings.py`:
    `test_every_region_type_maps_to_a_role`,
    `test_page_number_survives_instead_of_becoming_a_footer`,
    `test_header_and_footer_do_not_collapse_the_folio_distinction`,
    `test_figure_and_illustration_stay_distinct`.
  - `tests/test_review_metadata_provenance.py`:
    `test_defaults_keep_existing_records_valid`,
    `test_source_and_state_round_trip`,
    `test_a_rejection_is_expressible`,
    `test_an_f2_supplied_answer_is_distinguishable_from_a_typed_one`,
    `test_a_legacy_dict_without_the_new_keys_still_loads`.
- Artifacts: none.
- Verified: 2026-11-06, `uv run pytest` in this repository, 34 passed.

## `make test` enforces a 95 percent coverage floor

`make test` measures this package with branch coverage over the tests in this
repository and fails below 95 percent.
