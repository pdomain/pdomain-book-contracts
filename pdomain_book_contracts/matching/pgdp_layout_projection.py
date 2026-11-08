"""Compose immutable PGDP F2, P3, and OCR matches."""

from __future__ import annotations

import hashlib
import json
import time
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, model_validator

from pdomain_book_contracts.layout.text_hints import LayoutTextHint
from pdomain_book_contracts.matching.models import (
    MatchDocument,
    MatchGraph,
    MatchOperationKind,
    MatchQuarantineReason,
    MatchRelation,
    MatchToken,
)
from pdomain_book_contracts.matching.pgdp_bounded import (
    PgdpAlignmentWindow,
    PgdpBoundedMatch,
    PgdpBoundedStrategy,
    match_pgdp_documents_bounded,
)
from pdomain_book_contracts.typography.spans import (
    CanonicalModel,
    StyleSpan,
    split_graphemes,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from pdomain_book_contracts.matching.models import MatchPolicy
    from pdomain_book_contracts.matching.pgdp_continuations import PgdpContinuation

_Text = Annotated[str, Field(strict=True, min_length=1)]
_Index = Annotated[int, Field(strict=True, ge=0)]
_EXHAUSTED = frozenset(
    {
        MatchQuarantineReason.STATE_LIMIT_EXHAUSTED,
        MatchQuarantineReason.TRANSITION_LIMIT_EXHAUSTED,
        MatchQuarantineReason.GRAPHEME_STATE_LIMIT_EXHAUSTED,
    }
)


class PgdpAlignmentDisposition(StrEnum):
    """The review state retained for a mapping."""

    ACCEPTED = "accepted"
    CHANGED = "changed"
    AMBIGUOUS = "ambiguous"
    UNMAPPED = "unmapped"
    EXHAUSTED = "exhausted"


class PgdpAlignmentGroup(CanonicalModel):
    """One connected component through shared P3 tokens."""

    group_id: _Text
    f2_token_ids: tuple[_Text, ...] = ()
    p3_token_ids: tuple[_Text, ...] = ()
    ocr_token_ids: tuple[_Text, ...] = ()
    f2_to_p3_relation_ids: tuple[_Text, ...] = ()
    p3_to_ocr_relation_ids: tuple[_Text, ...] = ()
    disposition: PgdpAlignmentDisposition
    warnings: tuple[str, ...] = ()


class PgdpWorkSummary(CanonicalModel):
    """Bounded work consumed by both matcher invocations."""

    f2_to_p3_state_count: _Index
    f2_to_p3_transition_count: _Index
    f2_to_p3_grapheme_work_count: _Index
    p3_to_ocr_state_count: _Index
    p3_to_ocr_transition_count: _Index
    p3_to_ocr_grapheme_work_count: _Index


class PgdpTimingSummary(CanonicalModel):
    """Monotonic elapsed seconds for matching and composition."""

    f2_to_p3_seconds: float
    p3_to_ocr_seconds: float
    composition_seconds: float


class PgdpPageAlignment(CanonicalModel):
    """Both graphs and their explicit many-to-many groups."""

    f2_to_p3: MatchGraph
    p3_to_ocr: MatchGraph
    groups: tuple[PgdpAlignmentGroup, ...]
    disposition: PgdpAlignmentDisposition
    warnings: tuple[str, ...]
    work: PgdpWorkSummary
    timing: PgdpTimingSummary
    f2_to_p3_windows: tuple[PgdpAlignmentWindow, ...] = ()
    p3_to_ocr_windows: tuple[PgdpAlignmentWindow, ...] = ()
    f2_to_p3_strategy: PgdpBoundedStrategy = PgdpBoundedStrategy.WHOLE_DOCUMENT
    p3_to_ocr_strategy: PgdpBoundedStrategy = PgdpBoundedStrategy.WHOLE_DOCUMENT


class PgdpProjectedTokenRange(CanonicalModel):
    """A local half-open grapheme range in one OCR token."""

    token_id: _Text
    grapheme_range: tuple[_Index, _Index]

    @model_validator(mode="after")
    def _valid_range(self) -> PgdpProjectedTokenRange:
        if self.grapheme_range[0] >= self.grapheme_range[1]:
            msg = "OCR grapheme range must be nonempty and ordered"
            raise ValueError(msg)
        return self


class PgdpProjectedLayoutHint(CanonicalModel):
    """A hint mapped via F2 artifact ranges instead of text searching."""

    hint: LayoutTextHint
    group_ids: tuple[_Text, ...]
    f2_token_ids: tuple[_Text, ...]
    p3_token_ids: tuple[_Text, ...]
    ocr_token_ids: tuple[_Text, ...]
    disposition: PgdpAlignmentDisposition
    warnings: tuple[str, ...] = ()


class PgdpProjectedStyleSpan(CanonicalModel):
    """A style segment whose originals match through both graphs."""

    style_span: StyleSpan
    source_grapheme_range: tuple[_Index, _Index]
    group_ids: tuple[_Text, ...]
    f2_token_ids: tuple[_Text, ...]
    p3_token_ids: tuple[_Text, ...]
    ocr_token_ids: tuple[_Text, ...]
    ocr_ranges: tuple[PgdpProjectedTokenRange, ...]
    disposition: PgdpAlignmentDisposition
    warnings: tuple[str, ...] = ()


class PgdpUnresolvedFormatting(CanonicalModel):
    """Formatting that must remain visible for review."""

    source_kind: Literal["layout_hint", "style_span"]
    source_ref: _Text
    grapheme_range: tuple[_Index, _Index] | None
    disposition: PgdpAlignmentDisposition
    warnings: tuple[str, ...]


class PgdpFormattingProjection(CanonicalModel):
    """Mapped formatting and explicit unresolved source evidence."""

    layout_hints: tuple[PgdpProjectedLayoutHint, ...]
    style_spans: tuple[PgdpProjectedStyleSpan, ...]
    unresolved: tuple[PgdpUnresolvedFormatting, ...]
    warnings: tuple[str, ...] = ()


def match_pgdp_documents(
    *,
    source: MatchDocument,
    target: MatchDocument,
    policy: MatchPolicy,
    continuations: tuple[PgdpContinuation, ...] = (),
) -> MatchGraph:
    """Match two PGDP document views through the bounded matcher."""
    return match_pgdp_documents_bounded(
        source=source,
        target=target,
        policy=policy,
        continuations=continuations,
    ).graph


def align_pgdp_page(
    *,
    f2: MatchDocument,
    p3: MatchDocument,
    ocr: MatchDocument,
    policy: MatchPolicy,
    continuations: tuple[PgdpContinuation, ...] = (),
) -> PgdpPageAlignment:
    """Match F2 to P3 and P3 to OCR before composing their groups."""
    f2_match = match_pgdp_documents_bounded(
        source=f2, target=p3, policy=policy, continuations=continuations
    )
    ocr_match = match_pgdp_documents_bounded(
        source=p3, target=ocr, policy=policy, continuations=continuations
    )
    return _compose(
        f2_to_p3=f2_match.graph,
        p3_to_ocr=ocr_match.graph,
        f2_seconds=f2_match.elapsed_seconds,
        ocr_seconds=ocr_match.elapsed_seconds,
        f2_windows=f2_match.windows,
        ocr_windows=ocr_match.windows,
        f2_strategy=f2_match.strategy,
        ocr_strategy=ocr_match.strategy,
        f2_bounded=f2_match,
        ocr_bounded=ocr_match,
    )


def compose_pgdp_alignments(
    *,
    f2_to_p3: MatchGraph,
    p3_to_ocr: MatchGraph,
    f2_to_p3_windows: tuple[PgdpAlignmentWindow, ...] = (),
    p3_to_ocr_windows: tuple[PgdpAlignmentWindow, ...] = (),
    f2_to_p3_strategy: PgdpBoundedStrategy | None = None,
    p3_to_ocr_strategy: PgdpBoundedStrategy | None = None,
) -> PgdpPageAlignment:
    """Compose graphs that retain the same complete P3 document."""
    return _compose(
        f2_to_p3=f2_to_p3,
        p3_to_ocr=p3_to_ocr,
        f2_seconds=0.0,
        ocr_seconds=0.0,
        f2_windows=f2_to_p3_windows,
        ocr_windows=p3_to_ocr_windows,
        f2_strategy=_compose_strategy(f2_to_p3_windows, f2_to_p3_strategy),
        ocr_strategy=_compose_strategy(p3_to_ocr_windows, p3_to_ocr_strategy),
        f2_bounded=None,
        ocr_bounded=None,
    )


def _compose(
    *,
    f2_to_p3: MatchGraph,
    p3_to_ocr: MatchGraph,
    f2_seconds: float,
    ocr_seconds: float,
    f2_windows: tuple[PgdpAlignmentWindow, ...],
    ocr_windows: tuple[PgdpAlignmentWindow, ...],
    f2_strategy: PgdpBoundedStrategy,
    ocr_strategy: PgdpBoundedStrategy,
    f2_bounded: PgdpBoundedMatch | None,
    ocr_bounded: PgdpBoundedMatch | None,
) -> PgdpPageAlignment:
    if f2_to_p3.target_document != p3_to_ocr.source_document:
        msg = "cannot compose alignments with different shared P3 documents"
        raise ValueError(msg)
    started = time.perf_counter()
    groups = _groups(
        f2_to_p3=f2_to_p3,
        p3_to_ocr=p3_to_ocr,
        f2_windows=f2_windows,
        ocr_windows=ocr_windows,
    )
    elapsed = time.perf_counter() - started
    return PgdpPageAlignment(
        f2_to_p3=f2_to_p3,
        p3_to_ocr=p3_to_ocr,
        groups=groups,
        disposition=_overall_disposition(groups),
        warnings=(*f2_to_p3.warnings, *p3_to_ocr.warnings),
        work=_work(
            f2_to_p3=f2_to_p3,
            p3_to_ocr=p3_to_ocr,
            f2_bounded=f2_bounded,
            ocr_bounded=ocr_bounded,
            f2_windows=f2_windows,
            ocr_windows=ocr_windows,
        ),
        timing=PgdpTimingSummary(
            f2_to_p3_seconds=f2_seconds,
            p3_to_ocr_seconds=ocr_seconds,
            composition_seconds=elapsed,
        ),
        f2_to_p3_windows=f2_windows,
        p3_to_ocr_windows=ocr_windows,
        f2_to_p3_strategy=f2_strategy,
        p3_to_ocr_strategy=ocr_strategy,
    )


def _compose_strategy(
    windows: tuple[PgdpAlignmentWindow, ...],
    supplied: PgdpBoundedStrategy | None,
) -> PgdpBoundedStrategy:
    if supplied is not None:
        return supplied
    if any(window.is_anchor for window in windows):
        return PgdpBoundedStrategy.UNIQUE_EXACT_ANCHORS
    return PgdpBoundedStrategy.WHOLE_DOCUMENT


def _groups(
    *,
    f2_to_p3: MatchGraph,
    p3_to_ocr: MatchGraph,
    f2_windows: tuple[PgdpAlignmentWindow, ...],
    ocr_windows: tuple[PgdpAlignmentWindow, ...],
) -> tuple[PgdpAlignmentGroup, ...]:
    nodes: dict[tuple[str, str], set[tuple[str, str]]] = {}
    relation_nodes: dict[tuple[str, str], MatchRelation] = {}
    for side, document in (
        ("f2", f2_to_p3.source_document),
        ("p3", f2_to_p3.target_document),
        ("ocr", p3_to_ocr.target_document),
    ):
        for token_id in _token_order(document):
            nodes[(side, token_id)] = set()
    _add_relations(
        nodes,
        relation_nodes=relation_nodes,
        graph=f2_to_p3,
        source_side="f2",
        target_side="p3",
        relation_side="f2r",
    )
    _add_relations(
        nodes,
        relation_nodes=relation_nodes,
        graph=p3_to_ocr,
        source_side="p3",
        target_side="ocr",
        relation_side="p3r",
    )
    orders = {
        "f2": _token_order(f2_to_p3.source_document),
        "p3": _token_order(f2_to_p3.target_document),
        "ocr": _token_order(p3_to_ocr.target_document),
        "f2r": tuple(_relation_id(relation) for relation in _relations(f2_to_p3)),
        "p3r": tuple(_relation_id(relation) for relation in _relations(p3_to_ocr)),
    }
    visited: set[tuple[str, str]] = set()
    groups: list[PgdpAlignmentGroup] = []
    for node in nodes:
        if node in visited:
            continue
        component = _component(node, nodes=nodes, visited=visited)
        identifiers = {
            side: tuple(
                identifier
                for identifier in orders[side]
                if (side, identifier) in component
            )
            for side in orders
        }
        if not identifiers["f2r"] and not identifiers["p3r"]:
            continue
        relations = tuple(
            relation_nodes[(side, relation_id)]
            for side in ("f2r", "p3r")
            for relation_id in identifiers[side]
        )
        disposition = _group_disposition(
            f2_to_p3=f2_to_p3,
            p3_to_ocr=p3_to_ocr,
            f2_ids=identifiers["f2"],
            p3_ids=identifiers["p3"],
            ocr_ids=identifiers["ocr"],
            f2_relation_ids=identifiers["f2r"],
            ocr_relation_ids=identifiers["p3r"],
            relations=relations,
            f2_windows=f2_windows,
            ocr_windows=ocr_windows,
        )
        groups.append(
            PgdpAlignmentGroup(
                group_id=_group_id(identifiers),
                f2_token_ids=identifiers["f2"],
                p3_token_ids=identifiers["p3"],
                ocr_token_ids=identifiers["ocr"],
                f2_to_p3_relation_ids=identifiers["f2r"],
                p3_to_ocr_relation_ids=identifiers["p3r"],
                disposition=disposition,
                warnings=_disposition_warnings(disposition),
            )
        )
    return tuple(groups)


def _add_relations(
    nodes: dict[tuple[str, str], set[tuple[str, str]]],
    *,
    relation_nodes: dict[tuple[str, str], MatchRelation],
    graph: MatchGraph,
    source_side: str,
    target_side: str,
    relation_side: str,
) -> None:
    for relation in _relations(graph):
        relation_key = (relation_side, _relation_id(relation))
        nodes[relation_key] = set()
        relation_nodes[relation_key] = relation
        for token_id in relation.source_token_ids:
            _join(nodes, relation_key, (source_side, token_id))
        for token_id in relation.target_token_ids:
            _join(nodes, relation_key, (target_side, token_id))


def _join(
    nodes: dict[tuple[str, str], set[tuple[str, str]]],
    left: tuple[str, str],
    right: tuple[str, str],
) -> None:
    nodes[left].add(right)
    nodes[right].add(left)


def _component(
    start: tuple[str, str],
    *,
    nodes: Mapping[tuple[str, str], set[tuple[str, str]]],
    visited: set[tuple[str, str]],
) -> frozenset[tuple[str, str]]:
    pending = [start]
    result: set[tuple[str, str]] = set()
    while pending:
        node = pending.pop()
        if node in visited:
            continue
        visited.add(node)
        result.add(node)
        pending.extend(nodes[node] - visited)
    return frozenset(result)


def _relations(graph: MatchGraph) -> tuple[MatchRelation, ...]:
    return graph.best_alternative.relations


def _relation_id(relation: MatchRelation) -> str:
    if relation.relation_id is None:
        msg = "match relation is missing its canonical ID"
        raise ValueError(msg)
    return relation.relation_id


def _token_order(document: MatchDocument) -> tuple[str, ...]:
    return tuple(
        token.token_id
        for page in document.pages
        for line in page.lines
        for token in line.tokens
    )


def _group_id(identifiers: Mapping[str, tuple[str, ...]]) -> str:
    payload = json.dumps(
        tuple(identifiers[side] for side in ("f2", "p3", "ocr", "f2r", "p3r")),
        separators=(",", ":"),
    ).encode()
    return f"pgdp-{hashlib.sha256(payload).hexdigest()}"


def _group_disposition(
    *,
    f2_to_p3: MatchGraph,
    p3_to_ocr: MatchGraph,
    f2_ids: tuple[str, ...],
    p3_ids: tuple[str, ...],
    ocr_ids: tuple[str, ...],
    f2_relation_ids: tuple[str, ...],
    ocr_relation_ids: tuple[str, ...],
    relations: tuple[MatchRelation, ...],
    f2_windows: tuple[PgdpAlignmentWindow, ...],
    ocr_windows: tuple[PgdpAlignmentWindow, ...],
) -> PgdpAlignmentDisposition:
    locally_supported = _locally_supported(
        relation_ids=f2_relation_ids, windows=f2_windows
    ) and _locally_supported(relation_ids=ocr_relation_ids, windows=ocr_windows)
    if (_is_exhausted(f2_to_p3) or _is_exhausted(p3_to_ocr)) and not locally_supported:
        return PgdpAlignmentDisposition.EXHAUSTED
    if (not f2_to_p3.accepted or not p3_to_ocr.accepted) and not locally_supported:
        return PgdpAlignmentDisposition.AMBIGUOUS
    if not f2_ids or not p3_ids or not ocr_ids:
        return PgdpAlignmentDisposition.UNMAPPED
    f2_graph_relation_ids = {
        _relation_id(relation) for relation in _relations(f2_to_p3)
    }
    if any(
        _relation_changed(
            relation,
            source=f2_to_p3.source_document
            if _relation_id(relation) in f2_graph_relation_ids
            else p3_to_ocr.source_document,
            target=f2_to_p3.target_document
            if _relation_id(relation) in f2_graph_relation_ids
            else p3_to_ocr.target_document,
        )
        for relation in relations
    ):
        return PgdpAlignmentDisposition.CHANGED
    return PgdpAlignmentDisposition.ACCEPTED


def _locally_supported(
    *, relation_ids: tuple[str, ...], windows: tuple[PgdpAlignmentWindow, ...]
) -> bool:
    if not windows:
        return False
    accepted_relation_ids = {
        _relation_id(relation)
        for window in windows
        if window.graph.accepted
        for relation in _relations(window.graph)
    }
    return bool(relation_ids) and set(relation_ids).issubset(accepted_relation_ids)


def _relation_changed(
    relation: MatchRelation, *, source: MatchDocument, target: MatchDocument
) -> bool:
    source_tokens = {item.token_id: item for item in _tokens(source)}
    target_tokens = {item.token_id: item for item in _tokens(target)}
    source_locations = _relation_locations(relation.source_token_ids, source_tokens)
    target_locations = _relation_locations(relation.target_token_ids, target_tokens)
    for operation in relation.operations:
        if operation.kind is not MatchOperationKind.MATCH:
            return True
        source_slice = source_locations[
            operation.source_grapheme_range[0] : operation.source_grapheme_range[1]
        ]
        target_slice = target_locations[
            operation.target_grapheme_range[0] : operation.target_grapheme_range[1]
        ]
        if len(source_slice) != len(target_slice):
            return True
        if any(
            _grapheme(left, source_tokens) != _grapheme(right, target_tokens)
            for left, right in zip(source_slice, target_slice, strict=True)
        ):
            return True
    return False


def _is_exhausted(graph: MatchGraph) -> bool:
    return bool(_EXHAUSTED.intersection(graph.quarantine_reasons))


def _disposition_warnings(
    disposition: PgdpAlignmentDisposition,
) -> tuple[str, ...]:
    if disposition is PgdpAlignmentDisposition.EXHAUSTED:
        return ("one or both bounded match searches exhausted",)
    if disposition is PgdpAlignmentDisposition.UNMAPPED:
        return ("component does not connect all F2, P3, and OCR sides",)
    if disposition is PgdpAlignmentDisposition.CHANGED:
        return ("component contains substitutions or one-sided operations",)
    return ()


def _overall_disposition(
    groups: tuple[PgdpAlignmentGroup, ...],
) -> PgdpAlignmentDisposition:
    values = {group.disposition for group in groups}
    for disposition in (
        PgdpAlignmentDisposition.EXHAUSTED,
        PgdpAlignmentDisposition.AMBIGUOUS,
        PgdpAlignmentDisposition.UNMAPPED,
        PgdpAlignmentDisposition.CHANGED,
    ):
        if disposition in values:
            return disposition
    return PgdpAlignmentDisposition.ACCEPTED


def _work(
    *,
    f2_to_p3: MatchGraph,
    p3_to_ocr: MatchGraph,
    f2_bounded: PgdpBoundedMatch | None,
    ocr_bounded: PgdpBoundedMatch | None,
    f2_windows: tuple[PgdpAlignmentWindow, ...],
    ocr_windows: tuple[PgdpAlignmentWindow, ...],
) -> PgdpWorkSummary:
    f2_state_count, f2_transition_count, f2_grapheme_work_count = _work_values(
        graph=f2_to_p3, bounded=f2_bounded, windows=f2_windows
    )
    ocr_state_count, ocr_transition_count, ocr_grapheme_work_count = _work_values(
        graph=p3_to_ocr, bounded=ocr_bounded, windows=ocr_windows
    )
    return PgdpWorkSummary(
        f2_to_p3_state_count=f2_state_count,
        f2_to_p3_transition_count=f2_transition_count,
        f2_to_p3_grapheme_work_count=f2_grapheme_work_count,
        p3_to_ocr_state_count=ocr_state_count,
        p3_to_ocr_transition_count=ocr_transition_count,
        p3_to_ocr_grapheme_work_count=ocr_grapheme_work_count,
    )


def _work_values(
    *,
    graph: MatchGraph,
    bounded: PgdpBoundedMatch | None,
    windows: tuple[PgdpAlignmentWindow, ...],
) -> tuple[int, int, int]:
    if bounded is not None:
        return (
            bounded.total_state_count,
            bounded.total_transition_count,
            bounded.total_grapheme_work_count,
        )
    if windows:
        return _window_work(windows)
    evidence = graph.search_evidence
    if evidence is None:
        return 0, 0, 0
    return evidence.state_count, evidence.transition_count, evidence.grapheme_work_count


def _window_work(windows: tuple[PgdpAlignmentWindow, ...]) -> tuple[int, int, int]:
    state_count = 0
    transition_count = 0
    grapheme_work_count = 0
    for window in windows:
        evidence = window.graph.search_evidence
        if evidence is not None:
            state_count += evidence.state_count
            transition_count += evidence.transition_count
            grapheme_work_count += evidence.grapheme_work_count
            continue
        if window.is_anchor:
            grapheme_count = sum(
                len(split_graphemes(token.text))
                for token in _tokens(window.graph.source_document)
            )
            transition_count += grapheme_count
            grapheme_work_count += grapheme_count
    return state_count, transition_count, grapheme_work_count


def project_f2_formatting(
    *,
    alignment: PgdpPageAlignment,
    hints: tuple[LayoutTextHint, ...],
    style_spans: tuple[StyleSpan, ...],
) -> PgdpFormattingProjection:
    """Project hints by ranges and styles by exact original grapheme operations."""
    groups_by_f2 = {
        token_id: group for group in alignment.groups for token_id in group.f2_token_ids
    }
    locations = _f2_locations(alignment.f2_to_p3.source_document)
    projected_hints: list[PgdpProjectedLayoutHint] = []
    unresolved: list[PgdpUnresolvedFormatting] = []
    for hint in hints:
        token_ids = (
            ()
            if hint.grapheme_range is None
            else _f2_tokens(locations, hint.grapheme_range)
        )
        groups = _groups_for_tokens(token_ids, groups_by_f2)
        disposition = _projection_disposition(groups)
        warnings = () if groups else ("hint range has no aligned F2 token",)
        projected_hints.append(
            PgdpProjectedLayoutHint(
                hint=hint,
                group_ids=tuple(group.group_id for group in groups),
                f2_token_ids=_group_tokens(groups, "f2"),
                p3_token_ids=_group_tokens(groups, "p3"),
                ocr_token_ids=_group_tokens(groups, "ocr"),
                disposition=disposition,
                warnings=warnings,
            )
        )
        if disposition is not PgdpAlignmentDisposition.ACCEPTED:
            unresolved.append(
                PgdpUnresolvedFormatting(
                    source_kind="layout_hint",
                    source_ref=hint.source_ref,
                    grapheme_range=hint.grapheme_range,
                    disposition=disposition,
                    warnings=warnings or ("layout hint is not fully accepted",),
                )
            )
    matches = _exact_composed_matches(alignment)
    projected_styles, style_unresolved = _project_styles(
        style_spans=style_spans,
        matches=matches,
        locations=locations,
        groups_by_f2=groups_by_f2,
    )
    return PgdpFormattingProjection(
        layout_hints=tuple(projected_hints),
        style_spans=projected_styles,
        unresolved=(*unresolved, *style_unresolved),
    )


def _f2_locations(document: MatchDocument) -> dict[int, tuple[str, int]]:
    locations: dict[int, tuple[str, int]] = {}
    for token in _tokens(document):
        grapheme_count = len(split_graphemes(token.text))
        global_indices = tuple(
            dict.fromkeys(
                index
                for artifact_range in token.artifact_ranges
                for index in range(
                    artifact_range.grapheme_start, artifact_range.grapheme_end
                )
            )
        )
        if grapheme_count != len(global_indices):
            continue
        for local, global_index in enumerate(global_indices):
            locations[global_index] = (token.token_id, local)
    return locations


def _tokens(document: MatchDocument) -> tuple[MatchToken, ...]:
    return tuple(
        token for page in document.pages for line in page.lines for token in line.tokens
    )


def _f2_tokens(
    locations: Mapping[int, tuple[str, int]], grapheme_range: tuple[int, int]
) -> tuple[str, ...]:
    return _unique(
        location[0]
        for index, location in locations.items()
        if grapheme_range[0] <= index < grapheme_range[1]
    )


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _groups_for_tokens(
    token_ids: tuple[str, ...], groups_by_f2: Mapping[str, PgdpAlignmentGroup]
) -> tuple[PgdpAlignmentGroup, ...]:
    return tuple(
        dict.fromkeys(
            groups_by_f2[token_id] for token_id in token_ids if token_id in groups_by_f2
        )
    )


def _group_tokens(
    groups: tuple[PgdpAlignmentGroup, ...], side: Literal["f2", "p3", "ocr"]
) -> tuple[str, ...]:
    if side == "f2":
        return _unique(token_id for group in groups for token_id in group.f2_token_ids)
    if side == "p3":
        return _unique(token_id for group in groups for token_id in group.p3_token_ids)
    return _unique(token_id for group in groups for token_id in group.ocr_token_ids)


def _projection_disposition(
    groups: tuple[PgdpAlignmentGroup, ...],
) -> PgdpAlignmentDisposition:
    return (
        PgdpAlignmentDisposition.UNMAPPED
        if not groups
        else _overall_disposition(groups)
    )


def _exact_composed_matches(
    alignment: PgdpPageAlignment,
) -> dict[tuple[str, int], tuple[str, int]]:
    f2_to_p3 = _exact_matches(alignment.f2_to_p3)
    p3_to_ocr = _exact_matches(alignment.p3_to_ocr)
    return {
        f2_location: p3_to_ocr[p3_location]
        for f2_location, p3_location in f2_to_p3.items()
        if p3_location in p3_to_ocr
    }


def _exact_matches(graph: MatchGraph) -> dict[tuple[str, int], tuple[str, int]]:
    source = {token.token_id: token for token in _tokens(graph.source_document)}
    target = {token.token_id: token for token in _tokens(graph.target_document)}
    matches: dict[tuple[str, int], tuple[str, int]] = {}
    for relation in _relations(graph):
        source_locations = _relation_locations(relation.source_token_ids, source)
        target_locations = _relation_locations(relation.target_token_ids, target)
        for operation in relation.operations:
            if operation.kind is not MatchOperationKind.MATCH:
                continue
            source_slice = source_locations[
                operation.source_grapheme_range[0] : operation.source_grapheme_range[1]
            ]
            target_slice = target_locations[
                operation.target_grapheme_range[0] : operation.target_grapheme_range[1]
            ]
            if len(source_slice) != len(target_slice):
                continue
            matches.update(
                {
                    source_location: target_location
                    for source_location, target_location in zip(
                        source_slice, target_slice, strict=True
                    )
                    if _grapheme(source_location, source)
                    == _grapheme(target_location, target)
                }
            )
    return matches


def _relation_locations(
    token_ids: tuple[str, ...], tokens: Mapping[str, MatchToken]
) -> tuple[tuple[str, int], ...]:
    return tuple(
        (token_id, index)
        for token_id in token_ids
        for index in range(len(split_graphemes(tokens[token_id].text)))
    )


def _grapheme(location: tuple[str, int], tokens: Mapping[str, MatchToken]) -> str:
    return split_graphemes(tokens[location[0]].text)[location[1]]


def _project_styles(
    *,
    style_spans: tuple[StyleSpan, ...],
    matches: Mapping[tuple[str, int], tuple[str, int]],
    locations: Mapping[int, tuple[str, int]],
    groups_by_f2: Mapping[str, PgdpAlignmentGroup],
) -> tuple[tuple[PgdpProjectedStyleSpan, ...], tuple[PgdpUnresolvedFormatting, ...]]:
    projected: list[PgdpProjectedStyleSpan] = []
    unresolved: list[PgdpUnresolvedFormatting] = []
    for style_span in style_spans:
        exact = {
            index: matches[location]
            for index, location in locations.items()
            if style_span.start <= index < style_span.end and location in matches
        }
        for source_range in _ranges(tuple(exact)):
            source_locations = tuple(locations[index] for index in range(*source_range))
            target_locations = tuple(exact[index] for index in range(*source_range))
            groups = _groups_for_tokens(
                _unique(item[0] for item in source_locations), groups_by_f2
            )
            projected.append(
                PgdpProjectedStyleSpan(
                    style_span=style_span,
                    source_grapheme_range=source_range,
                    group_ids=tuple(group.group_id for group in groups),
                    f2_token_ids=_unique(item[0] for item in source_locations),
                    p3_token_ids=_group_tokens(groups, "p3"),
                    ocr_token_ids=_unique(item[0] for item in target_locations),
                    ocr_ranges=_target_ranges(target_locations),
                    disposition=PgdpAlignmentDisposition.ACCEPTED,
                )
            )
        for source_range in _ranges(
            tuple(
                index
                for index in range(style_span.start, style_span.end)
                if index not in exact
            )
        ):
            tokens = _unique(
                locations[index][0]
                for index in range(*source_range)
                if index in locations
            )
            groups = _groups_for_tokens(tokens, groups_by_f2)
            unresolved.append(
                PgdpUnresolvedFormatting(
                    source_kind="style_span",
                    source_ref=style_span.rule_ref or "style_span",
                    grapheme_range=source_range,
                    disposition=_projection_disposition(groups),
                    warnings=("style graphemes are not exact composed matches",),
                )
            )
    return tuple(projected), tuple(unresolved)


def _ranges(indices: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    if not indices:
        return ()
    result: list[tuple[int, int]] = []
    start = indices[0]
    previous = start
    for index in indices[1:]:
        if index != previous + 1:
            result.append((start, previous + 1))
            start = index
        previous = index
    result.append((start, previous + 1))
    return tuple(result)


def _target_ranges(
    locations: tuple[tuple[str, int], ...],
) -> tuple[PgdpProjectedTokenRange, ...]:
    ranges: list[PgdpProjectedTokenRange] = []
    for token_id, index in locations:
        if (
            ranges
            and ranges[-1].token_id == token_id
            and ranges[-1].grapheme_range[1] == index
        ):
            previous = ranges.pop()
            ranges.append(
                PgdpProjectedTokenRange(
                    token_id=token_id,
                    grapheme_range=(previous.grapheme_range[0], index + 1),
                )
            )
        else:
            ranges.append(
                PgdpProjectedTokenRange(
                    token_id=token_id, grapheme_range=(index, index + 1)
                )
            )
    return tuple(ranges)


__all__ = [
    "PgdpAlignmentDisposition",
    "PgdpAlignmentGroup",
    "PgdpFormattingProjection",
    "PgdpPageAlignment",
    "PgdpProjectedLayoutHint",
    "PgdpProjectedStyleSpan",
    "PgdpProjectedTokenRange",
    "PgdpTimingSummary",
    "PgdpUnresolvedFormatting",
    "PgdpWorkSummary",
    "align_pgdp_page",
    "compose_pgdp_alignments",
    "match_pgdp_documents",
    "project_f2_formatting",
]
