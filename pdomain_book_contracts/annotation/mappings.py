"""Translation from detector and legacy vocabularies into RegionRole.

RegionType stays as it is. It records what a detector proposed, which is a
different question from what a person meant, and merging them would erase the
distinction. This module is the one-way bridge.
"""

from __future__ import annotations

from typing import Final

from pdomain_book_contracts.annotation.roles import RegionRole
from pdomain_book_contracts.layout.types import RegionType

REGION_TYPE_TO_ROLE: Final[dict[RegionType, RegionRole]] = {
    RegionType.text: RegionRole.PARAGRAPH,
    RegionType.title: RegionRole.TITLE,
    RegionType.section: RegionRole.SECTION,
    RegionType.list: RegionRole.LIST,
    RegionType.table: RegionRole.TABLE,
    RegionType.figure: RegionRole.FIGURE,
    RegionType.decoration: RegionRole.DECORATION,
    RegionType.caption: RegionRole.CAPTION,
    RegionType.header: RegionRole.PAGE_HEADER,
    RegionType.footer: RegionRole.PAGE_FOOTER,
    RegionType.footnote: RegionRole.FOOTNOTE,
    RegionType.formula: RegionRole.FORMULA,
    RegionType.abandoned: RegionRole.ABANDONED,
    RegionType.sidenote: RegionRole.SIDENOTE,
    RegionType.page_number: RegionRole.PAGE_NUMBER,
}


def region_role_for_region_type(region_type: RegionType) -> RegionRole:
    """Return the role a detector's region type proposes."""
    return REGION_TYPE_TO_ROLE[region_type]
