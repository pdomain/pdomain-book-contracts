from __future__ import annotations

import math

from pdomain_book_contracts.layout.regions import (
    caption_for_figure,
    contains,
    horizontal_overlap_ratio,
    iou,
    region_reading_order,
)
from pdomain_book_contracts.layout.types import LayoutRegion, RegionType


def _r(
    left: int,
    top: int,
    right: int,
    bottom: int,
    kind: RegionType = RegionType.text,
) -> LayoutRegion:
    return LayoutRegion(kind, left, right, top, bottom)


def test_iou_of_identical_regions_is_one() -> None:
    assert iou(_r(0, 0, 10, 10), _r(0, 0, 10, 10)) == 1.0


def test_iou_of_half_overlapping_regions_is_one_third() -> None:
    assert math.isclose(iou(_r(0, 0, 10, 10), _r(5, 0, 15, 10)), 1 / 3)


def test_iou_is_symmetric() -> None:
    a, b = _r(0, 0, 10, 20), _r(4, 6, 30, 12)
    assert iou(a, b) == iou(b, a)


def test_iou_of_disjoint_or_touching_regions_is_zero() -> None:
    assert iou(_r(0, 0, 10, 10), _r(50, 50, 60, 60)) == 0.0
    assert iou(_r(0, 0, 10, 10), _r(10, 0, 20, 10)) == 0.0


def test_iou_of_coincident_zero_area_regions_is_zero() -> None:
    assert iou(_r(5, 5, 5, 5), _r(5, 5, 5, 5)) == 0.0


def test_iou_of_a_region_inside_another_is_the_area_ratio() -> None:
    assert math.isclose(iou(_r(0, 0, 10, 10), _r(0, 0, 5, 10)), 0.5)


def test_contains_requires_full_enclosure() -> None:
    outer = _r(10, 10, 100, 100)
    assert contains(outer, _r(20, 20, 90, 90))
    assert contains(outer, outer)
    assert not contains(outer, _r(5, 20, 90, 90))
    assert not contains(outer, _r(20, 5, 90, 90))
    assert not contains(outer, _r(20, 20, 101, 90))
    assert not contains(outer, _r(20, 20, 90, 101))


def test_contains_tolerance_is_applied_on_every_side() -> None:
    outer = _r(10, 10, 100, 100)
    inner = _r(8, 8, 102, 102)
    assert not contains(outer, inner)
    assert not contains(outer, inner, tol=1)
    assert contains(outer, inner, tol=2)


def test_horizontal_overlap_is_relative_to_the_narrower_region() -> None:
    wide = _r(0, 0, 100, 10)
    narrow = _r(50, 20, 250, 30)
    assert horizontal_overlap_ratio(wide, narrow) == 0.5
    inside = _r(10, 20, 30, 30)
    assert horizontal_overlap_ratio(wide, inside) == 1.0


def test_horizontal_overlap_of_separate_or_touching_regions_is_zero() -> None:
    assert horizontal_overlap_ratio(_r(0, 0, 10, 10), _r(10, 0, 20, 10)) == 0.0
    assert horizontal_overlap_ratio(_r(0, 0, 10, 10), _r(30, 0, 40, 10)) == 0.0


def test_horizontal_overlap_with_a_zero_width_region_is_zero() -> None:
    assert horizontal_overlap_ratio(_r(0, 0, 100, 10), _r(50, 0, 50, 10)) == 0.0


FIGURE = _r(100, 100, 300, 300, RegionType.figure)


def test_caption_below_the_figure_is_found() -> None:
    caption = _r(100, 320, 300, 340, RegionType.caption)
    assert caption_for_figure(FIGURE, [caption]) is caption


def test_no_regions_means_no_caption() -> None:
    assert caption_for_figure(FIGURE, []) is None


def test_the_figure_itself_and_other_types_are_never_captions() -> None:
    table = _r(100, 310, 300, 330, RegionType.table)
    assert caption_for_figure(FIGURE, [FIGURE, table]) is None


def test_gap_beyond_the_limit_is_rejected() -> None:
    far = _r(100, 381, 300, 400, RegionType.caption)
    near = _r(100, 380, 300, 400, RegionType.caption)
    assert caption_for_figure(FIGURE, [far]) is None
    assert caption_for_figure(FIGURE, [near]) is near
    assert caption_for_figure(FIGURE, [far], max_gap_px=100) is far


def test_little_horizontal_overlap_is_rejected() -> None:
    off_to_the_side = _r(290, 310, 600, 330, RegionType.caption)
    assert caption_for_figure(FIGURE, [off_to_the_side]) is None
    assert (
        caption_for_figure(FIGURE, [off_to_the_side], min_horizontal_overlap=0.03)
        is off_to_the_side
    )


def test_region_overlapping_the_figure_vertically_is_not_a_caption() -> None:
    inside = _r(100, 250, 300, 280, RegionType.caption)
    assert caption_for_figure(FIGURE, [inside]) is None


def test_explicit_caption_beats_a_closer_text_region() -> None:
    text = _r(100, 305, 300, 315)
    caption = _r(100, 350, 300, 370, RegionType.caption)
    assert caption_for_figure(FIGURE, [text, caption]) is caption
    assert caption_for_figure(FIGURE, [caption, text]) is caption


def test_text_is_the_fallback_when_there_is_no_caption() -> None:
    text = _r(100, 320, 300, 340)
    assert caption_for_figure(FIGURE, [text]) is text


def test_among_the_same_type_the_closest_wins() -> None:
    near = _r(100, 310, 300, 330, RegionType.caption)
    far = _r(100, 350, 300, 370, RegionType.caption)
    assert caption_for_figure(FIGURE, [far, near]) is near
    assert caption_for_figure(FIGURE, [near, far]) is near


def test_a_caption_above_is_ignored_unless_requested() -> None:
    above = _r(100, 50, 300, 80, RegionType.caption)
    assert caption_for_figure(FIGURE, [above]) is None
    assert caption_for_figure(FIGURE, [above], above=True) is above


def test_above_search_still_picks_the_closest_side() -> None:
    above = _r(100, 70, 300, 90, RegionType.caption)
    below = _r(100, 340, 300, 360, RegionType.caption)
    assert caption_for_figure(FIGURE, [below, above], above=True) is above
    far_above = _r(100, 20, 300, 40, RegionType.caption)
    assert caption_for_figure(FIGURE, [below, far_above], above=True) is below


def test_reading_order_of_nothing_and_of_one_region() -> None:
    assert region_reading_order([]) == []
    only = _r(0, 0, 10, 10)
    assert region_reading_order([only]) == [only]


def test_single_column_is_sorted_top_to_bottom_then_left_to_right() -> None:
    low = _r(0, 200, 100, 220)
    high_right = _r(30, 0, 100, 20)
    high_left = _r(0, 0, 40, 20)
    assert region_reading_order([low, high_right, high_left]) == [
        high_left,
        high_right,
        low,
    ]


def test_two_columns_are_read_one_after_the_other() -> None:
    left_top = _r(0, 0, 100, 50)
    left_bottom = _r(0, 300, 100, 350)
    right_top = _r(150, 10, 250, 60)
    right_bottom = _r(150, 100, 250, 150)
    shuffled = [right_bottom, left_bottom, right_top, left_top]
    assert region_reading_order(shuffled) == [
        left_top,
        left_bottom,
        right_top,
        right_bottom,
    ]


def test_three_columns_are_read_left_to_right() -> None:
    cols = [_r(x, 0, x + 80, 40) for x in (0, 100, 200)]
    below = [_r(x, 100, x + 80, 140) for x in (0, 100, 200)]
    result = region_reading_order(
        [below[2], cols[1], below[0], cols[2], below[1], cols[0]]
    )
    assert result == [cols[0], below[0], cols[1], below[1], cols[2], below[2]]


def test_full_width_header_falls_back_to_top_then_left_order() -> None:
    header = _r(0, 0, 250, 20)
    left = _r(0, 100, 100, 200)
    right = _r(150, 30, 250, 130)
    assert region_reading_order([right, left, header]) == [header, right, left]


def test_reading_order_keeps_every_region_exactly_once() -> None:
    regions = [
        _r(0, 0, 100, 50),
        _r(150, 0, 250, 50),
        _r(0, 60, 100, 90),
        _r(0, 0, 100, 50),
    ]
    result = region_reading_order(regions)
    assert len(result) == 4
    assert sorted(result, key=id) == sorted(regions, key=id)
