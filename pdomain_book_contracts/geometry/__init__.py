"""
Spatial value types shared by every contract in this package.

Will own ``point.py`` (``Point``) and ``bounding_box.py`` (``BoundingBox``),
moved verbatim from ``pdomain_book_tools.geometry``. These are pure-Python
value types with no dependency on any other subpackage; every other
subpackage that needs a coordinate depends on this one.

Empty pending the code move in a later task.
"""

from __future__ import annotations
