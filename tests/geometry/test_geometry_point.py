from __future__ import annotations

import math
import operator
from typing import TYPE_CHECKING

import pytest
from pydantic import TypeAdapter, ValidationError

from pdomain_book_contracts.geometry.point import Point

if TYPE_CHECKING:
    from collections.abc import Callable


def test_whole_number_coordinates_come_back_as_int() -> None:
    p = Point(3.0, 4)
    assert isinstance(p.x, int)
    assert isinstance(p.y, int)
    assert (p.x, p.y) == (3, 4)


def test_fractional_coordinates_stay_float() -> None:
    p = Point(0.25, 0.5)
    assert (p.x, p.y) == (0.25, 0.5)


def test_flag_is_inferred_from_the_unit_square() -> None:
    assert Point(0.5, 1).is_normalized
    assert not Point(0.5, 1.5).is_normalized
    assert not Point(200, 300).is_normalized


def test_pixel_override_is_accepted_inside_the_unit_square() -> None:
    assert not Point.pixel(1, 1).is_normalized


def test_normalized_override_outside_the_unit_square_is_rejected() -> None:
    with pytest.raises(ValueError, match="normalized"):
        Point.normalized(2, 0.5)


def test_negative_coordinates_are_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        Point(-1, 5)
    with pytest.raises(ValueError, match="non-negative"):
        Point(5, -0.5)


def test_scale_turns_a_normalized_point_into_pixels() -> None:
    scaled = Point(0.5, 0.25).scale(200, 400)
    assert scaled == Point.pixel(100, 100)
    assert not scaled.is_normalized


def test_scale_rejects_a_pixel_point() -> None:
    with pytest.raises(ValueError, match="normalized point"):
        Point.pixel(10, 10).scale(100, 100)


def test_normalize_divides_by_the_image_size() -> None:
    result = Point(50, 100).normalize(100, 200)
    assert result == Point.normalized(0.5, 0.5)
    assert result.is_normalized


def test_normalize_rejects_a_normalized_point() -> None:
    with pytest.raises(ValueError, match="pixel point"):
        Point(0.5, 0.5).normalize(100, 100)


def test_normalize_rejects_fractional_pixel_coordinates() -> None:
    with pytest.raises(ValueError, match="integer-like"):
        Point(10.5, 20).normalize(100, 100)


def test_normalize_rejects_a_point_beyond_the_image() -> None:
    with pytest.raises(ValueError, match="normalized"):
        Point(150, 20).normalize(100, 100)


def test_scale_then_normalize_round_trips() -> None:
    original = Point.normalized(0.25, 0.75)
    assert original.scale(400, 800).normalize(400, 800) == original


def test_distance_is_euclidean() -> None:
    assert math.isclose(Point(0, 0).distance_to(Point(3, 4)), 5.0)


def test_as_shapely_exposes_the_coordinates() -> None:
    geom = Point(7, 9).as_shapely()
    assert (geom.x, geom.y) == (7.0, 9.0)


def test_repr_shows_the_coordinates() -> None:
    assert repr(Point(3, 0.5)) == "Point(3, 0.5)"


def test_to_dict_includes_the_flag() -> None:
    assert Point(0.5, 0.5).to_dict() == {"x": 0.5, "y": 0.5, "is_normalized": True}
    assert Point(5, 6).to_dict() == {"x": 5, "y": 6, "is_normalized": False}


def test_dict_round_trip_preserves_an_explicit_pixel_flag() -> None:
    original = Point.pixel(1, 1)
    restored = Point.from_dict(dict(original.to_dict()))
    assert restored == original
    assert not restored.is_normalized


def test_from_dict_without_a_flag_infers_it() -> None:
    assert Point.from_dict({"x": 0.1, "y": 0.2}).is_normalized
    assert not Point.from_dict({"x": 10, "y": 20}).is_normalized


def test_from_dict_rejects_a_normalized_flag_on_pixel_values() -> None:
    with pytest.raises(ValueError, match="normalized"):
        Point.from_dict({"x": 10, "y": 20, "is_normalized": True})


def test_ordering_is_lexicographic_on_x_then_y() -> None:
    assert Point(1, 9) < Point(2, 0)
    assert Point(2, 1) < Point(2, 3)
    assert Point(2, 3) > Point(2, 1)
    assert Point(2, 3) <= Point(2, 3)
    assert Point(2, 3) >= Point(2, 3)
    assert not Point(2, 3) < Point(2, 3)


@pytest.mark.parametrize(
    "compare",
    [operator.lt, operator.le, operator.gt, operator.ge, operator.eq],
)
def test_comparing_across_normalization_states_raises(
    compare: Callable[[Point, Point], object],
) -> None:
    with pytest.raises(TypeError, match="normalization"):
        compare(Point(0.5, 0.5), Point(50, 50))


def test_ordering_against_a_non_point_is_unsupported() -> None:
    with pytest.raises(TypeError):
        operator.lt(Point(1, 1), 5)
    with pytest.raises(TypeError):
        operator.ge(Point(1, 1), "x")


def test_equality_with_a_non_point_is_false() -> None:
    other: object = (1, 1)
    assert Point(1, 1) != other


def test_equal_points_hash_alike_and_dedupe_in_a_set() -> None:
    assert Point(2, 3) == Point(2.0, 3.0)
    assert len({Point(2, 3), Point(2.0, 3.0), Point(2, 4)}) == 2


def test_pydantic_validates_the_wire_shape() -> None:
    adapter = TypeAdapter(Point)
    point = adapter.validate_python({"x": 0.5, "y": 0.25, "is_normalized": True})
    assert point == Point.normalized(0.5, 0.25)


def test_pydantic_dumps_the_same_shape_as_to_dict() -> None:
    adapter = TypeAdapter(Point)
    assert adapter.dump_python(Point(30, 40)) == {
        "x": 30,
        "y": 40,
        "is_normalized": False,
    }


def test_pydantic_rejects_a_missing_field() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(Point).validate_python({"x": 1})


def test_pydantic_json_schema_lists_the_three_fields() -> None:
    schema = TypeAdapter(Point).json_schema()
    assert schema["required"] == ["x", "y", "is_normalized"]


@pytest.mark.parametrize(
    "coordinates",
    [(float("nan"), 1.0), (1.0, float("nan")), ("nan", 1.0)],
)
def test_nan_coordinate_is_rejected(coordinates: tuple[float, float]) -> None:
    with pytest.raises(ValueError, match="real numbers"):
        _ = Point(*coordinates)


def test_nan_coordinate_is_a_validation_error_on_the_wire() -> None:
    with pytest.raises(ValidationError, match="real numbers"):
        _ = TypeAdapter(Point).validate_python(
            {"x": float("nan"), "y": 1.0, "is_normalized": False}
        )
