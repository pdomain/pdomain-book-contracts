"""Anchor-conditioned bounded PGDP document matching."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated

from pydantic import Field, model_validator

from pdomain_book_contracts.matching.engine import match_documents
from pdomain_book_contracts.matching.models import (
    MatchAlternative,
    MatchDocument,
    MatchGraph,
    MatchLine,
    MatchOperation,
    MatchOperationKind,
    MatchPage,
    MatchPolicy,
    MatchQuarantineReason,
    MatchRelation,
    MatchRelationKind,
    MatchToken,
)
from pdomain_book_contracts.typography.normalization import build_comparison_view
from pdomain_book_contracts.typography.spans import CanonicalModel, split_graphemes

if TYPE_CHECKING:
    from pdomain_book_contracts.matching.pgdp_continuations import PgdpContinuation


_Index = Annotated[int, Field(strict=True, ge=0)]
_ANCHOR_TOKEN_COUNT = 3


class PgdpBoundedStrategy(StrEnum):
    """The safe partitioning route selected for one match."""

    WHOLE_DOCUMENT = "whole_document"
    UNIQUE_EXACT_ANCHORS = "unique_exact_anchors"
    CONTINUATION_ABSTENTION = "continuation_abstention"


class PgdpAlignmentWindow(CanonicalModel):
    """One actual local graph with ranges in the original token orders."""

    source_token_range: tuple[_Index, _Index]
    target_token_range: tuple[_Index, _Index]
    graph: MatchGraph
    is_anchor: bool

    @model_validator(mode="after")
    def _validate_ranges(self) -> PgdpAlignmentWindow:
        source_start, source_end = self.source_token_range
        target_start, target_end = self.target_token_range
        if source_start > source_end or target_start > target_end:
            msg = "alignment window token ranges must be ordered"
            raise ValueError(msg)
        if source_start == source_end and target_start == target_end:
            msg = "alignment window must contain source or target tokens"
            raise ValueError(msg)
        return self


class PgdpBoundedMatch(CanonicalModel):
    """One assembled graph plus its honest local matching evidence."""

    graph: MatchGraph
    windows: tuple[PgdpAlignmentWindow, ...]
    strategy: PgdpBoundedStrategy
    elapsed_seconds: Annotated[float, Field(ge=0.0)]
    total_state_count: _Index
    total_transition_count: _Index
    total_grapheme_state_count: _Index
    total_grapheme_work_count: _Index


@dataclass(frozen=True)
class _Anchor:
    source_range: tuple[int, int]
    target_range: tuple[int, int]


@dataclass
class _Usage:
    state_count: int = 0
    transition_count: int = 0
    grapheme_state_count: int = 0
    grapheme_work_count: int = 0


def match_pgdp_documents_bounded(
    *,
    source: MatchDocument,
    target: MatchDocument,
    policy: MatchPolicy,
    continuations: tuple[PgdpContinuation, ...] = (),
) -> PgdpBoundedMatch:
    """Bound real PGDP pages with exact anchors and core residual matching."""
    started = time.monotonic()
    if continuations:
        window = _core_window(
            source,
            target,
            source_range=(0, len(_ordered_tokens(source))),
            target_range=(0, len(_ordered_tokens(target))),
            policy=policy,
            continuations=continuations,
        )
        return _singleton_result(
            window=window,
            strategy=PgdpBoundedStrategy.CONTINUATION_ABSTENTION,
            elapsed_seconds=time.monotonic() - started,
        )

    source_tokens = _ordered_tokens(source)
    target_tokens = _ordered_tokens(target)
    anchors = _unique_exact_anchors(source_tokens, target_tokens)
    if not anchors:
        window = _core_window(
            source,
            target,
            source_range=(0, len(source_tokens)),
            target_range=(0, len(target_tokens)),
            policy=policy,
            continuations=(),
        )
        return _singleton_result(
            window=window,
            strategy=PgdpBoundedStrategy.WHOLE_DOCUMENT,
            elapsed_seconds=time.monotonic() - started,
        )

    anchor_usage = _anchor_usage(source_tokens, anchors)
    if not _fits_policy(anchor_usage, policy):
        window = _core_window(
            source,
            target,
            source_range=(0, len(source_tokens)),
            target_range=(0, len(target_tokens)),
            policy=policy,
            continuations=(),
        )
        return _singleton_result(
            window=window,
            strategy=PgdpBoundedStrategy.WHOLE_DOCUMENT,
            elapsed_seconds=time.monotonic() - started,
        )
    windows, usage = _anchored_windows(
        source=source,
        target=target,
        anchors=anchors,
        policy=policy,
        anchor_usage=anchor_usage,
    )
    return _result_from_windows(
        source=source,
        target=target,
        policy=policy,
        windows=windows,
        strategy=PgdpBoundedStrategy.UNIQUE_EXACT_ANCHORS,
        usage=usage,
        elapsed_seconds=time.monotonic() - started,
    )


def _ordered_tokens(document: MatchDocument) -> tuple[MatchToken, ...]:
    return tuple(
        token for page in document.pages for line in page.lines for token in line.tokens
    )


def _unique_exact_anchors(
    source: tuple[MatchToken, ...], target: tuple[MatchToken, ...]
) -> tuple[_Anchor, ...]:
    source_positions = _sequence_positions(source)
    target_positions = _sequence_positions(target)
    candidates = tuple(
        _Anchor(
            source_range=(source_index, source_index + _ANCHOR_TOKEN_COUNT),
            target_range=(target_index, target_index + _ANCHOR_TOKEN_COUNT),
        )
        for sequence, source_indices in source_positions.items()
        if len(source_indices) == 1
        for target_indices in (target_positions.get(sequence, ()),)
        if len(target_indices) == 1
        for source_index in source_indices
        for target_index in target_indices
    )
    selected: list[_Anchor] = []
    for candidate in sorted(candidates, key=lambda anchor: anchor.source_range):
        if selected and (
            candidate.source_range[0] < selected[-1].source_range[1]
            or candidate.target_range[0] < selected[-1].target_range[1]
        ):
            continue
        selected.append(candidate)
    return tuple(selected)


def _sequence_positions(
    tokens: tuple[MatchToken, ...],
) -> dict[tuple[str, ...], tuple[int, ...]]:
    positions: dict[tuple[str, ...], list[int]] = {}
    for index in range(len(tokens) - _ANCHOR_TOKEN_COUNT + 1):
        sequence = tuple(
            token.text for token in tokens[index : index + _ANCHOR_TOKEN_COUNT]
        )
        positions.setdefault(sequence, []).append(index)
    return {sequence: tuple(indices) for sequence, indices in positions.items()}


def _anchored_windows(
    *,
    source: MatchDocument,
    target: MatchDocument,
    anchors: tuple[_Anchor, ...],
    policy: MatchPolicy,
    anchor_usage: _Usage,
) -> tuple[tuple[PgdpAlignmentWindow, ...], _Usage]:
    source_tokens = _ordered_tokens(source)
    target_tokens = _ordered_tokens(target)
    windows: list[PgdpAlignmentWindow] = []
    source_cursor = 0
    target_cursor = 0
    usage = anchor_usage
    for anchor in anchors:
        if (source_cursor, target_cursor) != (
            anchor.source_range[0],
            anchor.target_range[0],
        ):
            residual = _core_or_exhausted_window(
                source,
                target,
                source_range=(source_cursor, anchor.source_range[0]),
                target_range=(target_cursor, anchor.target_range[0]),
                policy=policy,
                usage=usage,
            )
            windows.append(residual)
            _add_usage(usage, _window_usage(residual))
        anchor_window = _exact_anchor_window(
            source,
            target,
            source_range=anchor.source_range,
            target_range=anchor.target_range,
            policy=policy,
        )
        windows.append(anchor_window)
        source_cursor = anchor.source_range[1]
        target_cursor = anchor.target_range[1]
    if source_cursor != len(source_tokens) or target_cursor != len(target_tokens):
        residual = _core_or_exhausted_window(
            source,
            target,
            source_range=(source_cursor, len(source_tokens)),
            target_range=(target_cursor, len(target_tokens)),
            policy=policy,
            usage=usage,
        )
        windows.append(residual)
        _add_usage(usage, _window_usage(residual))
    return tuple(windows), usage


def _remaining_policy(policy: MatchPolicy, usage: _Usage) -> MatchPolicy | None:
    remaining_state_count = policy.max_state_count - usage.state_count
    remaining_transition_count = policy.max_transition_count - usage.transition_count
    remaining_grapheme_work_count = (
        policy.max_grapheme_work_count - usage.grapheme_work_count
    )
    if (
        remaining_state_count <= 0
        or remaining_transition_count <= 0
        or remaining_grapheme_work_count <= 0
    ):
        return None
    return policy.model_copy(
        update={
            "max_state_count": remaining_state_count,
            "max_transition_count": remaining_transition_count,
            "max_grapheme_work_count": remaining_grapheme_work_count,
        }
    )


def _core_or_exhausted_window(
    source: MatchDocument,
    target: MatchDocument,
    *,
    source_range: tuple[int, int],
    target_range: tuple[int, int],
    policy: MatchPolicy,
    usage: _Usage,
) -> PgdpAlignmentWindow:
    remaining = _remaining_policy(policy, usage)
    if remaining is None:
        return _unsearched_exhausted_window(
            source,
            target,
            source_range=source_range,
            target_range=target_range,
            policy=policy,
            reasons=_spent_budget_reasons(policy, usage),
        )
    return _core_window(
        source,
        target,
        source_range=source_range,
        target_range=target_range,
        policy=remaining,
        continuations=(),
    )


def _core_window(
    source: MatchDocument,
    target: MatchDocument,
    *,
    source_range: tuple[int, int],
    target_range: tuple[int, int],
    policy: MatchPolicy,
    continuations: tuple[PgdpContinuation, ...],
) -> PgdpAlignmentWindow:
    graph = match_documents(
        _window_document(source, source_range),
        _window_document(target, target_range),
        policy=policy,
        pgdp_continuations=continuations,
    )
    return PgdpAlignmentWindow(
        source_token_range=source_range,
        target_token_range=target_range,
        graph=graph,
        is_anchor=False,
    )


def _unsearched_exhausted_window(
    source: MatchDocument,
    target: MatchDocument,
    *,
    source_range: tuple[int, int],
    target_range: tuple[int, int],
    policy: MatchPolicy,
    reasons: tuple[MatchQuarantineReason, ...],
) -> PgdpAlignmentWindow:
    source_window = _window_document(source, source_range)
    target_window = _window_document(target, target_range)
    source_tokens = _ordered_tokens(source_window)
    target_tokens = _ordered_tokens(target_window)
    relations = tuple(_source_only_relation(token) for token in source_tokens) + tuple(
        _target_only_relation(token) for token in target_tokens
    )
    total_cost = (
        sum(len(split_graphemes(token.text)) for token in source_tokens)
        * policy.source_only_cost
        + sum(len(split_graphemes(token.text)) for token in target_tokens)
        * policy.target_only_cost
    )
    graph = MatchGraph(
        source_document=source_window,
        target_document=target_window,
        policy=policy,
        best_alternative=MatchAlternative(total_cost=total_cost, relations=relations),
        runner_up_alternative=None,
        runner_up_margin=None,
        accepted=False,
        quarantine_reasons=reasons,
        search_evidence=None,
        warnings=("global bounded budget was spent before this window",),
    )
    return PgdpAlignmentWindow(
        source_token_range=source_range,
        target_token_range=target_range,
        graph=graph,
        is_anchor=False,
    )


def _source_only_relation(token: MatchToken) -> MatchRelation:
    grapheme_count = len(split_graphemes(token.text))
    return MatchRelation(
        kind=MatchRelationKind.SOURCE_ONLY,
        source_token_ids=(token.token_id,),
        target_token_ids=(),
        operations=(
            MatchOperation(
                kind=MatchOperationKind.SOURCE_ONLY_DELETION,
                source_grapheme_range=(0, grapheme_count),
                target_grapheme_range=(0, 0),
            ),
        ),
    )


def _target_only_relation(token: MatchToken) -> MatchRelation:
    grapheme_count = len(split_graphemes(token.text))
    return MatchRelation(
        kind=MatchRelationKind.TARGET_ONLY,
        source_token_ids=(),
        target_token_ids=(token.token_id,),
        operations=(
            MatchOperation(
                kind=MatchOperationKind.TARGET_ONLY_INSERTION,
                source_grapheme_range=(0, 0),
                target_grapheme_range=(0, grapheme_count),
            ),
        ),
    )


def _exact_anchor_window(
    source: MatchDocument,
    target: MatchDocument,
    *,
    source_range: tuple[int, int],
    target_range: tuple[int, int],
    policy: MatchPolicy,
) -> PgdpAlignmentWindow:
    source_window = _window_document(source, source_range)
    target_window = _window_document(target, target_range)
    relations = tuple(
        _exact_relation(source_token, target_token)
        for source_token, target_token in zip(
            _ordered_tokens(source_window), _ordered_tokens(target_window), strict=True
        )
    )
    graph = MatchGraph(
        source_document=source_window,
        target_document=target_window,
        policy=policy,
        best_alternative=MatchAlternative(
            total_cost=sum(
                len(split_graphemes(token.text)) * policy.exact_match_cost
                for token in _ordered_tokens(source_window)
            ),
            relations=relations,
        ),
        runner_up_alternative=None,
        runner_up_margin=None,
        accepted=True,
        quarantine_reasons=(),
        warnings=("unique raw-exact anchor; no dynamic-program search",),
    )
    return PgdpAlignmentWindow(
        source_token_range=source_range,
        target_token_range=target_range,
        graph=graph,
        is_anchor=True,
    )


def _exact_relation(source: MatchToken, target: MatchToken) -> MatchRelation:
    source_graphemes = split_graphemes(source.text)
    target_graphemes = split_graphemes(target.text)
    if source_graphemes != target_graphemes:
        msg = "exact anchor tokens must have identical graphemes"
        raise ValueError(msg)
    return MatchRelation(
        kind=MatchRelationKind.ONE_TO_ONE,
        source_token_ids=(source.token_id,),
        target_token_ids=(target.token_id,),
        operations=tuple(
            MatchOperation(
                kind=MatchOperationKind.MATCH,
                source_grapheme_range=(index, index + 1),
                target_grapheme_range=(index, index + 1),
            )
            for index in range(len(source_graphemes))
        ),
        source_comparison=build_comparison_view(source.text, casefold_all=True),
        target_comparison=build_comparison_view(target.text, casefold_all=True),
    )


def _window_document(
    document: MatchDocument, token_range: tuple[int, int]
) -> MatchDocument:
    start, end = token_range
    position = 0
    pages: list[MatchPage] = []
    for page in document.pages:
        lines: list[MatchLine] = []
        for line in page.lines:
            line_tokens: list[MatchToken] = []
            for token in line.tokens:
                if start <= position < end:
                    line_tokens.append(token)
                position += 1
            if line_tokens:
                lines.append(MatchLine(line_id=line.line_id, tokens=tuple(line_tokens)))
        if lines:
            pages.append(MatchPage(page_id=page.page_id, lines=tuple(lines)))
    return MatchDocument(document_id=document.document_id, pages=tuple(pages))


def _window_usage(window: PgdpAlignmentWindow) -> _Usage:
    evidence = window.graph.search_evidence
    if evidence is not None:
        return _Usage(
            state_count=evidence.state_count,
            transition_count=evidence.transition_count,
            grapheme_state_count=evidence.grapheme_state_count,
            grapheme_work_count=evidence.grapheme_work_count,
        )
    if not window.is_anchor:
        return _Usage()
    token_count = sum(
        len(split_graphemes(token.text))
        for token in _ordered_tokens(window.graph.source_document)
    )
    return _Usage(
        transition_count=token_count,
        grapheme_state_count=max(
            (
                len(split_graphemes(token.text)) + 1
                for token in _ordered_tokens(window.graph.source_document)
            ),
            default=0,
        ),
        grapheme_work_count=token_count,
    )


def _anchor_usage(
    source_tokens: tuple[MatchToken, ...], anchors: tuple[_Anchor, ...]
) -> _Usage:
    anchor_tokens = tuple(
        token
        for anchor in anchors
        for token in source_tokens[anchor.source_range[0] : anchor.source_range[1]]
    )
    grapheme_counts = tuple(len(split_graphemes(token.text)) for token in anchor_tokens)
    return _Usage(
        transition_count=sum(grapheme_counts),
        grapheme_state_count=max(
            (grapheme_count + 1 for grapheme_count in grapheme_counts), default=0
        ),
        grapheme_work_count=sum(grapheme_counts),
    )


def _fits_policy(usage: _Usage, policy: MatchPolicy) -> bool:
    return (
        usage.transition_count < policy.max_transition_count
        and usage.grapheme_work_count < policy.max_grapheme_work_count
        and usage.grapheme_state_count <= policy.max_grapheme_state_count
    )


def _spent_budget_reasons(
    policy: MatchPolicy, usage: _Usage
) -> tuple[MatchQuarantineReason, ...]:
    reasons: list[MatchQuarantineReason] = []
    if usage.state_count >= policy.max_state_count:
        reasons.append(MatchQuarantineReason.STATE_LIMIT_EXHAUSTED)
    if usage.transition_count >= policy.max_transition_count:
        reasons.append(MatchQuarantineReason.TRANSITION_LIMIT_EXHAUSTED)
    if usage.grapheme_work_count >= policy.max_grapheme_work_count:
        reasons.append(MatchQuarantineReason.GRAPHEME_STATE_LIMIT_EXHAUSTED)
    if not reasons:
        reasons.append(MatchQuarantineReason.GRAPHEME_STATE_LIMIT_EXHAUSTED)
    return tuple(reasons)


def _add_usage(usage: _Usage, addition: _Usage) -> None:
    usage.state_count += addition.state_count
    usage.transition_count += addition.transition_count
    usage.grapheme_state_count = max(
        usage.grapheme_state_count, addition.grapheme_state_count
    )
    usage.grapheme_work_count += addition.grapheme_work_count


def _singleton_result(
    *,
    window: PgdpAlignmentWindow,
    strategy: PgdpBoundedStrategy,
    elapsed_seconds: float,
) -> PgdpBoundedMatch:
    usage = _window_usage(window)
    return PgdpBoundedMatch(
        graph=window.graph,
        windows=(window,),
        strategy=strategy,
        elapsed_seconds=elapsed_seconds,
        total_state_count=usage.state_count,
        total_transition_count=usage.transition_count,
        total_grapheme_state_count=usage.grapheme_state_count,
        total_grapheme_work_count=usage.grapheme_work_count,
    )


def _result_from_windows(
    *,
    source: MatchDocument,
    target: MatchDocument,
    policy: MatchPolicy,
    windows: tuple[PgdpAlignmentWindow, ...],
    strategy: PgdpBoundedStrategy,
    usage: _Usage,
    elapsed_seconds: float,
) -> PgdpBoundedMatch:
    reasons = tuple(
        dict.fromkeys(
            reason for window in windows for reason in window.graph.quarantine_reasons
        )
    )
    graph = MatchGraph(
        source_document=source,
        target_document=target,
        policy=policy,
        best_alternative=MatchAlternative(
            total_cost=sum(
                window.graph.best_alternative.total_cost for window in windows
            ),
            relations=tuple(
                relation
                for window in windows
                for relation in window.graph.best_alternative.relations
            ),
        ),
        runner_up_alternative=None,
        runner_up_margin=None,
        accepted=not reasons and all(window.graph.accepted for window in windows),
        quarantine_reasons=reasons,
        search_evidence=None,
        warnings=(
            "anchor-conditioned assembly is not an unrestricted global optimum",
            "window search evidence is retained on each alignment window",
            "no assembled runner-up alternative is claimed across windows",
        ),
    )
    return PgdpBoundedMatch(
        graph=graph,
        windows=windows,
        strategy=strategy,
        elapsed_seconds=elapsed_seconds,
        total_state_count=usage.state_count,
        total_transition_count=usage.transition_count,
        total_grapheme_state_count=usage.grapheme_state_count,
        total_grapheme_work_count=usage.grapheme_work_count,
    )
