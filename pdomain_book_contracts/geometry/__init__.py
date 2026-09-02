"""
Spatial value types shared by every contract in this package.

Owns ``point.py`` (``Point``) and ``bounding_box.py`` (``BoundingBox``),
moved from ``pdomain_book_tools.geometry``. These are pure-Python value
types with no dependency on any other subpackage; every other subpackage
that needs a coordinate depends on this one.
"""

from __future__ import annotations

from pdomain_book_contracts.geometry.bounding_box import BoundingBox
from pdomain_book_contracts.geometry.point import Point

__all__ = ["BoundingBox", "Point"]
