# tests/test_annotation_mappings.py
from __future__ import annotations


def test_every_region_type_maps_to_a_role() -> None:
    from pdomain_book_contracts.annotation import REGION_TYPE_TO_ROLE
    from pdomain_book_contracts.layout import RegionType

    assert set(REGION_TYPE_TO_ROLE) == set(RegionType)


def test_page_number_survives_instead_of_becoming_a_footer() -> None:
    from pdomain_book_contracts.annotation import (
        RegionRole,
        region_role_for_region_type,
    )
    from pdomain_book_contracts.layout import RegionType

    assert region_role_for_region_type(RegionType.page_number) == RegionRole.PAGE_NUMBER
    assert region_role_for_region_type(RegionType.footer) == RegionRole.PAGE_FOOTER


def test_header_and_footer_do_not_collapse_the_folio_distinction() -> None:
    from pdomain_book_contracts.annotation import (
        RegionRole,
        region_role_for_region_type,
    )
    from pdomain_book_contracts.layout import RegionType

    assert region_role_for_region_type(RegionType.header) == RegionRole.PAGE_HEADER
    assert region_role_for_region_type(RegionType.abandoned) == RegionRole.ABANDONED


def test_figure_and_illustration_stay_distinct() -> None:
    from pdomain_book_contracts.annotation import (
        RegionRole,
        region_role_for_region_type,
    )
    from pdomain_book_contracts.layout import RegionType

    # A figure region carrying OCR text is a figure. The empty-placeholder
    # illustration role is stamped elsewhere and is not a RegionType target.
    assert region_role_for_region_type(RegionType.figure) == RegionRole.FIGURE
