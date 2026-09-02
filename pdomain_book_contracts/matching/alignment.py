from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Annotated, Self

from pydantic import Field, field_validator, model_validator

from pdomain_book_contracts.geometry.bounding_box import BoundingBox
from pdomain_book_contracts.text.normalization import (
    ComparisonOperation,
    ComparisonOperationKind,
    ComparisonView,
    build_comparison_view,
)
from pdomain_book_contracts.typography.records import (
    AlignmentEvidence,
    AlignmentPathOperation,
    OcrTokenRef,
    SourceCoordinateSpace,
    TargetCoordinateSpace,
)
from pdomain_book_contracts.typography.spans import (
    CanonicalModel,
    StyleSpan,
    split_graphemes,
)

_StrictIndex = Annotated[int, Field(strict=True, ge=0)]


class AlignmentEditKind(StrEnum):
    """A monotonic edit used to align source and OCR comparison graphemes."""

    MATCH = "match"
    SUBSTITUTION = "substitution"
    SOURCE_ONLY_DELETION = "source_only_deletion"
    TARGET_ONLY_INSERTION = "target_only_insertion"


class AlignmentConfig(CanonicalModel):
    """Versioned alignment settings that determine acceptance."""

    low_margin_threshold: Annotated[float, Field(ge=0.0)] = 1.0

    @field_validator("low_margin_threshold")
    @classmethod
    def _validate_threshold(cls, value: float) -> float:
        if not isfinite(value):
            msg = "low_margin_threshold must be finite"
            raise ValueError(msg)
        return value


class AlignmentEdit(CanonicalModel):
    """One source-to-target monotonic edit in canonical grapheme coordinates."""

    kind: AlignmentEditKind
    source_range: tuple[_StrictIndex, _StrictIndex]
    target_range: tuple[_StrictIndex, _StrictIndex]

    @model_validator(mode="after")
    def _validate_ranges(self) -> Self:
        source_start, source_end = self.source_range
        target_start, target_end = self.target_range
        if source_start > source_end or target_start > target_end:
            msg = "alignment edit ranges must be ordered"
            raise ValueError(msg)
        source_consumed = source_start < source_end
        target_consumed = target_start < target_end
        if self.kind in {
            AlignmentEditKind.MATCH,
            AlignmentEditKind.SUBSTITUTION,
        } and not (source_consumed and target_consumed):
            msg = "match and substitution edits must consume both source and target"
            raise ValueError(msg)
        if self.kind is AlignmentEditKind.SOURCE_ONLY_DELETION and not (
            source_consumed and not target_consumed
        ):
            msg = "source-only deletion must consume only source"
            raise ValueError(msg)
        if self.kind is AlignmentEditKind.TARGET_ONLY_INSERTION and not (
            target_consumed and not source_consumed
        ):
            msg = "target-only insertion must consume only target"
            raise ValueError(msg)
        return self


class ProjectedBoundingBox(CanonicalModel):
    """Immutable finite coordinate snapshot for one projected OCR crop."""

    left: float
    top: float
    right: float
    bottom: float
    is_normalized: bool

    @model_validator(mode="after")
    def _validate_coordinates(self) -> Self:
        coordinates = (self.left, self.top, self.right, self.bottom)
        if not all(isfinite(coordinate) for coordinate in coordinates):
            msg = "projected bounding box coordinates must be finite"
            raise ValueError(msg)
        if self.left > self.right or self.top > self.bottom:
            msg = "projected bounding box coordinates must be ordered"
            raise ValueError(msg)
        if min(coordinates) < 0:
            msg = "projected pixel coordinates must be nonnegative"
            raise ValueError(msg)
        if self.is_normalized and max(coordinates) > 1:
            msg = "projected normalized coordinates must lie within [0, 1]"
            raise ValueError(msg)
        return self

    def to_ltrb(self) -> tuple[float, float, float, float]:
        """Return immutable coordinates in left-top-right-bottom order."""
        return self.left, self.top, self.right, self.bottom


def _snapshot_box(box: BoundingBox) -> ProjectedBoundingBox:
    is_normalized = box.is_normalized
    if is_normalized is None:
        msg = "projected bounding box must declare its coordinate system"
        raise ValueError(msg)
    return ProjectedBoundingBox(
        left=float(box.minX),
        top=float(box.minY),
        right=float(box.maxX),
        bottom=float(box.maxY),
        is_normalized=is_normalized,
    )


def _box_snapshots_or_none(
    value: tuple[object, ...] | list[object],
) -> tuple[ProjectedBoundingBox, ...] | None:
    snapshots: list[ProjectedBoundingBox] = []
    for item in value:
        if isinstance(item, BoundingBox):
            snapshots.append(_snapshot_box(item))
        elif isinstance(item, ProjectedBoundingBox):
            snapshots.append(item)
        else:
            return None
    return tuple(snapshots)


class ProjectedStyleSpan(CanonicalModel):
    """A style crop slice linked to one unchanged canonical source span."""

    source_span_id: str
    source_span: StyleSpan
    token_id: str
    source_range: tuple[_StrictIndex, _StrictIndex]
    crop_bbox: BoundingBox | ProjectedBoundingBox
    character_boxes: (
        list[BoundingBox | ProjectedBoundingBox]
        | tuple[BoundingBox | ProjectedBoundingBox, ...]
        | None
    ) = None

    @field_validator("crop_bbox", mode="before")
    @classmethod
    def _accept_crop_bbox_instance(cls, value: object) -> object:
        if isinstance(value, BoundingBox):
            return _snapshot_box(value)
        return value

    @field_validator("character_boxes", mode="before")
    @classmethod
    def _accept_character_box_instances(
        cls, value: tuple[object, ...] | list[object] | None
    ) -> object:
        if isinstance(value, tuple | list):
            snapshots = _box_snapshots_or_none(value)
            if snapshots is not None:
                return snapshots
        return value

    @field_validator("character_boxes", mode="after")
    @classmethod
    def _freeze_character_boxes(
        cls,
        value: (
            list[BoundingBox | ProjectedBoundingBox]
            | tuple[BoundingBox | ProjectedBoundingBox, ...]
            | None
        ),
    ) -> tuple[ProjectedBoundingBox, ...] | None:
        if value is None:
            return None
        snapshots = _box_snapshots_or_none(list(value))
        if snapshots is None:
            msg = "character_boxes must be projected bounding boxes"
            raise TypeError(msg)
        return snapshots

    @model_validator(mode="after")
    def _validate_source_range(self) -> Self:
        start, end = self.source_range
        if start >= end:
            msg = "projected style source_range must be nonempty"
            raise ValueError(msg)
        if start < self.source_span.start or end > self.source_span.end:
            msg = "projected style source_range must lie within source_span"
            raise ValueError(msg)
        if isinstance(self.crop_bbox, BoundingBox):
            msg = "crop_bbox must be an immutable projected bounding box"
            raise TypeError(msg)
        if self.character_boxes is not None and any(
            box.is_normalized != self.crop_bbox.is_normalized
            for box in self.character_boxes
        ):
            msg = "character_boxes must use the crop_bbox coordinate system"
            raise ValueError(msg)
        return self


class TokenAlignmentResult(CanonicalModel):
    """Deterministic alignment result with best and runner-up monotonic paths."""

    config: AlignmentConfig
    source_grapheme_count: _StrictIndex
    target_grapheme_count: _StrictIndex
    best_path: tuple[AlignmentEdit, ...]
    runner_up_path: tuple[AlignmentEdit, ...] | None
    best_cost: _StrictIndex
    runner_up_margin: float | None
    token_source_ranges: tuple[tuple[_StrictIndex, _StrictIndex] | None, ...]
    dp_state_count: _StrictIndex
    accepted: bool
    source_normalization_operations: tuple[ComparisonOperation, ...]
    target_normalization_operations: tuple[ComparisonOperation, ...]
    runner_up_target_normalization_operations: (
        tuple[ComparisonOperation, ...] | None
    ) = None

    @field_validator("runner_up_margin")
    @classmethod
    def _validate_margin(cls, value: float | None) -> float | None:
        if value is not None and (value < 0 or not isfinite(value)):
            msg = "runner_up_margin must be finite and nonnegative when present"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_acceptance(self) -> Self:
        expected = (
            self.runner_up_margin is None
            or self.runner_up_margin >= self.config.low_margin_threshold
        )
        if self.accepted is not expected:
            msg = "accepted must match the configured runner-up margin threshold"
            raise ValueError(msg)
        self._validate_path_ranges(self.best_path, path_name="best_path")
        if self.runner_up_path is not None:
            self._validate_path_ranges(self.runner_up_path, path_name="runner_up_path")
        elif self.runner_up_target_normalization_operations is not None:
            msg = "runner_up target normalization operations require a runner-up path"
            raise ValueError(msg)
        previous_end = 0
        for source_range in self.token_source_ranges:
            if source_range is None:
                continue
            start, end = source_range
            if start >= end:
                msg = "token_source_ranges must be nonempty"
                raise ValueError(msg)
            if end > self.source_grapheme_count:
                msg = "token_source_ranges cannot exceed source_grapheme_count"
                raise ValueError(msg)
            if start < previous_end:
                msg = "token_source_ranges cannot overlap"
                raise ValueError(msg)
            previous_end = end
        return self

    def _validate_path_ranges(
        self, path: tuple[AlignmentEdit, ...], *, path_name: str
    ) -> None:
        previous_source_range: tuple[int, int] | None = None
        previous_target_range: tuple[int, int] | None = None
        for edit in path:
            _source_start, source_end = edit.source_range
            _target_start, target_end = edit.target_range
            if source_end > self.source_grapheme_count:
                msg = f"{path_name} source_range exceeds source_grapheme_count"
                raise ValueError(msg)
            if target_end > self.target_grapheme_count:
                msg = f"{path_name} target_range exceeds target_grapheme_count"
                raise ValueError(msg)
            if previous_source_range is not None:
                self._validate_range_progression(
                    previous_source_range,
                    edit.source_range,
                    coordinate_name="source_range",
                    path_name=path_name,
                )
            if previous_target_range is not None:
                self._validate_range_progression(
                    previous_target_range,
                    edit.target_range,
                    coordinate_name="target_range",
                    path_name=path_name,
                )
            previous_source_range = edit.source_range
            previous_target_range = edit.target_range

    @staticmethod
    def _validate_range_progression(
        previous: tuple[int, int],
        current: tuple[int, int],
        *,
        coordinate_name: str,
        path_name: str,
    ) -> None:
        previous_start, previous_end = previous
        current_start, current_end = current
        if current_start < previous_start or current_end < previous_end:
            msg = f"{path_name} {coordinate_name} must be non-descending"
            raise ValueError(msg)
        if current_start < previous_end and current != previous:
            msg = f"{path_name} {coordinate_name} ranges cannot partially overlap"
            raise ValueError(msg)

    def to_evidence(
        self,
        *,
        alignment_id: str,
        source_artifact_sha256: str,
        target_artifact_sha256: str,
    ) -> AlignmentEvidence:
        """Create page-record evidence with the applied margin threshold."""
        return AlignmentEvidence(
            alignment_id=alignment_id,
            method="monotonic_grapheme_dp_v1",
            source_artifact_sha256=source_artifact_sha256,
            target_artifact_sha256=target_artifact_sha256,
            source_coordinate_space=SourceCoordinateSpace.SOURCE_GRAPHEMES,
            target_coordinate_space=TargetCoordinateSpace.OCR_GRAPHEMES,
            source_range=(0, self.source_grapheme_count),
            target_range=(0, self.target_grapheme_count),
            operations=tuple(
                f"{edit.kind}:{edit.source_range[0]}:{edit.source_range[1]}:"
                f"{edit.target_range[0]}:{edit.target_range[1]}"
                for edit in self.best_path
            ),
            score=-float(self.best_cost),
            margin=self.runner_up_margin,
            low_margin_threshold=self.config.low_margin_threshold,
            alternatives=(),
            accepted=self.accepted,
            source_normalization_operations=self.source_normalization_operations,
            target_normalization_operations=self.target_normalization_operations,
            runner_up_target_normalization_operations=(
                self.runner_up_target_normalization_operations
            ),
            runner_up_operations=(
                None
                if self.runner_up_path is None
                else tuple(
                    AlignmentPathOperation(
                        kind=edit.kind.value,
                        source_range=edit.source_range,
                        target_range=edit.target_range,
                    )
                    for edit in self.runner_up_path
                )
            ),
        )


@dataclass(frozen=True)
class _Backpointer:
    cost: int
    rank: int
    origin_rank: int
    parent_index: int | None
    kind: AlignmentEditKind | None
    source_range: tuple[int, int] | None
    target_range: tuple[int, int] | None
    target_case_fold_operation: ComparisonOperation | None


@dataclass(frozen=True)
class _TargetComparison:
    graphemes: tuple[str, ...]
    case_sensitive_graphemes: tuple[str, ...]
    grapheme_map: tuple[tuple[int, ...], ...]
    canonical_grapheme_count: int
    token_ranges: tuple[tuple[int, int], ...]
    normalization_operations: tuple[ComparisonOperation, ...]
    case_fold_operations: tuple[ComparisonOperation | None, ...]


def _backpointer_sort_key(pointer: _Backpointer) -> tuple[int, int, int]:
    return pointer.cost, pointer.origin_rank, pointer.rank


def _add_candidate(
    cells: list[list[list[int]]],
    backpointers: list[_Backpointer],
    row: int,
    column: int,
    backpointer_index: int,
) -> None:
    candidate_indices = cells[row][column]
    candidate_indices.append(backpointer_index)
    candidate_indices.sort(key=lambda index: _backpointer_sort_key(backpointers[index]))
    del candidate_indices[2:]


def _reconstruct_path(
    backpointers: list[_Backpointer], terminal_index: int
) -> tuple[tuple[AlignmentEdit, ...], tuple[ComparisonOperation, ...]]:
    reconstructed: list[tuple[AlignmentEdit, ComparisonOperation | None]] = []
    current_index: int | None = terminal_index
    while current_index is not None:
        pointer = backpointers[current_index]
        if (
            pointer.kind is not None
            and pointer.source_range is not None
            and pointer.target_range is not None
        ):
            reconstructed.append(
                (
                    AlignmentEdit(
                        kind=pointer.kind,
                        source_range=pointer.source_range,
                        target_range=pointer.target_range,
                    ),
                    pointer.target_case_fold_operation,
                )
            )
        current_index = pointer.parent_index
    reconstructed.reverse()
    operations: list[ComparisonOperation] = []
    for _edit, operation in reconstructed:
        if operation is not None and operation not in operations:
            operations.append(operation)
    return (
        tuple(edit for edit, _operation in reconstructed),
        tuple(operations),
    )


def _source_range(view: ComparisonView, index: int) -> tuple[int, int]:
    mapped = view.source_grapheme_map[index]
    return min(mapped), max(mapped) + 1


def _source_boundary(view: ComparisonView, index: int) -> int:
    if index == 0:
        return 0
    return _source_range(view, index - 1)[1]


def _target_comparison(tokens: tuple[OcrTokenRef, ...]) -> _TargetComparison:
    graphemes: list[str] = []
    case_sensitive_graphemes: list[str] = []
    grapheme_map: list[tuple[int, ...]] = []
    token_ranges: list[tuple[int, int]] = []
    operations: list[ComparisonOperation] = []
    case_fold_operations: list[ComparisonOperation | None] = []
    canonical_offset = 0
    for token in tokens:
        canonical_count = len(split_graphemes(token.text))
        case_sensitive_view = build_comparison_view(token.text)
        view = build_comparison_view(token.text, casefold_all=True)
        original_text_by_grapheme = {
            index: "".join(
                grapheme
                for grapheme, mapped in zip(
                    case_sensitive_view.graphemes,
                    case_sensitive_view.source_grapheme_map,
                    strict=True,
                )
                if mapped == (index,)
            )
            for index in range(canonical_count)
        }
        comparison_offset = len(graphemes)
        graphemes.extend(view.graphemes)
        case_sensitive_graphemes.extend(
            original_text_by_grapheme[mapped[0]] for mapped in view.source_grapheme_map
        )
        offset_operations = tuple(
            operation.model_copy(
                update={
                    "input_range": (
                        operation.input_range[0] + canonical_offset,
                        operation.input_range[1] + canonical_offset,
                    ),
                    "output_range": (
                        operation.output_range[0] + comparison_offset,
                        operation.output_range[1] + comparison_offset,
                    ),
                }
            )
            for operation in view.operations
        )
        operations.extend(
            operation
            for operation in offset_operations
            if operation.kind is not ComparisonOperationKind.SMALL_CAPS_CASE_FOLDED
        )
        case_fold_operations.extend(
            next(
                (
                    operation
                    for operation in offset_operations
                    if operation.kind is ComparisonOperationKind.SMALL_CAPS_CASE_FOLDED
                    and operation.output_range[0]
                    <= comparison_index + comparison_offset
                    < operation.output_range[1]
                ),
                None,
            )
            for comparison_index in range(len(view.graphemes))
        )
        grapheme_map.extend(
            tuple(canonical_offset + index for index in mapped)
            for mapped in view.source_grapheme_map
        )
        token_ranges.append((canonical_offset, canonical_offset + canonical_count))
        canonical_offset += canonical_count
    return _TargetComparison(
        graphemes=tuple(graphemes),
        case_sensitive_graphemes=tuple(case_sensitive_graphemes),
        grapheme_map=tuple(grapheme_map),
        canonical_grapheme_count=canonical_offset,
        token_ranges=tuple(token_ranges),
        normalization_operations=tuple(operations),
        case_fold_operations=tuple(case_fold_operations),
    )


def _target_range(comparison: _TargetComparison, index: int) -> tuple[int, int]:
    mapped = comparison.grapheme_map[index]
    return min(mapped), max(mapped) + 1


def _target_boundary(comparison: _TargetComparison, index: int) -> int:
    if index == 0:
        return 0
    if index == len(comparison.graphemes):
        return comparison.canonical_grapheme_count
    return comparison.grapheme_map[index][0]


def _source_is_small_caps(view: ComparisonView, index: int) -> bool:
    source_start, source_end = _source_range(view, index)
    return any(
        small_caps_start <= source_start and source_end <= small_caps_end
        for small_caps_start, small_caps_end in view.small_caps_ranges
    )


def _target_group_end(comparison: _TargetComparison, index: int) -> int:
    target_range = _target_range(comparison, index)
    end = index + 1
    while (
        end < len(comparison.graphemes)
        and _target_range(comparison, end) == target_range
    ):
        end += 1
    return end


def _token_source_ranges(
    *,
    token_ranges: tuple[tuple[int, int], ...],
    best_path: tuple[AlignmentEdit, ...],
) -> tuple[tuple[int, int] | None, ...]:
    projected: list[tuple[int, int] | None] = []
    for target_start, target_end in token_ranges:
        source_ranges = [
            edit.source_range
            for edit in best_path
            if edit.target_range[0] < target_end
            and edit.target_range[1] > target_start
            and edit.source_range[0] < edit.source_range[1]
        ]
        if not source_ranges:
            projected.append(None)
            continue
        projected.append(
            (
                min(source_range[0] for source_range in source_ranges),
                max(source_range[1] for source_range in source_ranges),
            )
        )
    return tuple(projected)


def align_tokens(
    source_view: ComparisonView,
    tokens: tuple[OcrTokenRef, ...],
    *,
    config: AlignmentConfig | None = None,
) -> TokenAlignmentResult:
    """Align a source comparison view to OCR tokens in deterministic reading order."""
    active_config = config or AlignmentConfig()
    target_comparison = _target_comparison(tokens)
    source_count = len(source_view.graphemes)
    target_count = len(target_comparison.graphemes)
    cells: list[list[list[int]]] = [
        [[] for _ in range(target_count + 1)] for _ in range(source_count + 1)
    ]
    backpointers = [
        _Backpointer(
            cost=0,
            rank=0,
            origin_rank=0,
            parent_index=None,
            kind=None,
            source_range=None,
            target_range=None,
            target_case_fold_operation=None,
        )
    ]
    next_rank = 1
    cells[0][0].append(0)

    def add_transition(
        *,
        row: int,
        column: int,
        parent_index: int,
        cost: int,
        kind: AlignmentEditKind,
        source_range: tuple[int, int],
        target_range: tuple[int, int],
        target_case_fold_operation: ComparisonOperation | None = None,
    ) -> None:
        nonlocal next_rank
        backpointers.append(
            _Backpointer(
                cost=cost,
                rank=next_rank,
                origin_rank=(
                    next_rank
                    if backpointers[parent_index].parent_index is None
                    else backpointers[parent_index].origin_rank
                ),
                parent_index=parent_index,
                kind=kind,
                source_range=source_range,
                target_range=target_range,
                target_case_fold_operation=target_case_fold_operation,
            )
        )
        _add_candidate(cells, backpointers, row, column, len(backpointers) - 1)
        next_rank += 1

    for source_index in range(source_count + 1):
        for target_index in range(target_count + 1):
            for parent_index in tuple(cells[source_index][target_index]):
                parent = backpointers[parent_index]
                if source_index < source_count and target_index < target_count:
                    source_range = _source_range(source_view, source_index)
                    target_range = _target_range(target_comparison, target_index)
                    source_is_small_caps = _source_is_small_caps(
                        source_view, source_index
                    )
                    equal = source_view.graphemes[source_index] == (
                        target_comparison.graphemes[target_index]
                        if source_is_small_caps
                        else target_comparison.case_sensitive_graphemes[target_index]
                    )
                    target_step = (
                        target_index + 1
                        if source_is_small_caps
                        else _target_group_end(target_comparison, target_index)
                    )
                    add_transition(
                        row=source_index + 1,
                        column=target_step,
                        parent_index=parent_index,
                        cost=parent.cost + (0 if equal else 1),
                        kind=(
                            AlignmentEditKind.MATCH
                            if equal
                            else AlignmentEditKind.SUBSTITUTION
                        ),
                        source_range=source_range,
                        target_range=target_range,
                        target_case_fold_operation=(
                            target_comparison.case_fold_operations[target_index]
                            if source_is_small_caps
                            else None
                        ),
                    )
                if source_index < source_count:
                    target_boundary = _target_boundary(target_comparison, target_index)
                    add_transition(
                        row=source_index + 1,
                        column=target_index,
                        parent_index=parent_index,
                        cost=parent.cost + 1,
                        kind=AlignmentEditKind.SOURCE_ONLY_DELETION,
                        source_range=_source_range(source_view, source_index),
                        target_range=(target_boundary, target_boundary),
                    )
                if target_index < target_count:
                    source_boundary = _source_boundary(source_view, source_index)
                    add_transition(
                        row=source_index,
                        column=target_index + 1,
                        parent_index=parent_index,
                        cost=parent.cost + 1,
                        kind=AlignmentEditKind.TARGET_ONLY_INSERTION,
                        source_range=(source_boundary, source_boundary),
                        target_range=_target_range(target_comparison, target_index),
                    )

    complete = cells[source_count][target_count]
    if not complete:
        msg = "alignment could not produce a monotonic path"
        raise RuntimeError(msg)
    best_index = complete[0]
    runner_up_index = complete[1] if len(complete) > 1 else None
    best = backpointers[best_index]
    runner_up = None if runner_up_index is None else backpointers[runner_up_index]
    best_path, best_target_case_fold_operations = _reconstruct_path(
        backpointers, best_index
    )
    runner_up_path, runner_up_target_case_fold_operations = (
        (None, None)
        if runner_up_index is None
        else _reconstruct_path(backpointers, runner_up_index)
    )
    margin = None if runner_up is None else float(runner_up.cost - best.cost)
    token_source_ranges = _token_source_ranges(
        token_ranges=target_comparison.token_ranges, best_path=best_path
    )
    return TokenAlignmentResult(
        config=active_config,
        source_grapheme_count=len(split_graphemes(source_view.source_text)),
        target_grapheme_count=target_comparison.canonical_grapheme_count,
        best_path=best_path,
        runner_up_path=runner_up_path,
        best_cost=best.cost,
        runner_up_margin=margin,
        token_source_ranges=token_source_ranges,
        dp_state_count=len(backpointers),
        accepted=margin is None or margin >= active_config.low_margin_threshold,
        source_normalization_operations=source_view.operations,
        target_normalization_operations=(
            *target_comparison.normalization_operations,
            *best_target_case_fold_operations,
        ),
        runner_up_target_normalization_operations=(
            runner_up_target_case_fold_operations
        ),
    )


def project_token_ranges(
    tokens: tuple[OcrTokenRef, ...],
    result: TokenAlignmentResult,
    *,
    alignment_id: str,
) -> tuple[OcrTokenRef, ...]:
    """Bind source-backed OCR tokens, omitting target-only insertions."""
    if not result.accepted:
        msg = "cannot project token ranges from an unaccepted alignment"
        raise ValueError(msg)
    if len(tokens) != len(result.token_source_ranges):
        msg = "token count must match the alignment token projection count"
        raise ValueError(msg)
    projected: list[OcrTokenRef] = []
    for token, source_range in zip(tokens, result.token_source_ranges, strict=True):
        if source_range is None:
            continue
        projected.append(
            token.model_copy(
                update={
                    "grapheme_start": source_range[0],
                    "grapheme_end": source_range[1],
                    "alignment_id": alignment_id,
                }
            )
        )
    return tuple(projected)


def project_style_span(
    source_span: StyleSpan,
    *,
    source_span_id: str,
    tokens: tuple[OcrTokenRef, ...],
) -> tuple[ProjectedStyleSpan, ...]:
    """Split one canonical style span at OCR word boxes without mutating it."""
    projections: list[ProjectedStyleSpan] = []
    for token in tokens:
        start = max(source_span.start, token.grapheme_start)
        end = min(source_span.end, token.grapheme_end)
        if start >= end:
            continue
        projections.append(
            ProjectedStyleSpan(
                source_span_id=source_span_id,
                source_span=source_span,
                token_id=token.token_id,
                source_range=(start, end),
                crop_bbox=token.bbox,
            )
        )
    return tuple(projections)
