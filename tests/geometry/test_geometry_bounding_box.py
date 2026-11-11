from __future__ import annotations

import json
import math

import pytest
from pydantic import TypeAdapter
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import box as shapely_box

from pdomain_book_contracts.geometry.bounding_box import BoundingBox
from pdomain_book_contracts.geometry.point import Point


def _px(left: float, top: float, right: float, bottom: float) -> BoundingBox:
    return BoundingBox.from_ltrb(left, top, right, bottom, is_normalized=False)


def test_flag_is_inferred_from_the_coordinates() -> None:
    assert BoundingBox.from_ltrb(0.1, 0.2, 0.5, 0.6).is_normalized
    assert BoundingBox.from_ltrb(10, 20, 50, 60).is_normalized is False


def test_normalized_override_outside_the_unit_square_is_rejected() -> None:
    with pytest.raises(ValueError, match="normalized"):
        BoundingBox.from_ltrb(10, 20, 50, 60, is_normalized=True)


def test_pixel_override_rebuilds_the_corner_points() -> None:
    box = BoundingBox(Point(0.2, 0.2), Point(0.4, 0.4), is_normalized=False)
    assert not box.top_left.is_normalized
    assert not box.bottom_right.is_normalized


def test_inverted_corners_are_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid bounding box"):
        BoundingBox(Point(50, 50), Point(10, 60))
    with pytest.raises(ValueError, match="Invalid bounding box"):
        BoundingBox(Point(10, 60), Point(50, 20))


def test_from_ltwh_adds_the_size() -> None:
    box = BoundingBox.from_ltwh(10, 20, 30, 40)
    assert box.to_ltrb() == (10, 20, 40, 60)


def test_from_ltwh_rejects_negative_size() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        BoundingBox.from_ltwh(10, 20, -1, 5)
    with pytest.raises(ValueError, match="non-negative"):
        BoundingBox.from_ltwh(10, 20, 5, -1)


def test_from_float_reads_ltrb_order() -> None:
    assert BoundingBox.from_float([1, 2, 30, 40]).to_ltrb() == (1, 2, 30, 40)


def test_from_float_rejects_wrong_length_and_wrong_order() -> None:
    with pytest.raises(ValueError, match="exactly 4"):
        BoundingBox.from_float([1, 2, 3])
    with pytest.raises(ValueError, match="correct order"):
        BoundingBox.from_float([30, 2, 1, 40])
    with pytest.raises(ValueError, match="correct order"):
        BoundingBox.from_float([1, 40, 30, 2])


def test_from_nested_float_reads_two_points() -> None:
    box = BoundingBox.from_nested_float([[1, 2], [30, 40]])
    assert box.to_ltrb() == (1, 2, 30, 40)


def test_from_nested_float_rejects_malformed_input() -> None:
    with pytest.raises(ValueError, match="exactly 2 points"):
        BoundingBox.from_nested_float([[1, 2]])
    with pytest.raises(ValueError, match="exactly 2 coordinates"):
        BoundingBox.from_nested_float([[1, 2, 3], [4, 5]])
    with pytest.raises(ValueError, match="correct order"):
        BoundingBox.from_nested_float([[10, 2], [5, 40]])


def test_from_points_accepts_each_supported_point_form() -> None:
    expected = (1, 2, 30, 40)
    assert BoundingBox.from_points([Point(1, 2), Point(30, 40)]).to_ltrb() == expected
    assert (
        BoundingBox.from_points([{"x": 1, "y": 2}, {"x": 30, "y": 40}]).to_ltrb()
        == expected
    )
    assert (
        BoundingBox.from_points([ShapelyPoint(1, 2), ShapelyPoint(30, 40)]).to_ltrb()
        == expected
    )
    assert BoundingBox.from_points([(1, 2), (30, 40)]).to_ltrb() == expected


def test_from_points_accepts_a_zero_area_box() -> None:
    assert BoundingBox.from_points([Point(5, 5), Point(5, 5)]).area == 0


def test_from_points_rejects_bad_input() -> None:
    with pytest.raises(ValueError, match="exactly 2 points"):
        BoundingBox.from_points([Point(1, 1)])
    with pytest.raises(ValueError, match="'x' and 'y'"):
        BoundingBox.from_points([{"x": 1}, {"x": 3, "y": 4}])
    with pytest.raises(ValueError, match="larger or equal"):
        BoundingBox.from_points([Point(30, 40), Point(1, 2)])
    with pytest.raises(TypeError, match="Unsupported"):
        BoundingBox.from_points([(1, 2, 3), (4, 5)])


def test_scalar_properties() -> None:
    box = _px(10, 20, 50, 100)
    assert (box.minX, box.minY, box.maxX, box.maxY) == (10, 20, 50, 100)
    assert box.width == 40
    assert box.height == 80
    assert box.size == (40, 80)
    assert box.area == 3200
    assert box.y_range == (20, 100)
    assert box.horizontal_midpoint == 30
    assert box.vertical_midpoint == 60
    assert box.center == Point(30, 60)
    assert box.to_points() == (Point(10, 20), Point(50, 100))
    assert box.to_ltwh() == (10, 20, 40, 80)


def test_deprecated_aliases_warn_and_match_the_replacements() -> None:
    box = _px(10, 20, 50, 100)
    with pytest.warns(DeprecationWarning, match="to_ltrb"):
        assert box.lrtb == box.to_ltrb()
    with pytest.warns(DeprecationWarning, match="to_ltwh"):
        assert box.lrwh == box.to_ltwh()


def test_repr_can_be_read_back_as_the_factory_call() -> None:
    assert repr(_px(10, 20, 50, 100)) == "BoundingBox.from_ltrb(10, 20, 50, 100)"


def test_four_point_polygon_truncates_scaled_corners() -> None:
    box = BoundingBox.from_ltrb(0.1, 0.2, 0.5, 0.6)
    assert box.get_four_point_scaled_polygon_list(100, 200) == [
        [10, 40],
        [50, 40],
        [50, 120],
        [10, 120],
    ]


def test_finite_box_has_usable_coordinates() -> None:
    assert _px(0, 0, 10, 10).has_usable_coordinates


def test_infinite_corner_is_not_usable() -> None:
    box = BoundingBox(Point(0, 0), Point(10, float("inf")), is_normalized=False)
    assert not box.has_usable_coordinates


def test_scale_converts_to_pixels() -> None:
    scaled = BoundingBox.from_ltrb(0.1, 0.2, 0.5, 0.6).scale(200, 100)
    assert scaled.is_normalized is False
    assert scaled.to_ltrb() == (20, 20, 100, 60)


def test_scale_rejects_a_pixel_box() -> None:
    with pytest.raises(ValueError, match="normalized bounding box"):
        _px(10, 10, 20, 20).scale(100, 100)


def test_normalize_converts_to_the_unit_square() -> None:
    normalized = _px(20, 20, 100, 60).normalize(200, 100)
    assert normalized.is_normalized is True
    assert normalized.to_ltrb() == (0.1, 0.2, 0.5, 0.6)


def test_normalize_rejects_a_normalized_box() -> None:
    with pytest.raises(ValueError, match="already normalized"):
        BoundingBox.from_ltrb(0.1, 0.1, 0.2, 0.2).normalize(100, 100)


def test_to_scaled_ltwh_is_pixel_size() -> None:
    box = BoundingBox.from_ltrb(0.1, 0.2, 0.5, 0.6)
    assert box.to_scaled_ltwh(200, 100) == (20, 20, 80, 40)


def test_contains_point_includes_the_edges() -> None:
    box = _px(10, 10, 20, 20)
    assert box.contains_point(Point(10, 10))
    assert box.contains_point(Point(20, 20))
    assert box.contains_point(Point(15, 12))
    assert not box.contains_point(Point(21, 15))
    assert not box.contains_point(Point(15, 9))


def test_split_x_offset_divides_the_width() -> None:
    left, right = _px(10, 0, 50, 20).split_x_offset(15)
    assert left.to_ltrb() == (10, 0, 25, 20)
    assert right.to_ltrb() == (25, 0, 50, 20)


def test_split_at_an_edge_gives_a_zero_width_side() -> None:
    left, right = _px(10, 0, 50, 20).split_x_offset(0)
    assert left.width == 0
    assert right.width == 40


def test_split_x_offset_out_of_range_is_rejected() -> None:
    box = _px(10, 0, 50, 20)
    with pytest.raises(ValueError, match="x_offset"):
        box.split_x_offset(-1)
    with pytest.raises(ValueError, match="x_offset"):
        box.split_x_offset(41)


def test_split_x_absolute_uses_page_coordinates() -> None:
    left, right = _px(10, 0, 50, 20).split_x_absolute(30)
    assert left.to_ltrb() == (10, 0, 30, 20)
    assert right.to_ltrb() == (30, 0, 50, 20)


def test_split_x_absolute_out_of_range_is_rejected() -> None:
    box = _px(10, 0, 50, 20)
    with pytest.raises(ValueError, match="split x"):
        box.split_x_absolute(9)
    with pytest.raises(ValueError, match="split x"):
        box.split_x_absolute(51)


def test_intersection_is_the_shared_rectangle() -> None:
    inter = _px(0, 0, 10, 10).intersection(_px(5, 5, 20, 20))
    assert inter is not None
    assert inter.to_ltrb() == (5, 5, 10, 10)


def test_edge_touching_boxes_intersect_but_have_no_intersection_box() -> None:
    a = _px(0, 0, 10, 10)
    b = _px(10, 0, 20, 10)
    assert a.intersects(b)
    assert a.intersection(b) is None


def test_disjoint_boxes_do_not_intersect() -> None:
    a = _px(0, 0, 10, 10)
    b = _px(20, 20, 30, 30)
    assert not a.intersects(b)
    assert a.intersection(b) is None


def test_intersection_of_normalized_boxes_stays_normalized() -> None:
    a = BoundingBox.from_ltrb(0.0, 0.0, 0.5, 0.5)
    b = BoundingBox.from_ltrb(0.25, 0.25, 0.75, 0.75)
    inter = a.intersection(b)
    assert inter is not None
    assert inter.is_normalized is True


def test_mixed_coordinate_systems_are_rejected() -> None:
    normalized = BoundingBox.from_ltrb(0.1, 0.1, 0.5, 0.5)
    pixel = _px(0, 0, 10, 10)
    with pytest.raises(ValueError, match="share coordinate system"):
        normalized.intersects(pixel)
    with pytest.raises(ValueError, match="share coordinate system"):
        normalized.intersection(pixel)
    with pytest.raises(ValueError, match="share coordinate system"):
        normalized.iou(pixel)
    with pytest.raises(ValueError, match="share coordinate system"):
        normalized.overlap_x_amount(pixel)
    with pytest.raises(ValueError, match="share coordinate system"):
        normalized.overlap_y_amount(pixel)


def test_overlap_amounts_are_projection_lengths() -> None:
    a = _px(0, 0, 10, 10)
    b = _px(4, 7, 30, 40)
    assert a.overlap_x_amount(b) == 6
    assert a.overlap_y_amount(b) == 3
    assert a.overlap_x_amount(_px(50, 0, 60, 10)) == 0


def test_union_covers_every_box() -> None:
    merged = BoundingBox.union([_px(0, 5, 10, 10), _px(20, 0, 30, 8), _px(5, 5, 6, 40)])
    assert merged.to_ltrb() == (0, 0, 30, 40)
    assert merged.is_normalized is False


def test_union_of_normalized_boxes_stays_normalized() -> None:
    merged = BoundingBox.union(
        [
            BoundingBox.from_ltrb(0.1, 0.1, 0.2, 0.2),
            BoundingBox.from_ltrb(0.5, 0.5, 0.9, 0.6),
        ]
    )
    assert merged.is_normalized is True
    assert merged.to_ltrb() == (0.1, 0.1, 0.9, 0.6)


def test_union_rejects_empty_input_and_mixed_systems() -> None:
    with pytest.raises(ValueError, match="empty"):
        BoundingBox.union([])
    with pytest.raises(ValueError, match="share coordinate system"):
        BoundingBox.union(
            [_px(0, 0, 10, 10), BoundingBox.from_ltrb(0.1, 0.1, 0.2, 0.2)]
        )


def test_union_with_matches_the_class_union() -> None:
    a = _px(0, 0, 10, 10)
    b = _px(5, 5, 20, 30)
    assert a.union_with(b) == BoundingBox.union([a, b])


def test_iou_of_identical_boxes_is_one() -> None:
    assert math.isclose(_px(0, 0, 10, 10).iou(_px(0, 0, 10, 10)), 1.0)


def test_iou_of_half_overlapping_boxes_is_one_third() -> None:
    assert math.isclose(_px(0, 0, 10, 10).iou(_px(5, 0, 15, 10)), 1 / 3)


def test_iou_of_disjoint_boxes_is_zero() -> None:
    assert _px(0, 0, 10, 10).iou(_px(50, 50, 60, 60)) == 0.0


def test_iou_of_zero_area_boxes_is_zero() -> None:
    assert _px(5, 5, 5, 5).iou(_px(5, 5, 5, 5)) == 0.0


def test_expand_by_zero_returns_an_equal_copy() -> None:
    box = _px(10, 10, 20, 20)
    same = box.expand()
    assert same == box
    assert same is not box


def test_uniform_expand_grows_every_side_with_square_corners() -> None:
    assert _px(10, 10, 20, 20).expand(5, 5).to_ltrb() == (5, 5, 25, 25)


def test_uniform_shrink_pulls_every_side_in() -> None:
    assert _px(10, 10, 30, 30).expand(-4, -4).to_ltrb() == (14, 14, 26, 26)


def test_uniform_shrink_past_the_centre_is_rejected() -> None:
    with pytest.raises(ValueError, match="collapse"):
        _px(10, 10, 20, 20).expand(-6, -6)


def test_anisotropic_expand_keeps_the_centre() -> None:
    assert _px(10, 10, 20, 30).expand(dx=2, dy=0).to_ltrb() == (8, 10, 22, 30)


def test_anisotropic_shrink_past_zero_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative size"):
        _px(10, 10, 20, 30).expand(dx=-6, dy=1)


def test_clamp_pixel_box_to_the_image() -> None:
    clamped = _px(0, 10, 120, 300).clamp_to_image(100, 200)
    assert clamped is not None
    assert clamped.to_ltrb() == (0, 10, 100, 200)
    assert clamped.is_normalized is False


def test_clamp_leaves_an_inside_box_unchanged() -> None:
    box = _px(10, 10, 20, 20)
    assert box.clamp_to_image(100, 100) == box


def test_clamp_returns_none_when_entirely_outside() -> None:
    assert _px(150, 10, 200, 20).clamp_to_image(100, 100) is None
    assert _px(10, 150, 20, 200).clamp_to_image(100, 100) is None


def test_clamp_returns_none_for_a_zero_area_box() -> None:
    assert _px(10, 10, 10, 20).clamp_to_image(100, 100) is None


def test_clamp_ignores_image_size_for_a_normalized_box() -> None:
    normalized = BoundingBox.from_ltrb(0.2, 0.2, 0.6, 0.6)
    assert normalized.clamp_to_image(10, 10) == normalized


def test_clamp_returns_none_for_a_zero_area_normalized_box() -> None:
    assert BoundingBox.from_ltrb(0.5, 0.2, 0.5, 0.6).clamp_to_image(10, 10) is None


def test_dict_round_trip_keeps_corners_and_flags() -> None:
    original = BoundingBox.from_ltrb(0.1, 0.2, 0.5, 0.6)
    assert BoundingBox.from_dict(original.to_dict()) == original
    pixel = _px(1, 1, 5, 5)
    assert BoundingBox.from_dict(pixel.to_dict()).is_normalized is False


def test_to_dict_has_the_documented_shape() -> None:
    assert _px(10, 20, 30, 40).to_dict() == {
        "top_left": {"x": 10, "y": 20, "is_normalized": False},
        "bottom_right": {"x": 30, "y": 40, "is_normalized": False},
        "is_normalized": False,
    }


def test_from_dict_infers_flags_when_absent() -> None:
    box = BoundingBox.from_dict(
        {
            "top_left": {"x": 0.1, "y": 0.1},
            "bottom_right": {"x": 0.9, "y": 0.9},
            "is_normalized": None,
        }
    )
    assert box.is_normalized is True


def test_json_round_trip() -> None:
    original = _px(10, 20, 30, 40)
    text = original.to_json()
    assert json.loads(text)["bottom_right"]["x"] == 30
    assert BoundingBox.from_json(text) == original


def test_from_shapely_reads_the_bounds() -> None:
    box = BoundingBox.from_shapely(shapely_box(10, 20, 30, 40))
    assert box.to_ltrb() == (10, 20, 30, 40)
    assert box.is_normalized is False
    assert BoundingBox.from_shapely(shapely_box(0.1, 0.1, 0.5, 0.5)).is_normalized


def test_as_shapely_round_trips_through_from_shapely() -> None:
    box = _px(10, 20, 30, 40)
    assert box.as_shapely().area == box.area
    assert box.shapely.bounds == (10, 20, 30, 40)
    assert BoundingBox.from_shapely(box.shapely) == box


def test_normalization_error_detection_matches_the_known_message() -> None:
    known = AttributeError("'NoneType' object has no attribute 'is_normalized'")
    assert BoundingBox.is_geometry_normalization_error(known)
    assert not BoundingBox.is_geometry_normalization_error(ValueError("other"))
    assert not BoundingBox.is_geometry_normalization_error(AttributeError("NoneType"))


def test_pydantic_round_trip_and_schema() -> None:
    adapter = TypeAdapter(BoundingBox)
    original = _px(10, 20, 30, 40)
    restored = adapter.validate_python(adapter.dump_python(original))
    assert restored == original
    assert adapter.json_schema()["required"] == [
        "top_left",
        "bottom_right",
        "is_normalized",
    ]
