from __future__ import annotations

import pytest

from pdomain_book_contracts.layout.types import (
    LayoutRegion,
    PageLayout,
    RegionType,
)


def _region(
    left: int = 10,
    top: int = 20,
    right: int = 110,
    bottom: int = 70,
    kind: RegionType = RegionType.text,
) -> LayoutRegion:
    return LayoutRegion(kind, left, right, top, bottom)


def test_geometry_properties() -> None:
    region = _region()
    assert region.width == 100
    assert region.height == 50
    assert region.area == 5000
    assert region.center == (60.0, 45.0)


def test_zero_size_region_is_accepted_with_zero_area() -> None:
    assert _region(10, 20, 10, 70).area == 0
    assert _region(10, 20, 110, 20).area == 0


def test_inverted_rectangles_are_rejected() -> None:
    with pytest.raises(ValueError, match="L > R"):
        _region(left=50, right=10)
    with pytest.raises(ValueError, match="T > B"):
        _region(top=50, bottom=10)


def test_negative_coordinates_are_clamped_to_zero() -> None:
    region = _region(left=-5, top=-8, right=40, bottom=30)
    assert (region.L, region.T, region.R, region.B) == (0, 0, 40, 30)


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("nan"), float("inf")])
def test_bad_confidence_is_rejected(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        LayoutRegion(RegionType.text, 0, 10, 0, 10, confidence=confidence)


@pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
def test_confidence_bounds_are_inclusive(confidence: float) -> None:
    region = LayoutRegion(RegionType.text, 0, 10, 0, 10, confidence=confidence)
    assert region.confidence == confidence


def test_contains_point_includes_the_edges() -> None:
    region = _region()
    assert region.contains_point(10, 20)
    assert region.contains_point(110, 70)
    assert region.contains_point(60.5, 45.5)
    assert not region.contains_point(9.9, 45)
    assert not region.contains_point(60, 70.1)


def test_to_dict_uses_string_type_value() -> None:
    region = LayoutRegion(RegionType.figure, 1, 2, 3, 4, 0.75, "Picture")
    assert region.to_dict() == {
        "type": "figure",
        "L": 1,
        "R": 2,
        "T": 3,
        "B": 4,
        "confidence": 0.75,
        "raw_label": "Picture",
    }


def test_region_dict_round_trip() -> None:
    original = LayoutRegion(RegionType.page_number, 1, 20, 3, 40, 0.5, "folio")
    assert LayoutRegion.from_dict(dict(original.to_dict())) == original


def test_from_dict_defaults_confidence_and_label() -> None:
    region = LayoutRegion.from_dict({"type": "caption", "L": 0, "R": 5, "T": 0, "B": 5})
    assert region.type is RegionType.caption
    assert region.confidence == 1.0
    assert region.raw_label == ""


def test_from_dict_rejects_an_unknown_type() -> None:
    with pytest.raises(ValueError, match="not a valid"):
        LayoutRegion.from_dict({"type": "bogus", "L": 0, "R": 5, "T": 0, "B": 5})


def test_from_dict_requires_coordinates() -> None:
    with pytest.raises(KeyError):
        LayoutRegion.from_dict({"type": "text", "L": 0, "R": 5, "T": 0})


def test_equal_regions_hash_alike() -> None:
    assert len({_region(), _region(), _region(right=111)}) == 2


def test_region_type_is_a_string_enum() -> None:
    assert RegionType.page_number == "page_number"
    assert RegionType("sidenote") is RegionType.sidenote


def test_page_layout_defaults_are_empty() -> None:
    layout = PageLayout()
    assert len(layout) == 0
    assert list(layout) == []
    assert layout.detector == ""


def test_page_layout_iterates_and_counts_regions() -> None:
    a, b = _region(), _region(kind=RegionType.figure)
    layout = PageLayout(regions=[a, b])
    assert len(layout) == 2
    assert list(layout) == [a, b]


def test_page_layout_instances_do_not_share_region_lists() -> None:
    first, second = PageLayout(), PageLayout()
    first.regions.append(_region())
    assert second.regions == []


def test_of_type_filters_in_order_and_accepts_several_types() -> None:
    text = _region()
    figure = _region(kind=RegionType.figure)
    caption = _region(kind=RegionType.caption)
    layout = PageLayout(regions=[text, figure, caption, _region()])
    assert layout.of_type(RegionType.figure) == [figure]
    assert layout.of_type(RegionType.caption, RegionType.figure) == [figure, caption]
    assert layout.of_type(RegionType.table) == []


def test_of_type_with_no_types_is_an_error() -> None:
    with pytest.raises(ValueError, match="at least one RegionType"):
        PageLayout(regions=[_region()]).of_type()


def test_page_layout_dict_round_trip() -> None:
    original = PageLayout(
        regions=[_region(), _region(kind=RegionType.footnote)],
        image_width=800,
        image_height=1200,
        detector="pp-doclayout",
        inference_ms=42,
    )
    assert PageLayout.from_dict(dict(original.to_dict())) == original


def test_page_layout_from_empty_dict_uses_defaults() -> None:
    assert PageLayout.from_dict({}) == PageLayout()
