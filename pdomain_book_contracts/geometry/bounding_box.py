from __future__ import annotations

import functools
import sys
from dataclasses import dataclass
from logging import getLogger
from typing import TYPE_CHECKING, TypedDict, TypeVar

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override  # pyright: ignore[reportUnreachable]

from pydantic_core import CoreSchema, core_schema
from shapely.geometry import (
    Point as ShapelyPoint,
)  # removed LineString import
from shapely.geometry import (
    Polygon as ShapelyPolygon,
)
from shapely.geometry import (
    box as shapely_box,
)
from shapely.ops import unary_union  # removed split import

from pdomain_book_tools.geometry.point import Point
from pdomain_book_tools.schemas._helpers import NUMBER_SCHEMA

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from numpy import ndarray
    from pydantic import GetCoreSchemaHandler

# Inline wire-shape for a Point dict — mirrors _POINT_DICT_SCHEMA from point.py
# without importing a private name. Used by __get_pydantic_core_schema__.
_POINT_DICT_SCHEMA_INLINE = core_schema.typed_dict_schema(
    {
        "x": core_schema.typed_dict_field(NUMBER_SCHEMA),
        "y": core_schema.typed_dict_field(NUMBER_SCHEMA),
        "is_normalized": core_schema.typed_dict_field(
            core_schema.bool_schema(),
        ),
    }
)

# Configure logging
logger = getLogger(__name__)

# TypeVar for the _require_same_coords decorator
_T = TypeVar("_T")


class _PointDict(TypedDict, total=False):
    """Wire shape for a serialized Point corner (from to_dict / from_dict)."""

    x: float
    y: float
    is_normalized: bool | None


class _BoundingBoxDict(TypedDict):
    """Wire shape for a serialized BoundingBox (from to_dict / from_dict).

    ``top_left`` and ``bottom_right`` are required; ``is_normalized`` is
    optional (older serialized forms omit it).
    """

    top_left: _PointDict
    bottom_right: _PointDict
    is_normalized: bool | None


@dataclass
class BoundingBox:
    """Axis-aligned bounding box.

    Internally represented with two corner points (top-left & bottom-right).
    Shapely is leveraged for certain spatial combinations (intersection/union),
    but core scalar properties (area, overlaps, splits) use inexpensive arithmetic.
    """

    top_left: Point
    bottom_right: Point
    is_normalized: bool | None = None  # explicit override; inferred when None

    @property
    def minX(self) -> float:
        return self.top_left.x

    @property
    def minY(self) -> float:
        return self.top_left.y

    @property
    def maxX(self) -> float:
        return self.bottom_right.x

    @property
    def maxY(self) -> float:
        return self.bottom_right.y

    @property
    def lrtb(self) -> tuple[float, float, float, float]:
        """Deprecated alias for :meth:`to_ltrb`.

        The ``lrtb`` name is misleading — the tuple returned is
        ``(left, top, right, bottom)``, not left-right-top-bottom. Use
        :meth:`to_ltrb` instead.
        """
        import warnings

        warnings.warn(
            "BoundingBox.lrtb is deprecated; use BoundingBox.to_ltrb() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.to_ltrb()

    @property
    def width(self) -> float:
        """Get width of the box."""
        return self.bottom_right.x - self.top_left.x

    @property
    def height(self) -> float:
        """Get height of the box."""
        return self.bottom_right.y - self.top_left.y

    @property
    def size(self) -> tuple[float, float]:
        """Get (width, height) of the box."""
        return self.width, self.height

    @property
    def lrwh(self) -> tuple[float, float, float, float]:
        """Deprecated alias for :meth:`to_ltwh`.

        The ``lrwh`` name is misleading — the tuple returned is
        ``(left, top, width, height)``, not left-right-width-height. Use
        :meth:`to_ltwh` instead.
        """
        import warnings

        warnings.warn(
            "BoundingBox.lrwh is deprecated; use BoundingBox.to_ltwh() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.to_ltwh()

    def get_four_point_scaled_polygon_list(
        self, width: int, height: int
    ) -> list[list[float]]:
        """Get four points of the box."""
        return [
            [int(self.minX * width), int(self.minY * height)],
            [int(self.maxX * width), int(self.minY * height)],
            [int(self.maxX * width), int(self.maxY * height)],
            [int(self.minX * width), int(self.maxY * height)],
        ]

    @property
    def area(self) -> float:
        """Area of the bounding box (width * height)."""
        return float(self.width * self.height)

    @property
    def center(self) -> Point:
        """Get center point of the box."""
        return Point(
            (self.top_left.x + self.bottom_right.x) / 2,
            (self.top_left.y + self.bottom_right.y) / 2,
        )

    @property
    def vertical_midpoint(self) -> float:
        """Return the vertical centre (midpoint of minY and maxY)."""
        return (self.minY + self.maxY) / 2.0

    @property
    def horizontal_midpoint(self) -> float:
        """Return the horizontal centre (midpoint of minX and maxX)."""
        return (self.minX + self.maxX) / 2.0

    @property
    def y_range(self) -> tuple[float, float]:
        """Return ``(minY, maxY)`` tuple."""
        return (self.minY, self.maxY)

    @property
    def has_usable_coordinates(self) -> bool:
        """Return True when all four corners are finite numbers suitable for rendering.

        "Finite" means not ``None``, not ``NaN``, not ``+inf`` / ``-inf``. A
        validly constructed :class:`BoundingBox` cannot have ``None`` corners
        (Shapely-backed ``Point`` coordinates are always real), but it can
        receive ``NaN`` / ``inf`` from upstream Shapely operations whose result
        geometry is empty (e.g. ``buffer()`` collapsing a thin box). Rendering
        code uses this guard to skip drawing rather than crash.

        Genuine attribute / arithmetic errors are deliberately *not* swallowed
        here — if ``minX`` etc. raise, that is a real bug and should surface.
        """
        import math

        return all(
            math.isfinite(c) for c in (self.minX, self.minY, self.maxX, self.maxY)
        )

    @staticmethod
    def _split_at_x(
        box: BoundingBox, x_value: float
    ) -> tuple[BoundingBox, BoundingBox]:
        """Internal helper to split at absolute x coordinate (may coincide with an edge)."""
        if x_value < box.minX or x_value > box.maxX:
            raise ValueError("split x is out of range for bounding box")
        left = BoundingBox._build(
            box.minX, box.minY, x_value, box.maxY, box.is_normalized
        )
        right = BoundingBox._build(
            x_value, box.minY, box.maxX, box.maxY, box.is_normalized
        )
        return left, right

    def split_x_offset(self, x_offset: float) -> tuple[BoundingBox, BoundingBox]:
        """Split the bounding box into two boxes using the given x offset from left edge.

        Pure arithmetic implementation replaces earlier Shapely-based version
        (performance + determinism). Maintains previous semantics allowing
        zero-width side when offset is 0 or width.
        """
        if x_offset < 0 or x_offset > self.width:
            raise ValueError("x_offset is out of range for bounding box")
        x_abs = self.minX + x_offset
        return self._split_at_x(self, x_abs)

    def split_x_absolute(self, x_absolute: float) -> tuple[BoundingBox, BoundingBox]:
        """Split the bounding box into two boxes at absolute x coordinate.

        Arithmetic-only implementation (no Shapely).
        """
        return self._split_at_x(self, x_absolute)

    @override
    def __repr__(self) -> str:
        return (
            f"BoundingBox.from_ltrb({self.minX}, {self.minY}, {self.maxX}, {self.maxY})"
        )

    # Initialization Checks
    def __post_init__(self) -> None:
        """Validate the bounding box coordinates."""
        if (
            self.top_left.x > self.bottom_right.x
            or self.top_left.y > self.bottom_right.y
        ):
            raise ValueError(
                "Invalid bounding box coordinates: x_min must be <= x_max and y_min must be <= y_max"
            )
        coords = [
            float(self.top_left.x),
            float(self.top_left.y),
            float(self.bottom_right.x),
            float(self.bottom_right.y),
        ]
        inferred = all(0 <= c <= 1 for c in coords)
        if self.is_normalized is None:
            self.is_normalized = inferred
        elif self.is_normalized and not inferred:
            raise ValueError(
                "Cannot mark bounding box as normalized: coordinates must lie within [0,1]"
            )
        # Rebuild points if their flags differ from box-level flag
        if (
            self.top_left.is_normalized != self.is_normalized
            or self.bottom_right.is_normalized != self.is_normalized
        ):
            self.top_left = Point(
                self.top_left.x, self.top_left.y, is_normalized=self.is_normalized
            )
            self.bottom_right = Point(
                self.bottom_right.x,
                self.bottom_right.y,
                is_normalized=self.is_normalized,
            )

    @classmethod
    def from_points(
        cls,
        points: Sequence[dict[str, float] | Point | ShapelyPoint | Sequence[float]],
        is_normalized: bool | None = None,
    ) -> BoundingBox:
        """Create from a sequence of two Point instances, Shapely points, dicts with "x" and "y" keys, or sequences of 2 floats."""
        if len(points) != 2:
            raise ValueError("Bounding box should have exactly 2 points")
        converted_points: list[Point] = []
        for p in points:
            if isinstance(p, dict):
                if "x" not in p or "y" not in p:
                    raise ValueError("Dictionary should have 'x' and 'y' keys")
                converted_points.append(Point(float(p["x"]), float(p["y"])))
            elif isinstance(p, ShapelyPoint):
                if hasattr(p, "x") and hasattr(p, "y"):
                    converted_points.append(Point(float(p.x), float(p.y)))
                else:
                    raise ValueError("ShapelyPoint should have 'x' and 'y' attributes")
            elif isinstance(p, Point):
                converted_points.append(p)
            elif len(p) == 2:
                # Remaining type is Sequence[float] per the union annotation
                converted_points.append(Point(p[0], p[1]))
            else:
                raise TypeError("Unsupported point specification in from_points")
        # Policy: zero-width / zero-height boxes are accepted across the
        # constructor surface (`from_ltrb`, `from_float`, `from_ltwh`,
        # `_build` all accept `left == right` and `top == bottom`). Use `>=`
        # to match — only strictly inverted point pairs (second smaller than
        # first) are rejected. Zero-area boxes are sometimes useful as
        # singleton anchors / cursor positions; callers wanting a strict
        # nonzero check should validate after construction.
        if not (
            converted_points[1].x >= converted_points[0].x
            and converted_points[1].y >= converted_points[0].y
        ):
            raise ValueError(
                "Second point should have larger or equal x and y coordinates than the first point"
            )
        return cls._build(
            converted_points[0].x,
            converted_points[0].y,
            converted_points[1].x,
            converted_points[1].y,
            is_normalized,
        )

    @classmethod
    def from_float(
        cls, points: Sequence[float], is_normalized: bool | None = None
    ) -> BoundingBox:
        """Create from [x_min, y_min, x_max, y_max] format."""
        if len(points) != 4:
            raise ValueError(
                "Bounding box should have exactly 4 coordinates: x_min, y_min, x_max, y_max"
            )
        if points[0] > points[2] or points[1] > points[3]:
            raise ValueError(
                "Bounding box coordinates are not in correct order. x_min < x_max and y_min < y_max"
            )
        return cls._build(points[0], points[1], points[2], points[3], is_normalized)

    @classmethod
    def from_nested_float(
        cls, points: Sequence[Sequence[float]], is_normalized: bool | None = None
    ) -> BoundingBox:
        """Create from [[x_min, y_min], [x_max, y_max]] format."""
        if len(points) != 2:
            raise ValueError("Bounding box should have exactly 2 points")
        if len(points[0]) != 2 or len(points[1]) != 2:
            raise ValueError("Each point should have exactly 2 coordinates: x, y")
        if points[0][0] > points[1][0] or points[0][1] > points[1][1]:
            raise ValueError(
                "Bounding box coordinates are not in correct order. x_min < x_max and y_min < y_max"
            )
        return cls._build(
            points[0][0], points[0][1], points[1][0], points[1][1], is_normalized
        )

    @classmethod
    def from_ltrb(
        cls,
        left: float,
        top: float,
        right: float,
        bottom: float,
        is_normalized: bool | None = None,
    ) -> BoundingBox:
        """Create from left, top, right, bottom format."""
        return cls._build(left, top, right, bottom, is_normalized)

    @classmethod
    def from_ltwh(
        cls,
        left: float,
        top: float,
        width: float,
        height: float,
        is_normalized: bool | None = None,
    ) -> BoundingBox:
        """Create from left, top, width, height format."""
        if width < 0 or height < 0:
            raise ValueError("Bounding box width and height must be non-negative")
        right = left + width
        bottom = top + height
        return cls._build(left, top, right, bottom, is_normalized)

    def to_points(self) -> tuple[Point, Point]:
        """Convert to (Point,Point) format (top left point, bottom right point)."""
        return (self.top_left, self.bottom_right)

    def to_ltrb(self) -> tuple[float, float, float, float]:
        """Convert to (left, top, right, bottom) format."""
        return (
            self.top_left.x,
            self.top_left.y,
            self.bottom_right.x,
            self.bottom_right.y,
        )

    def to_ltwh(self) -> tuple[float, float, float, float]:
        """Convert to (left, top, width, height) format."""
        return (
            self.top_left.x,
            self.top_left.y,
            self.bottom_right.x - self.top_left.x,
            self.bottom_right.y - self.top_left.y,
        )

    def to_scaled_ltwh(
        self, width: int, height: int
    ) -> tuple[float, float, float, float]:
        """Convert to (left, top, width, height) format with absolute pixel coordinates."""
        scaled: BoundingBox = self.scale(width, height)
        return scaled.to_ltwh()

    def scale(self, width: int, height: int) -> BoundingBox:
        """
        Return a new BoundingBox with normalized coordinates converted
        to absolute pixel coordinates.

        Requires this box to be normalized. Raises ValueError if the box
        is already in pixel space (``is_normalized`` is False).
        """
        if not self.is_normalized:
            raise ValueError(
                "scale() expected a normalized bounding box (values in [0,1]); this box is pixel coordinates"
            )
        return BoundingBox(
            top_left=self.top_left.scale(width, height),
            bottom_right=self.bottom_right.scale(width, height),
            is_normalized=False,
        )

    def normalize(self, width: int, height: int) -> BoundingBox:
        """
        Return a new BoundingBox with absolute (pixel) coordinates converted
        to normalized coordinates in the unit square.

        Requires this box to be in pixel space. Raises ValueError if the box
        is already normalized.
        """
        if self.is_normalized:
            raise ValueError(
                "normalize() expected a pixel bounding box (non-normalized); this box is already normalized"
            )
        return BoundingBox(
            top_left=self.top_left.normalize(width, height),
            bottom_right=self.bottom_right.normalize(width, height),
            is_normalized=True,
        )

    def contains_point(self, point: Point) -> bool:
        """Check if the bounding box covers the given point (inclusive of edges).

        Implementation note: this is a trivial axis-aligned containment test;
        we previously delegated to ``shapely.geometry.box(...).covers(...)``
        which is functionally equivalent but allocates two Shapely geometries
        per call. Inclusive comparison matches Shapely's ``covers`` semantics
        (closed on the boundary).
        """
        return self.minX <= point.x <= self.maxX and self.minY <= point.y <= self.maxY

    @staticmethod
    def _require_same_coords(
        fn: Callable[..., _T],
    ) -> Callable[..., _T]:
        # R-21: ``functools.wraps`` preserves ``__name__``/``__doc__``/
        # ``__qualname__`` on decorated bounding-box methods so help(),
        # tracebacks, and tooling report the underlying method instead
        # of the generic ``wrapper`` shim.
        @functools.wraps(fn)
        def wrapper(
            self: BoundingBox, other: BoundingBox, *args: object, **kwargs: object
        ) -> _T:
            if self.is_normalized != other.is_normalized:
                raise ValueError(
                    "Bounding boxes must share coordinate system (both normalized or both pixel)"
                )
            return fn(self, other, *args, **kwargs)

        return wrapper

    @_require_same_coords
    def intersects(self, other: BoundingBox) -> bool:
        return self.as_shapely().intersects(other.as_shapely())

    @_require_same_coords
    def intersection(self, other: BoundingBox) -> BoundingBox | None:
        inter = self.as_shapely().intersection(other.as_shapely())
        if inter.is_empty:
            return None
        minx, miny, maxx, maxy = inter.bounds
        if minx == maxx or miny == maxy:
            return None
        is_norm = self.is_normalized and all(
            0 <= c <= 1 for c in (minx, miny, maxx, maxy)
        )
        return BoundingBox.from_ltrb(minx, miny, maxx, maxy, is_normalized=is_norm)

    @_require_same_coords
    def overlap_y_amount(self, other: BoundingBox) -> float:
        """Return the amount of overlap on the y-axis (projection overlap)."""
        return self._interval_overlap(self.minY, self.maxY, other.minY, other.maxY)

    @_require_same_coords
    def overlap_x_amount(self, other: BoundingBox) -> float:
        """Return the amount of overlap on the x-axis (projection overlap)."""
        return self._interval_overlap(self.minX, self.maxX, other.minX, other.maxX)

    @classmethod
    def union(cls, bounding_boxes: Sequence[BoundingBox]) -> BoundingBox:
        """Return the minimal box covering all provided boxes.

        When shapely is available we leverage unary_union to support future
        extension (e.g., rotated boxes). For current axis-aligned rectangles
        this reduces to bounds of all boxes.
        """
        if not bounding_boxes:
            raise ValueError("Bounding box list is empty")
        first_norm = bounding_boxes[0].is_normalized
        if any(b.is_normalized != first_norm for b in bounding_boxes[1:]):
            raise ValueError(
                "All bounding boxes must share coordinate system (all normalized or all pixel) for union"
            )
        geom = unary_union([b.as_shapely() for b in bounding_boxes])
        minx, miny, maxx, maxy = geom.bounds
        coords = [minx, miny, maxx, maxy]
        # Normalized only if all source boxes are normalized AND bounds lie in [0,1]
        is_norm = all(
            b.top_left.is_normalized and b.bottom_right.is_normalized
            for b in bounding_boxes
        ) and all(0 <= c <= 1 for c in coords)
        return cls(
            Point(minx, miny, is_normalized=is_norm),
            Point(maxx, maxy, is_normalized=is_norm),
            is_normalized=is_norm,
        )

    def to_dict(self) -> _BoundingBoxDict:
        """Convert to JSON-serializable dictionary.

        Includes each corner point's normalization state (``is_normalized``) so
        consumers can distinguish whether the coordinates are unit-normalized
        (in [0,1]) or absolute pixel values. Older serialized forms omitted this
        flag; :meth:`from_dict` remains backward compatible and will infer the
        state when the flag is absent.
        """
        tl: _PointDict = {
            "x": self.top_left.x,
            "y": self.top_left.y,
            "is_normalized": self.top_left.is_normalized,
        }
        br: _PointDict = {
            "x": self.bottom_right.x,
            "y": self.bottom_right.y,
            "is_normalized": self.bottom_right.is_normalized,
        }
        return {"top_left": tl, "bottom_right": br, "is_normalized": self.is_normalized}

    @classmethod
    def from_dict(cls, data: _BoundingBoxDict) -> BoundingBox:
        """Create BoundingBox from dictionary."""
        tl: _PointDict = data["top_left"]
        br: _PointDict = data["bottom_right"]
        box_norm: bool | None = data.get("is_normalized")
        tl_x = float(tl.get("x", 0.0))
        tl_y = float(tl.get("y", 0.0))
        br_x = float(br.get("x", 0.0))
        br_y = float(br.get("y", 0.0))
        return BoundingBox(
            top_left=Point(tl_x, tl_y, is_normalized=tl.get("is_normalized")),
            bottom_right=Point(br_x, br_y, is_normalized=br.get("is_normalized")),
            is_normalized=box_norm,
        )

    def refine(
        self,
        image: ndarray,
        padding_px: int = 0,
        expand_beyond_original: bool = False,
    ) -> BoundingBox:
        """Tighten this bbox around its image content (OTSU threshold).

        The implementation lives in
        :func:`pdomain_book_tools.geometry.image_ops.refine_bbox`; call that
        directly in new code. This wrapper is preserved for backward
        compatibility (R-01/R-03).
        """
        # Local import to avoid a cycle: image_ops imports BoundingBox.
        from pdomain_book_tools.geometry.image_ops import refine_bbox

        return refine_bbox(
            self,
            image,
            padding_px=padding_px,
            expand_beyond_original=expand_beyond_original,
        )

    def crop_bottom(self, image: ndarray) -> BoundingBox:
        """Return a new bbox cropped to the bottom half of its image content.

        The implementation lives in
        :func:`pdomain_book_tools.geometry.image_ops.crop_bottom_bbox`; call
        that directly in new code. This wrapper is preserved for
        backward compatibility (R-01/R-03).
        """
        from pdomain_book_tools.geometry.image_ops import crop_bottom_bbox

        return crop_bottom_bbox(self, image)

    def crop_top(self, image: ndarray) -> BoundingBox:
        """Return a new bbox cropped to the top half of its image content.

        The implementation lives in
        :func:`pdomain_book_tools.geometry.image_ops.crop_top_bbox`; call
        that directly in new code. This wrapper is preserved for
        backward compatibility (R-01/R-03).
        """
        from pdomain_book_tools.geometry.image_ops import crop_top_bbox

        return crop_top_bbox(self, image)

    def clamp_to_image(self, width: int, height: int) -> BoundingBox | None:
        """Return new box clamped to [0,width]x[0,height] in pixel or [0,1] if normalized.

        If normalized, simply clamps to [0,1].

        When the box lies entirely outside the image (so clamping collapses
        it to zero width or zero height), returns ``None`` rather than a
        degenerate zero-area box. Callers that previously got back a box
        with ``left == right`` or ``top == bottom`` would have hit
        divide-by-zero or empty-crop errors downstream; the explicit
        ``None`` lets them skip cleanly.
        """
        if self.is_normalized:
            left = max(0.0, min(1.0, self.minX))
            top = max(0.0, min(1.0, self.minY))
            right = max(0.0, min(1.0, self.maxX))
            bottom = max(0.0, min(1.0, self.maxY))
            if left >= right or top >= bottom:
                return None
            return BoundingBox.from_ltrb(left, top, right, bottom, is_normalized=True)
        left_p = max(0.0, min(width, self.minX))
        top_p = max(0.0, min(height, self.minY))
        right_p = max(0.0, min(width, self.maxX))
        bottom_p = max(0.0, min(height, self.maxY))
        if left_p >= right_p or top_p >= bottom_p:
            return None
        return BoundingBox.from_ltrb(
            left_p, top_p, right_p, bottom_p, is_normalized=False
        )

    def crop_image(self, image: ndarray) -> ndarray | None:
        """Crop a region from *image* using this bounding box.

        Handles both normalized and pixel-coordinate bounding boxes.
        Coordinates are clamped to valid image bounds before slicing.

        Returns ``None`` when the resulting crop would be empty.
        """
        shape: tuple[int, ...] = image.shape
        height, width = shape[0], shape[1]

        pixel_bbox = self.scale(width, height) if self.is_normalized else self

        x1 = int(pixel_bbox.minX)
        y1 = int(pixel_bbox.minY)
        x2 = int(pixel_bbox.maxX)
        y2 = int(pixel_bbox.maxY)

        # Reject degenerate (zero-area) boxes before any clamping.
        if x1 >= x2 or y1 >= y2:
            return None

        # Reject boxes with no overlap with the image.  Test BEFORE clamping:
        # clamping minX to width-1 would turn a fully-out-of-bounds box into a
        # spurious 1-pixel edge strip.
        if x1 >= width or x2 <= 0 or y1 >= height or y2 <= 0:
            return None

        # Clamp to [0, width] / [0, height] (not width-1/height-1 for min).
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(x2, width)
        y2 = min(y2, height)

        cropped = image[y1:y2, x1:x2]
        if cropped.size == 0:
            return None
        return cropped

    # Shapely integration methods
    @classmethod
    def from_shapely(cls, shapely_box: ShapelyPolygon) -> BoundingBox:
        """
        Create a BoundingBox from a Shapely geometry.

        Args:
            shapely_box: Any Shapely geometry with a bounds property

        Returns:
            BoundingBox instance

        Raises:
            ImportError: If shapely is not installed
            ValueError: If input is not a valid Shapely geometry
        """
        try:
            raw_bounds = shapely_box.bounds
            minx, miny, maxx, maxy = (
                float(raw_bounds[0]),
                float(raw_bounds[1]),
                float(raw_bounds[2]),
                float(raw_bounds[3]),
            )
            coords = [minx, miny, maxx, maxy]
            is_norm = all(0 <= c <= 1 for c in coords)
            return cls(
                Point(minx, miny, is_normalized=is_norm),
                Point(maxx, maxy, is_normalized=is_norm),
                is_normalized=is_norm,
            )
        except AttributeError as err:
            raise ValueError(
                "Input must be a valid Shapely geometry with a bounds property"
            ) from err

    def as_shapely(self) -> ShapelyPolygon:
        """Return a shapely geometry for the box.

        Raises ImportError if shapely is missing.
        """
        return shapely_box(
            self.top_left.x, self.top_left.y, self.bottom_right.x, self.bottom_right.y
        )

    @property
    def shapely(self) -> ShapelyPolygon:
        return self.as_shapely()

    # Additional shapely-powered helpers ---------------------------------
    def union_with(self, other: BoundingBox) -> BoundingBox:
        """Return the minimal box containing this and other."""
        return self.union([self, other])

    @_require_same_coords
    def iou(self, other: BoundingBox) -> float:
        a = self.as_shapely()
        b = other.as_shapely()
        inter = a.intersection(b)
        if inter.is_empty:
            return 0.0
        union_area = a.union(b).area
        if union_area == 0:
            return 0.0
        return float(inter.area / union_area)

    def expand(self, dx: float = 0.0, dy: float = 0.0) -> BoundingBox:
        """Expand (or shrink) the box by dx, dy on each side.

        Uniform case (dx == dy) uses Shapely buffer with square corners.
        Anisotropic case computes new rectangle about the center.
        Negative deltas shrink; resulting dimensions must remain non-negative.
        """
        if dx == dy:
            if dx == 0:
                return BoundingBox.from_ltrb(
                    self.minX,
                    self.minY,
                    self.maxX,
                    self.maxY,
                    is_normalized=self.is_normalized,
                )
            g = self.as_shapely().buffer(
                dx, join_style="mitre"
            )  # mitre=square corners; was int 2 (old shapely API)
            if g.is_empty:
                raise ValueError(
                    f"Expansion deltas collapse box to zero area (dx=dy={dx} applied to {self.width}x{self.height} box)"
                )
            minx, miny, maxx, maxy = g.bounds
            return BoundingBox.from_ltrb(
                minx, miny, maxx, maxy, is_normalized=self.is_normalized
            )
        cx = (self.minX + self.maxX) / 2.0
        cy = (self.minY + self.maxY) / 2.0
        half_w = (self.width / 2.0) + dx
        half_h = (self.height / 2.0) + dy
        if half_w < 0 or half_h < 0:
            raise ValueError("Expansion deltas collapse box to negative size")
        minx = cx - half_w
        maxx = cx + half_w
        miny = cy - half_h
        maxy = cy + half_h
        return BoundingBox.from_ltrb(
            minx, miny, maxx, maxy, is_normalized=self.is_normalized
        )

    @staticmethod
    def _build(
        left: float, top: float, right: float, bottom: float, is_normalized: bool | None
    ) -> BoundingBox:
        """Internal helper to construct a BoundingBox with shared validation & normalization inference.

        Mirrors the previous logic in individual factory constructors so behavior remains unchanged.
        """
        if left > right or top > bottom:
            raise ValueError(
                "Bounding box coordinates are not in correct order. left < right and top < bottom"
            )
        vals = [left, top, right, bottom]
        inferred = all(0 <= v <= 1 for v in vals)
        norm = inferred if is_normalized is None else is_normalized
        return BoundingBox(
            Point(left, top, is_normalized=norm),
            Point(right, bottom, is_normalized=norm),
            is_normalized=norm,
        )

    @staticmethod
    def _interval_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
        """Return 1D interval overlap length (>=0)."""
        return max(0.0, min(a1, b1) - max(a0, b0))

    def to_json(self) -> str:
        import json

        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, s: str) -> BoundingBox:
        import json
        from typing import cast

        return cls.from_dict(cast("_BoundingBoxDict", json.loads(s)))

    @staticmethod
    def is_geometry_normalization_error(error: Exception) -> bool:
        """Return True for known malformed-bbox normalization failures."""
        message = str(error)
        return "NoneType" in message and "is_normalized" in message

    # ------------------------------------------------------------------
    # Pydantic v2 integration: wire-shape JSON Schema via TypeAdapter.
    # See ``Point.__get_pydantic_core_schema__`` for the pattern rationale.
    # ------------------------------------------------------------------
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[BoundingBox],
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            function=cls.from_dict,
            schema=core_schema.typed_dict_schema(
                {
                    "top_left": core_schema.typed_dict_field(_POINT_DICT_SCHEMA_INLINE),
                    "bottom_right": core_schema.typed_dict_field(
                        _POINT_DICT_SCHEMA_INLINE
                    ),
                    "is_normalized": core_schema.typed_dict_field(
                        core_schema.bool_schema(),
                    ),
                }
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls.to_dict,
            ),
        )
