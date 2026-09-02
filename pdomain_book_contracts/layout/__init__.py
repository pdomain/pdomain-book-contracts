"""Page layout contracts: region and block value types.

Owns ``types.py`` and ``regions.py`` (renamed from
``pdomain_book_tools.layout.geometry``, since "geometry" already means the
spatial value types one level up), moved from ``pdomain_book_tools.layout``.
Depends only on ``geometry``.
"""

from __future__ import annotations

from pdomain_book_contracts.layout.regions import (
    caption_for_figure,
    contains,
    horizontal_overlap_ratio,
    iou,
    region_reading_order,
)
from pdomain_book_contracts.layout.types import (
    LayoutRegion,
    LayoutRegionDict,
    PageLayout,
    PageLayoutDict,
    RegionType,
)

__all__ = [
    "LayoutRegion",
    "LayoutRegionDict",
    "PageLayout",
    "PageLayoutDict",
    "RegionType",
    "caption_for_figure",
    "contains",
    "horizontal_overlap_ratio",
    "iou",
    "region_reading_order",
]
