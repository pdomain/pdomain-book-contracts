---
Status: active
Owner: CT
Created: 2026-09-02
Last verified: 2026-11-12
Kind: architecture
---

# Overview

## Agent Index

- **Kind:** architecture
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-11-12
- **Read when:** orienting on the package's purpose, dependency boundary, or
  module layout before adding a contract.
- **Search terms:** book contracts, geometry, typography, matching, ocr,
  layout, annotation, pgdp, dependency boundary, lightness test.

`pdomain-book-contracts` holds the pure-Python contracts shared by the
pdomain OCR suite. A consumer can use these types and algorithms without an
imaging stack or a machine-learning stack.

Runtime dependencies are pydantic, pydantic-core, shapely, regex, and
typing-extensions. The version bounds are in the
[module layout](module-layout.md).

Python 3.11 takes `override` from typing-extensions. Python 3.12 and later
take it from the standard library.

Shipped behavior is split across these pages.

- [Module layout](module-layout.md) lists every area and the import edges measured on 2026-11-12.
- [Layout contracts](layout-contracts.md) covers detector regions, the role map, text hints, and reviewed structure.
- [Matching](matching.md) covers the match graph and the PGDP adapters.
- [PGDP readers](pgdp-readers.md) covers the round container and the F2 parser.

Open work is the [roadmap](../plans/roadmap.md).

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
and numpy. That test does not prove there is no other path that also loads
numpy.

Importing the package root does not load shapely. Importing `geometry`,
`typography`, `ocr`, `matching`, or `sources.pgdp` does. `annotation`,
`layout`, `text`, and `licensing` do not. The measurements are in the
[module layout](module-layout.md).

## Evidence

- Code: `pdomain_book_contracts/` as listed in the [module layout](module-layout.md).
  Image-op dispatch is `register_image_ops` and `ImageOpsUnavailableError`
  in `pdomain_book_contracts/geometry/bounding_box.py`. The dependency list
  is `pyproject.toml`.
- Tests that pin the boundary and the shared words:
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
- Later tests, not in the 2026-11-06 list:
  - `tests/layout/test_text_hints.py` collected 10.
  - `tests/matching/test_pgdp_bounded.py` collected 6.
  - `tests/matching/test_pgdp_engine_regression.py` collected 1.
  - `tests/matching/test_pgdp_layout_projection.py` collected 8.
  - `tests/matching/test_pgdp_visible.py` collected 6.
  - `tests/pgdp/f2/test_structure.py` collected 14.
- Artifacts: none.
- Verified on 2026-11-06: `uv run pytest` in this repository, 34 passed.
- Verified on 2026-11-12: the collector listed 79 tests. `uv run pytest` printed a dot for each and exited 0.
- Verified on 2026-11-12: `pyproject.toml` still sets no coverage floor.

## Coverage is still open on master

This package does not enforce a coverage floor. The open item is the
[issue index](../issues/README.md). The unmerged attempt lives on
`feat/coverage-floor` and is recorded in the [roadmap](../plans/roadmap.md).
