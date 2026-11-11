from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdomain_book_contracts.geometry.bounding_box import BoundingBox
from pdomain_book_contracts.matching.alignment import (
    AlignmentConfig,
    AlignmentEdit,
    AlignmentEditKind,
    ProjectedBoundingBox,
    ProjectedStyleSpan,
    TokenAlignmentResult,
    align_tokens,
    project_style_span,
    project_token_ranges,
)
from pdomain_book_contracts.typography.labels import (
    ConfidenceTier,
    KnowledgeState,
    LabelSource,
    StyleLabel,
)
from pdomain_book_contracts.typography.normalization import (
    ComparisonOperationKind,
    build_comparison_view,
)
from pdomain_book_contracts.typography.records import (
    AlignmentPathOperation,
    OcrTokenRef,
)
from pdomain_book_contracts.typography.spans import StyleSpan

_HASH = "ab" * 32
_PIECE_ID = "piece"
_SHY = chr(0xAD)
_SHARP_S = chr(0xDF)


def _token(
    token_id: str, text: str, *, start: int = 0, end: int = 1, bbox_x: float = 0.0
) -> OcrTokenRef:
    return OcrTokenRef(
        token_id=token_id,
        text=text,
        confidence=None,
        bbox=BoundingBox.from_ltrb(bbox_x, 0, bbox_x + 10, 10),
        line_id="line",
        grapheme_start=start,
        grapheme_end=end,
        alignment_id="unbound",
    )


def _align(
    source: str,
    targets: tuple[str, ...],
    *,
    config: AlignmentConfig | None = None,
    small_caps: tuple[tuple[int, int], ...] = (),
) -> TokenAlignmentResult:
    view = build_comparison_view(source, small_caps_ranges=small_caps)
    tokens = tuple(_token(f"t{i}", text) for i, text in enumerate(targets))
    return align_tokens(view, tokens, config=config)


def _kinds(result: TokenAlignmentResult) -> list[str]:
    return [edit.kind.value for edit in result.best_path]


def _style(start: int, end: int) -> StyleSpan:
    return StyleSpan(
        label=StyleLabel.ITALIC,
        start=start,
        end=end,
        state=KnowledgeState.POSITIVE,
        label_source=LabelSource.F2,
        confidence_tier=ConfidenceTier.GOLD,
        source_slices=(),
        rule_ref=None,
        semantic_reason=None,
        warnings=(),
    )


def _result_payload(result: TokenAlignmentResult) -> dict[str, object]:
    return dict(result.model_dump())


def test_identical_text_aligns_with_zero_cost_matches() -> None:
    result = _align("abc", ("abc",))
    assert result.best_cost == 0
    assert _kinds(result) == ["match", "match", "match"]
    assert result.token_source_ranges == ((0, 3),)
    assert result.source_grapheme_count == 3
    assert result.target_grapheme_count == 3


def test_a_differing_character_is_one_substitution() -> None:
    result = _align("abc", ("abd",))
    assert result.best_cost == 1
    assert _kinds(result) == ["match", "match", "substitution"]


def test_case_differs_outside_small_caps_but_not_inside_them() -> None:
    assert _align("Ab", ("ab",)).best_cost == 1
    folded = _align("AB", ("ab",), small_caps=((0, 2),))
    assert folded.best_cost == 0
    assert _kinds(folded) == ["match", "match"]


def test_small_caps_target_case_fold_is_recorded_per_target_grapheme() -> None:
    result = _align("AB", ("Ab",), small_caps=((0, 2),))
    operations = result.target_normalization_operations
    assert [op.kind for op in operations] == [
        ComparisonOperationKind.SMALL_CAPS_CASE_FOLDED
    ]
    assert operations[0].original_text == "A"
    assert operations[0].input_range == (0, 1)


def test_unfolded_target_leaves_no_case_fold_operations() -> None:
    assert (
        _align("Ab", ("ab",), small_caps=((0, 1),)).target_normalization_operations
        == ()
    )


def test_extra_source_text_is_deleted_and_extra_target_text_is_inserted() -> None:
    deleted = _align("abcd", ("ab",))
    assert deleted.best_cost == 2
    assert _kinds(deleted) == [
        "match",
        "match",
        "source_only_deletion",
        "source_only_deletion",
    ]
    assert deleted.best_path[-1].target_range == (2, 2)
    inserted = _align("ab", ("abcd",))
    assert inserted.best_cost == 2
    assert inserted.best_path[-1].kind is AlignmentEditKind.TARGET_ONLY_INSERTION
    assert inserted.best_path[-1].source_range == (2, 2)
    assert inserted.best_path[-1].target_range == (3, 4)


def test_empty_inputs_align_without_a_runner_up() -> None:
    both = _align("", ())
    assert both.best_path == ()
    assert both.best_cost == 0
    assert both.runner_up_margin is None
    assert both.accepted is True
    only_target = _align("", ("ab",))
    assert only_target.best_cost == 2
    assert only_target.token_source_ranges == (None,)


def test_tokens_are_bound_to_the_source_span_they_cover_across_a_gap() -> None:
    result = _align("ab cd", ("ab", "cd"))
    assert result.token_source_ranges == ((0, 2), (3, 5))
    assert result.best_cost == 1
    assert result.best_path[2].kind is AlignmentEditKind.SOURCE_ONLY_DELETION


def test_soft_hyphen_in_the_target_is_removed_from_comparison_only() -> None:
    result = _align("ab", ("a" + _SHY + "b",))
    assert result.best_cost == 0
    assert result.target_grapheme_count == 3
    assert result.best_path[-1].target_range == (2, 3)
    assert [op.kind for op in result.target_normalization_operations] == [
        ComparisonOperationKind.SOFT_HYPHEN_REMOVED
    ]


def test_target_only_token_has_no_source_range_and_is_dropped_on_projection() -> None:
    result = _align("ab", ("ab", "zzzz"))
    assert result.token_source_ranges == ((0, 2), None)
    projected = project_token_ranges(
        (_token("t0", "ab"), _token("t1", "zzzz")), result, alignment_id="align-1"
    )
    assert [token.token_id for token in projected] == ["t0"]
    assert (projected[0].grapheme_start, projected[0].grapheme_end) == (0, 2)
    assert projected[0].alignment_id == "align-1"


def test_projection_keeps_token_order_and_binds_each_range() -> None:
    tokens = (_token("t0", "ab"), _token("t1", "cd"))
    result = align_tokens(build_comparison_view("abcd"), tokens)
    projected = project_token_ranges(tokens, result, alignment_id="a")
    assert [(t.token_id, t.grapheme_start, t.grapheme_end) for t in projected] == [
        ("t0", 0, 2),
        ("t1", 2, 4),
    ]


def test_low_margin_alignment_is_not_accepted_and_cannot_be_projected() -> None:
    config = AlignmentConfig(low_margin_threshold=5.0)
    result = _align("ab", ("ab",), config=config)
    assert result.runner_up_margin == 2.0
    assert result.accepted is False
    assert result.runner_up_path is not None
    with pytest.raises(ValueError, match="unaccepted alignment"):
        project_token_ranges((_token("t0", "ab"),), result, alignment_id="a")


def test_margin_equal_to_threshold_is_accepted() -> None:
    result = _align("ab", ("ab",), config=AlignmentConfig(low_margin_threshold=2.0))
    assert result.runner_up_margin == 2.0
    assert result.accepted is True


def test_projection_rejects_a_token_count_that_differs_from_the_alignment() -> None:
    result = _align("ab", ("ab",))
    with pytest.raises(ValueError, match="token count must match"):
        project_token_ranges(
            (_token("t0", "ab"), _token("t1", "x")), result, alignment_id="a"
        )


def test_alignment_is_deterministic() -> None:
    first = _align("the cat sat", ("the", "cot", "sat"))
    second = _align("the cat sat", ("the", "cot", "sat"))
    assert first == second
    assert first.to_json_bytes() == second.to_json_bytes()


def test_alignment_result_round_trips_through_canonical_json() -> None:
    result = _align("abc def", ("abx", "def"))
    assert TokenAlignmentResult.from_json_bytes(result.to_json_bytes()) == result


def test_evidence_describes_the_best_path_and_runner_up() -> None:
    result = _align("abc", ("abd",))
    evidence = result.to_evidence(
        alignment_id="evidence-1",
        source_artifact_sha256=_HASH,
        target_artifact_sha256="cd" * 32,
    )
    assert evidence.method == "monotonic_grapheme_dp_v1"
    assert evidence.operations == (
        "match:0:1:0:1",
        "match:1:2:1:2",
        "substitution:2:3:2:3",
    )
    assert evidence.score == -1.0
    assert evidence.margin == result.runner_up_margin
    assert evidence.low_margin_threshold == 1.0
    assert evidence.accepted is True
    assert evidence.source_range == (0, 3)
    assert evidence.target_range == (0, 3)
    assert result.runner_up_path is not None
    assert evidence.runner_up_operations == tuple(
        AlignmentPathOperation(
            kind=edit.kind.value,
            source_range=edit.source_range,
            target_range=edit.target_range,
        )
        for edit in result.runner_up_path
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_config_rejects_non_finite_threshold(value: float) -> None:
    with pytest.raises(ValidationError):
        AlignmentConfig(low_margin_threshold=value)


def test_config_rejects_negative_threshold() -> None:
    with pytest.raises(ValidationError):
        AlignmentConfig(low_margin_threshold=-0.5)


def test_edit_rejects_reversed_ranges() -> None:
    with pytest.raises(ValidationError, match="must be ordered"):
        AlignmentEdit(
            kind=AlignmentEditKind.MATCH, source_range=(2, 1), target_range=(0, 1)
        )


@pytest.mark.parametrize(
    ("kind", "source", "target", "message"),
    [
        (AlignmentEditKind.MATCH, (0, 1), (0, 0), "match and substitution"),
        (AlignmentEditKind.SUBSTITUTION, (0, 0), (0, 1), "match and substitution"),
        (AlignmentEditKind.SOURCE_ONLY_DELETION, (0, 1), (0, 1), "only source"),
        (AlignmentEditKind.SOURCE_ONLY_DELETION, (0, 0), (0, 0), "only source"),
        (AlignmentEditKind.TARGET_ONLY_INSERTION, (0, 1), (0, 1), "only target"),
        (AlignmentEditKind.TARGET_ONLY_INSERTION, (0, 0), (0, 0), "only target"),
    ],
)
def test_edit_rejects_ranges_that_contradict_its_kind(
    kind: AlignmentEditKind,
    source: tuple[int, int],
    target: tuple[int, int],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        AlignmentEdit(kind=kind, source_range=source, target_range=target)


def test_edit_accepts_a_valid_deletion_and_insertion() -> None:
    deletion = AlignmentEdit(
        kind=AlignmentEditKind.SOURCE_ONLY_DELETION,
        source_range=(1, 2),
        target_range=(3, 3),
    )
    insertion = AlignmentEdit(
        kind=AlignmentEditKind.TARGET_ONLY_INSERTION,
        source_range=(1, 1),
        target_range=(3, 4),
    )
    assert deletion.target_range == (3, 3)
    assert insertion.source_range == (1, 1)


def test_projected_box_returns_ltrb_order() -> None:
    box = ProjectedBoundingBox(
        left=1.0, top=2.0, right=3.0, bottom=4.0, is_normalized=False
    )
    assert box.to_ltrb() == (1.0, 2.0, 3.0, 4.0)


@pytest.mark.parametrize(
    ("coordinates", "normalized", "message"),
    [
        ((float("nan"), 0.0, 1.0, 1.0), False, "finite"),
        ((0.0, 0.0, float("inf"), 1.0), False, "finite"),
        ((5.0, 0.0, 1.0, 1.0), False, "ordered"),
        ((0.0, 5.0, 1.0, 1.0), False, "ordered"),
        ((-1.0, 0.0, 1.0, 1.0), False, "nonnegative"),
        ((0.0, 0.0, 1.5, 1.0), True, r"within \[0, 1\]"),
    ],
)
def test_projected_box_rejects_invalid_coordinates(
    coordinates: tuple[float, float, float, float], normalized: bool, message: str
) -> None:
    left, top, right, bottom = coordinates
    with pytest.raises(ValidationError, match=message):
        ProjectedBoundingBox(
            left=left, top=top, right=right, bottom=bottom, is_normalized=normalized
        )


def test_projected_box_allows_pixel_coordinates_above_one() -> None:
    box = ProjectedBoundingBox(
        left=0.0, top=0.0, right=640.0, bottom=480.0, is_normalized=False
    )
    assert box.right == 640.0


def test_style_span_snapshots_live_boxes_into_immutable_ones() -> None:
    projected = ProjectedStyleSpan(
        source_span_id="s",
        source_span=_style(2, 8),
        token_id=_PIECE_ID,
        source_range=(3, 5),
        crop_bbox=BoundingBox.from_ltrb(0, 0, 10, 10),
        character_boxes=[
            BoundingBox.from_ltrb(0, 0, 5, 10),
            BoundingBox.from_ltrb(5, 0, 10, 10),
        ],
    )
    assert projected.crop_bbox == ProjectedBoundingBox(
        left=0.0, top=0.0, right=10.0, bottom=10.0, is_normalized=False
    )
    assert isinstance(projected.character_boxes, tuple)
    assert [box.to_ltrb() for box in projected.character_boxes] == [
        (0.0, 0.0, 5.0, 10.0),
        (5.0, 0.0, 10.0, 10.0),
    ]


def test_style_span_without_character_boxes_keeps_none() -> None:
    projected = ProjectedStyleSpan(
        source_span_id="s",
        source_span=_style(0, 4),
        token_id=_PIECE_ID,
        source_range=(0, 4),
        crop_bbox=BoundingBox.from_ltrb(0.1, 0.1, 0.5, 0.5),
    )
    assert projected.character_boxes is None
    assert isinstance(projected.crop_bbox, ProjectedBoundingBox)
    assert projected.crop_bbox.is_normalized is True


@pytest.mark.parametrize(
    ("source_range", "message"),
    [
        ((3, 3), "nonempty"),
        ((1, 4), "lie within source_span"),
        ((3, 9), "lie within source_span"),
    ],
)
def test_style_span_rejects_a_source_range_outside_its_span(
    source_range: tuple[int, int], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        ProjectedStyleSpan(
            source_span_id="s",
            source_span=_style(2, 8),
            token_id=_PIECE_ID,
            source_range=source_range,
            crop_bbox=BoundingBox.from_ltrb(0, 0, 10, 10),
        )


def test_style_span_rejects_character_boxes_in_another_coordinate_system() -> None:
    with pytest.raises(ValidationError, match="crop_bbox coordinate system"):
        ProjectedStyleSpan(
            source_span_id="s",
            source_span=_style(2, 8),
            token_id=_PIECE_ID,
            source_range=(2, 4),
            crop_bbox=BoundingBox.from_ltrb(0, 0, 10, 10),
            character_boxes=[BoundingBox.from_ltrb(0.1, 0.1, 0.2, 0.2)],
        )


def test_style_span_rejects_a_box_without_a_declared_coordinate_system() -> None:
    box = BoundingBox.from_ltrb(0, 0, 10, 10)
    box.is_normalized = None
    with pytest.raises(ValidationError, match="declare its coordinate system"):
        ProjectedStyleSpan(
            source_span_id="s",
            source_span=_style(2, 8),
            token_id=_PIECE_ID,
            source_range=(2, 4),
            crop_bbox=box,
        )


def test_style_span_is_split_at_each_overlapping_token() -> None:
    tokens = (
        _token("early", "aa", start=0, end=2, bbox_x=0),
        _token("first", "bb", start=0, end=4, bbox_x=20),
        _token("second", "cc", start=4, end=6, bbox_x=40),
        _token("third", "dd", start=6, end=10, bbox_x=60),
        _token("late", "ee", start=10, end=12, bbox_x=80),
    )
    span = _style(2, 8)
    pieces = project_style_span(span, source_span_id="span-1", tokens=tokens)
    assert [(p.token_id, p.source_range) for p in pieces] == [
        ("first", (2, 4)),
        ("second", (4, 6)),
        ("third", (6, 8)),
    ]
    assert all(piece.source_span == span for piece in pieces)
    assert all(piece.source_span_id == "span-1" for piece in pieces)
    assert isinstance(pieces[1].crop_bbox, ProjectedBoundingBox)
    assert pieces[1].crop_bbox.left == 40.0


def test_style_span_projection_ignores_touching_tokens() -> None:
    tokens = (
        _token("before", "a", start=0, end=2),
        _token("after", "b", start=8, end=9),
    )
    assert project_style_span(_style(2, 8), source_span_id="s", tokens=tokens) == ()


def _valid_payload() -> dict[str, object]:
    return _result_payload(
        _align("ab", ("ab",), config=AlignmentConfig(low_margin_threshold=0.0))
    )


def test_result_rejects_acceptance_that_contradicts_the_margin() -> None:
    payload = _valid_payload()
    payload["accepted"] = False
    with pytest.raises(ValidationError, match="accepted must match"):
        TokenAlignmentResult.model_validate(payload)


@pytest.mark.parametrize("margin", [-1.0, float("inf"), float("nan")])
def test_result_rejects_invalid_margin(margin: float) -> None:
    payload = _valid_payload()
    payload["runner_up_margin"] = margin
    with pytest.raises(ValidationError, match="finite and nonnegative"):
        TokenAlignmentResult.model_validate(payload)


def test_result_rejects_runner_up_normalization_without_a_runner_up_path() -> None:
    payload = _valid_payload()
    payload["runner_up_path"] = None
    payload["runner_up_margin"] = None
    payload["accepted"] = True
    payload["runner_up_target_normalization_operations"] = ()
    with pytest.raises(ValidationError, match="require a runner-up path"):
        TokenAlignmentResult.model_validate(payload)


def test_result_rejects_paths_beyond_the_grapheme_counts() -> None:
    payload = _valid_payload()
    payload["source_grapheme_count"] = 1
    with pytest.raises(ValidationError, match="best_path source_range exceeds"):
        TokenAlignmentResult.model_validate(payload)
    payload = _valid_payload()
    payload["target_grapheme_count"] = 1
    with pytest.raises(ValidationError, match="best_path target_range exceeds"):
        TokenAlignmentResult.model_validate(payload)


def test_result_validates_the_runner_up_path_too() -> None:
    payload = _valid_payload()
    payload["target_grapheme_count"] = 1
    payload["best_path"] = ()
    with pytest.raises(ValidationError, match="runner_up_path target_range exceeds"):
        TokenAlignmentResult.model_validate(payload)


def _edit(source: tuple[int, int], target: tuple[int, int]) -> AlignmentEdit:
    return AlignmentEdit(
        kind=AlignmentEditKind.MATCH, source_range=source, target_range=target
    )


def test_result_rejects_descending_and_partially_overlapping_paths() -> None:
    payload = _valid_payload()
    payload["source_grapheme_count"] = 4
    payload["target_grapheme_count"] = 4
    payload["best_path"] = (_edit((2, 3), (2, 3)), _edit((0, 1), (3, 4)))
    with pytest.raises(ValidationError, match="source_range must be non-descending"):
        TokenAlignmentResult.model_validate(payload)
    payload["best_path"] = (_edit((0, 1), (2, 3)), _edit((1, 2), (0, 1)))
    with pytest.raises(ValidationError, match="target_range must be non-descending"):
        TokenAlignmentResult.model_validate(payload)
    payload["best_path"] = (_edit((0, 2), (0, 2)), _edit((1, 3), (2, 4)))
    with pytest.raises(ValidationError, match="source_range ranges cannot partially"):
        TokenAlignmentResult.model_validate(payload)
    payload["best_path"] = (_edit((0, 2), (0, 2)), _edit((2, 4), (1, 3)))
    with pytest.raises(ValidationError, match="target_range ranges cannot partially"):
        TokenAlignmentResult.model_validate(payload)


@pytest.mark.parametrize(
    ("ranges", "message"),
    [
        (((1, 1),), "must be nonempty"),
        (((0, 5),), "cannot exceed source_grapheme_count"),
        (((0, 2), (1, 2)), "cannot overlap"),
    ],
)
def test_result_rejects_invalid_token_source_ranges(
    ranges: tuple[tuple[int, int], ...], message: str
) -> None:
    payload = _valid_payload()
    payload["token_source_ranges"] = ranges
    with pytest.raises(ValidationError, match=message):
        TokenAlignmentResult.model_validate(payload)


def test_result_allows_unbound_tokens_between_bound_ones() -> None:
    payload = _valid_payload()
    payload["token_source_ranges"] = ((0, 1), None, (1, 2))
    result = TokenAlignmentResult.model_validate(payload)
    assert result.token_source_ranges == ((0, 1), None, (1, 2))


def test_target_letter_that_expands_on_casefold_matches_its_source_letter() -> None:
    result = _align(_SHARP_S, (_SHARP_S,))
    assert result.best_cost == 0
    assert _kinds(result) == ["match"]
    assert result.target_grapheme_count == 1


def test_small_caps_source_matches_a_target_letter_that_casefolds_to_two() -> None:
    result = _align("SS", (_SHARP_S,), small_caps=((0, 2),))
    assert result.best_cost == 0
    assert _kinds(result) == ["match", "match"]
    assert result.token_source_ranges == ((0, 2),)
    assert result.target_grapheme_count == 1
