import sys
from typing import cast

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override  # pyright: ignore[reportUnreachable]

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema
from shapely.geometry import Point as ShapelyPoint

from pdomain_book_tools.schemas._helpers import NUMBER_SCHEMA

# Wire shape for a Point dict — extracted as a module-level constant so
# composite models (BoundingBox, etc.) can embed Point's shape without
# triggering Point's full validator pipeline (which would coerce nested
# dicts to Point instances inside parent ``from_dict`` callers that
# expect raw dicts).
_POINT_DICT_SCHEMA = core_schema.typed_dict_schema(
    {
        "x": core_schema.typed_dict_field(NUMBER_SCHEMA),
        "y": core_schema.typed_dict_field(NUMBER_SCHEMA),
        "is_normalized": core_schema.typed_dict_field(
            core_schema.bool_schema(),
        ),
    }
)


class Point:
    """2D point backed by a Shapely ``Point`` with an inferred or overridable
    ``is_normalized`` flag describing coordinate semantics.

    Classification:
        * Normalized (``is_normalized=True``): both coordinates lie in [0,1].
        * Pixel (``is_normalized=False``): any other non\u2011negative coordinates.

    The flag is inferred on construction and after x/y mutation, unless explicitly
    overridden via the constructor argument or the ``is_normalized`` property.

    Ordering (>, <, >=, <=) is lexicographic on the tuple (x, y) and only permitted
    when both points share the same normalization state; otherwise a TypeError is
    raised. Equality likewise requires matching normalization; attempting to compare
    points whose normalization flags differ raises TypeError. Equality is otherwise
    exact on (x, y). Use a helper for approximate comparison if needed.

    Serialization: ``to_dict()`` / ``from_dict()`` round\u2011trip x, y and
    ``is_normalized`` (older dicts without the flag still infer it).
    """

    __slots__: tuple[str, ...] = ("_geom", "_is_normalized")
    _geom: ShapelyPoint
    _is_normalized: bool

    def __init__(
        self, x: float | int, y: float | int, is_normalized: bool | None = None
    ) -> None:
        """Create a point backed directly by a Shapely Point.

        Args:
            x: X coordinate (int/float or numeric string)
            y: Y coordinate (int/float or numeric string)
            is_normalized: Optional explicit override of the inferred normalized flag.
        """
        fx, fy = self._coerce_number(x), self._coerce_number(y)
        self._geom = ShapelyPoint(float(fx), float(fy))
        self._classify()
        if is_normalized is not None:
            if is_normalized and not (self._within_unit(fx) and self._within_unit(fy)):
                raise ValueError(
                    "Cannot mark as normalized: coordinates must lie within [0,1]"
                )
            self._is_normalized = bool(is_normalized)

    # Internal -----------------------------------------------------------
    def _coerce_number(self, value: float | int | str) -> float | int:
        try:
            f = float(value)
        except (TypeError, ValueError) as err:
            raise ValueError(
                "Point coordinates must be able to be coerced to real numbers"
            ) from err
        # Preserve int type when exact
        return int(f) if f.is_integer() else f

    def _classify(self) -> None:
        fx = float(self._geom.x)
        fy = float(self._geom.y)
        EPS = 1e-9
        if -EPS <= fx <= 1 + EPS and -EPS <= fy <= 1 + EPS:
            if fx < 0 or fy < 0:
                raise ValueError("Pixel point coordinates must be non-negative")
            self._is_normalized = True
        else:
            if fx < 0 or fy < 0:
                raise ValueError("Pixel point coordinates must be non-negative")
            self._is_normalized = False

    def _within_unit(self, v: float | int) -> bool:
        EPS = 1e-9
        fv = float(v)
        return -EPS <= fv <= 1 + EPS and fv >= 0

    # Properties ---------------------------------------------------------
    @property
    def x(self) -> float | int:
        # Return int when representable exactly
        return int(self._geom.x) if float(self._geom.x).is_integer() else self._geom.x

    @property
    def y(self) -> float | int:
        return int(self._geom.y) if float(self._geom.y).is_integer() else self._geom.y

    @property
    def is_normalized(self) -> bool:
        return self._is_normalized

    @is_normalized.setter
    def is_normalized(self, _value: bool) -> None:  # pragma: no cover - defensive
        raise AttributeError(
            "Point is immutable; use factory methods instead of mutating is_normalized"
        )

    # Note: ``Point`` deliberately does NOT delegate arbitrary attribute access
    # to the underlying Shapely geometry. Earlier versions defined
    # ``__getattr__ = lambda self, item: getattr(self._geom, item)``, which
    # silently exposed every Shapely attribute (``area``, ``bounds``,
    # ``buffer``, deprecated/internal members, etc.) as part of ``Point``'s
    # public API. That made every Shapely version-bump a potential breaking
    # change. The supported public surface is the explicit ``@property`` /
    # method members defined on this class; for raw Shapely access use
    # ``as_shapely()``.

    @override
    def __repr__(self) -> str:
        return f"Point({self.x}, {self.y})"

    # (to_x_y removed; use (p.x, p.y) directly)

    def scale(self, width: int, height: int) -> "Point":
        """Scale the point to pixel coordinates based on the given width and height."""
        if not self.is_normalized:
            raise ValueError("scale() expected a normalized point (values in [0,1])")
        return Point.pixel(round(self.x * width), round(self.y * height))

    def normalize(self, width: int, height: int) -> "Point":
        """Normalize the point to [0,1] unit square coordinates based on the given width and height."""
        if self.is_normalized:
            raise ValueError("normalize() expected a pixel point (non-normalized)")
        if not (self._is_int_like(self.x) and self._is_int_like(self.y)):
            raise ValueError(
                "normalize() requires integer-like pixel coordinates (e.g., 10 or 10.0)"
            )
        return Point.normalized(
            float(self.x) / float(width), float(self.y) / float(height)
        )

    # (with_* helpers removed; construct new instances directly)

    # Alternative constructors --------------------------------------------
    @classmethod
    def normalized(cls, x: float | int, y: float | int) -> "Point":
        return cls(x, y, is_normalized=True)

    @classmethod
    def pixel(cls, x: float | int, y: float | int) -> "Point":
        return cls(x, y, is_normalized=False)

    def to_dict(self) -> dict[str, float | int | bool]:
        # Include normalization state for round-trip serialization
        return {"x": self.x, "y": self.y, "is_normalized": self.is_normalized}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Point":
        """Create a Point from a dict produced by ``to_dict``.

        Accepts legacy dicts without ``is_normalized`` (falls back to inference).
        """
        x = cast("float | int", data["x"])
        y = cast("float | int", data["y"])
        is_norm = cast("bool | None", data.get("is_normalized"))
        return cls(x, y, is_normalized=is_norm)

    def as_shapely(self) -> "ShapelyPoint":
        return self._geom

    def distance_to(self, other: "Point") -> float:
        return float(self._geom.distance(other.as_shapely()))

    # Helpers ----------------------------------------------------------
    def _is_int_like(self, value: float | int) -> bool:
        return isinstance(value, int) or value.is_integer()

    # Comparisons ------------------------------------------------------
    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        if self.is_normalized != other.is_normalized:
            raise TypeError("Cannot compare points with different normalization state")
        return (self.x, self.y) > (other.x, other.y)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        if self.is_normalized != other.is_normalized:
            raise TypeError("Cannot compare points with different normalization state")
        return (self.x, self.y) < (other.x, other.y)

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        if self.is_normalized != other.is_normalized:
            raise TypeError("Cannot compare points with different normalization state")
        return (self.x, self.y) >= (other.x, other.y)

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        if self.is_normalized != other.is_normalized:
            raise TypeError("Cannot compare points with different normalization state")
        return (self.x, self.y) <= (other.x, other.y)

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        if self.is_normalized != other.is_normalized:
            raise TypeError("Cannot compare points with different normalization state")
        return (self.x, self.y) == (other.x, other.y)

    @override
    def __hash__(self) -> int:  # Allow use in sets / dicts
        return hash((float(self.x), float(self.y), self.is_normalized))

    # ------------------------------------------------------------------
    # Pydantic v2 integration: wire-shape JSON Schema via TypeAdapter.
    #
    # Point is not a dataclass and uses __slots__, so pydantic cannot
    # auto-introspect it. This hook declares the wire shape produced by
    # ``Point.to_dict()`` so ``TypeAdapter(Point).json_schema()`` emits a
    # precise JSON Schema for downstream TypeScript codegen (pdomain-ui,
    # pdomain-ops).
    # ------------------------------------------------------------------
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: object,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            function=cls.from_dict,
            schema=_POINT_DICT_SCHEMA,
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls.to_dict,
            ),
        )
