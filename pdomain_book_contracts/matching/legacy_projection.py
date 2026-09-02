"""Opt-in compatibility projection from immutable match graphs to OCR pages.

The matcher itself never receives mutable OCR objects. This module is the
sole compatibility boundary that may write legacy ground-truth fields or
collapse adjacent physical words to preserve older caller behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, TypedDict

from pdomain_book_contracts.matching.match_type import MatchType
from pdomain_book_contracts.matching.models import (
    MatchDocument,
    MatchGraph,
    MatchLine,
    MatchPage,
    MatchRelation,
    MatchToken,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from pdomain_book_contracts.typography.annotations import TypographyAnnotations


class _MatchableWord(Protocol):
    """Structural surface this module needs from a mutable OCR word.

    ``pdomain_book_tools.ocr.word.Word`` satisfies this structurally — the
    contracts package never imports it, so the one-way dependency direction
    holds even in this module, the sole compatibility boundary that touches
    mutable OCR objects at all. Only ``is None`` is ever checked on
    ``review`` and ``glyph_annotations``, so those two stay ``object | None``
    rather than importing the book-tools types that would make the check
    precise; ``typography_annotations`` gets the real
    ``pdomain_book_contracts.typography.annotations.TypographyAnnotations``
    type because that class now lives in this package.
    """

    text: str
    ground_truth_text: str
    ground_truth_match_keys: dict[str, object]
    review: object | None
    typography_annotations: TypographyAnnotations | None
    glyph_annotations: object | None

    def merge(self, word_to_merge: _MatchableWord) -> None: ...


class _MatchableLine(Protocol):
    """Structural surface this module needs from a mutable OCR line.

    A "line" here is a words-only ``pdomain_book_tools.ocr.block.Block``.
    """

    words: Sequence[_MatchableWord]
    base_ground_truth_text: str | None
    review: object | None

    def remove_item(self, item: _MatchableWord) -> None: ...


class _MatchablePage(Protocol):
    """Structural surface this module needs from a mutable OCR page."""

    page_index: int
    lines: Sequence[_MatchableLine]
    review: object | None


class LegacyDocumentSide(StrEnum):
    """The match-graph side represented by a mutable legacy page."""

    SOURCE = "source"
    TARGET = "target"


class LegacyProjectionMutation(StrEnum):
    """The physical page change made while projecting one graph relation."""

    NONE = "none"
    COMBINED_PAGE_FRAGMENTS = "combined_page_fragments"
    MANUAL_SPLIT_PRESERVED = "manual_split_preserved"
    PROTECTED_WORD_STATE_PRESERVED = "protected_word_state_preserved"
    CROSS_LINE_FRAGMENTS_PRESERVED = "cross_line_fragments_preserved"
    CONTAINER_REVIEW_PRESERVED = "container_review_preserved"


class LegacyMatchEvidence(TypedDict):
    """Typed keys stored in a word's ``ground_truth_match_keys`` by this adapter."""

    match_type: str
    match_score: int
    match_graph_id: str
    match_relation_id: str
    match_side: str
    match_source_token_ids: tuple[str, ...]
    match_target_token_ids: tuple[str, ...]
    match_projection_mutation: str


@dataclass(frozen=True)
class LegacyProjectionResult:
    """Deterministic record of accepted graph relations projected onto a page."""

    projected_relation_ids: tuple[str, ...]
    mutated_relation_ids: tuple[str, ...]
    skipped_relation_ids: tuple[str, ...]


@dataclass(frozen=True)
class _WordLocation:
    """One pre-projection physical-word location in a legacy page."""

    line_index: int
    word: _MatchableWord


def legacy_page_to_match_document(
    page: _MatchablePage, *, document_id: str
) -> MatchDocument:
    """Snapshot one legacy page as a source-neutral immutable match document.

    Token identities encode the page index and physical line/word positions.
    Call this before projection and use the returned document as the matching
    input. The adapter validates that same snapshot before it mutates a page.
    """
    page_id = f"{document_id}:page:{page.page_index}"
    lines = tuple(
        MatchLine(
            line_id=f"{page_id}:line:{line_index}",
            tokens=tuple(
                MatchToken(
                    token_id=f"{page_id}:line:{line_index}:word:{word_index}",
                    text=word.text,
                )
                for word_index, word in enumerate(line.words)
            ),
        )
        for line_index, line in enumerate(page.lines)
    )
    return MatchDocument(
        document_id=document_id,
        pages=(MatchPage(page_id=page_id, lines=lines),),
    )


def project_match_graph_onto_page(
    page: _MatchablePage,
    graph: MatchGraph,
    *,
    document_id: str,
    page_side: LegacyDocumentSide = LegacyDocumentSide.TARGET,
) -> LegacyProjectionResult:
    """Write accepted graph suggestions onto a legacy page, only on request.

    A one-to-one relation writes ground-truth text in place. When one logical
    token maps to adjacent physical words on one unreviewed page line, this
    compatibility adapter merges those page words deterministically. The
    evidence retains every pre-mutation token ID. Manual splits, protected
    word state, and cross-line fragments remain physical and receive typed
    skipped evidence. This function never writes review metadata or typography
    annotations.
    """
    if not graph.accepted:
        msg = "cannot project a quarantined match graph"
        raise ValueError(msg)
    page_document = legacy_page_to_match_document(page, document_id=document_id)
    graph_document = _graph_document(graph, page_side=page_side)
    if page_document != graph_document:
        msg = "legacy page does not match the graph's pre-projection document"
        raise ValueError(msg)

    locations = _word_locations(page, document_id=document_id)
    counterpart_tokens = _counterpart_tokens(graph, page_side=page_side)
    page_relation_ids = _page_relation_token_ids(graph, page_side=page_side)
    projected: list[str] = []
    mutated: list[str] = []
    skipped: list[str] = []

    for relation in graph.best_alternative.relations:
        relation_id = relation.relation_id
        if relation_id is None:
            msg = "validated graph relations require an ID"
            raise ValueError(msg)
        page_token_ids = page_relation_ids(relation)
        other_tokens = counterpart_tokens(relation)
        if not page_token_ids or not other_tokens:
            continue
        relation_locations = tuple(locations[token_id] for token_id in page_token_ids)
        other_text = "".join(token.text for token in other_tokens)
        if len(relation_locations) == 1:
            _apply_in_place(
                relation_locations[0].word,
                graph=graph,
                relation=relation,
                page_side=page_side,
                ground_truth_text=other_text,
                mutation=LegacyProjectionMutation.NONE,
            )
            projected.append(relation_id)
            continue
        if _has_manual_split(relation_locations):
            _record_skipped_relation(
                relation_locations,
                graph=graph,
                relation=relation,
                page_side=page_side,
                mutation=LegacyProjectionMutation.MANUAL_SPLIT_PRESERVED,
            )
            skipped.append(relation_id)
            continue
        if _has_protected_word_state(relation_locations):
            _record_skipped_relation(
                relation_locations,
                graph=graph,
                relation=relation,
                page_side=page_side,
                mutation=LegacyProjectionMutation.PROTECTED_WORD_STATE_PRESERVED,
            )
            skipped.append(relation_id)
            continue
        if _has_container_review(page, relation_locations):
            _record_skipped_relation(
                relation_locations,
                graph=graph,
                relation=relation,
                page_side=page_side,
                mutation=LegacyProjectionMutation.CONTAINER_REVIEW_PRESERVED,
            )
            skipped.append(relation_id)
            continue
        line = _contiguous_line(page, relation_locations)
        if line is None:
            _record_skipped_relation(
                relation_locations,
                graph=graph,
                relation=relation,
                page_side=page_side,
                mutation=LegacyProjectionMutation.CROSS_LINE_FRAGMENTS_PRESERVED,
            )
            skipped.append(relation_id)
            continue
        merged_word = _combine_page_words(line, relation_locations)
        _apply_in_place(
            merged_word,
            graph=graph,
            relation=relation,
            page_side=page_side,
            ground_truth_text=other_text,
            mutation=LegacyProjectionMutation.COMBINED_PAGE_FRAGMENTS,
        )
        projected.append(relation_id)
        mutated.append(relation_id)

    for line in page.lines:
        line.base_ground_truth_text = " ".join(
            word.ground_truth_text for word in line.words
        )
    return LegacyProjectionResult(
        projected_relation_ids=tuple(projected),
        mutated_relation_ids=tuple(mutated),
        skipped_relation_ids=tuple(skipped),
    )


def _graph_document(
    graph: MatchGraph, *, page_side: LegacyDocumentSide
) -> MatchDocument:
    """Return the immutable document represented by the mutable page."""
    if page_side is LegacyDocumentSide.SOURCE:
        return graph.source_document
    return graph.target_document


def _word_locations(
    page: _MatchablePage, *, document_id: str
) -> dict[str, _WordLocation]:
    """Return the exact pre-projection physical page locations by token ID."""
    page_id = f"{document_id}:page:{page.page_index}"
    return {
        f"{page_id}:line:{line_index}:word:{word_index}": _WordLocation(
            line_index=line_index,
            word=word,
        )
        for line_index, line in enumerate(page.lines)
        for word_index, word in enumerate(line.words)
    }


def _page_relation_token_ids(
    graph: MatchGraph,
    *,
    page_side: LegacyDocumentSide,
) -> Callable[[MatchRelation], tuple[str, ...]]:
    """Return the relation token accessor for the selected mutable-page side."""
    del graph
    if page_side is LegacyDocumentSide.SOURCE:
        return lambda relation: relation.source_token_ids
    return lambda relation: relation.target_token_ids


def _counterpart_tokens(
    graph: MatchGraph,
    *,
    page_side: LegacyDocumentSide,
) -> Callable[[MatchRelation], tuple[MatchToken, ...]]:
    """Return the immutable counterpart-token resolver for one page side."""
    source_tokens = _tokens_by_id(graph.source_document)
    target_tokens = _tokens_by_id(graph.target_document)
    if page_side is LegacyDocumentSide.SOURCE:
        return lambda relation: tuple(
            target_tokens[token_id] for token_id in relation.target_token_ids
        )
    return lambda relation: tuple(
        source_tokens[token_id] for token_id in relation.source_token_ids
    )


def _tokens_by_id(document: MatchDocument) -> dict[str, MatchToken]:
    """Index immutable document tokens by their validated stable IDs."""
    return {
        token.token_id: token
        for page in document.pages
        for line in page.lines
        for token in line.tokens
    }


def _has_manual_split(locations: tuple[_WordLocation, ...]) -> bool:
    """Return whether a caller has explicitly protected one physical word."""
    return any(
        bool(location.word.ground_truth_match_keys.get("split"))
        for location in locations
    )


def _has_protected_word_state(locations: tuple[_WordLocation, ...]) -> bool:
    """Return whether a topology merge would discard protected word state."""
    return any(
        location.word.review is not None
        or location.word.typography_annotations is not None
        or location.word.glyph_annotations is not None
        for location in locations
    )


def _has_container_review(
    page: _MatchablePage,
    locations: tuple[_WordLocation, ...],
) -> bool:
    """Return whether page or involved-line review protects physical topology."""
    return page.review is not None or any(
        page.lines[location.line_index].review is not None for location in locations
    )


def _contiguous_line(
    page: _MatchablePage,
    locations: tuple[_WordLocation, ...],
) -> _MatchableLine | None:
    """Return the shared line when locations are contiguous in page order."""
    line_indexes = {location.line_index for location in locations}
    if len(line_indexes) != 1:
        return None
    line = page.lines[locations[0].line_index]
    word_indexes = tuple(
        _current_word_index(line, location.word) for location in locations
    )
    if any(word_index is None for word_index in word_indexes):
        return None
    current_indexes = tuple(
        word_index for word_index in word_indexes if word_index is not None
    )
    expected_indexes = tuple(
        range(current_indexes[0], current_indexes[0] + len(current_indexes))
    )
    if current_indexes != expected_indexes:
        return None
    return line


def _current_word_index(line: _MatchableLine, word: _MatchableWord) -> int | None:
    """Return a word's current index by identity after earlier page mutation."""
    for index, candidate in enumerate(line.words):
        if candidate is word:
            return index
    return None


def _combine_page_words(
    line: _MatchableLine, locations: tuple[_WordLocation, ...]
) -> _MatchableWord:
    """Merge one contiguous physical page-word run into its first word."""
    words = tuple(location.word for location in locations)
    anchor = words[0]
    for word in words[1:]:
        anchor.merge(word)
        line.remove_item(word)
    return anchor


def _apply_in_place(
    word: _MatchableWord,
    *,
    graph: MatchGraph,
    relation: MatchRelation,
    page_side: LegacyDocumentSide,
    ground_truth_text: str,
    mutation: LegacyProjectionMutation,
) -> None:
    """Write one legacy suggestion and its typed graph provenance onto a word."""
    word.ground_truth_text = ground_truth_text
    _write_evidence(
        word,
        graph=graph,
        relation=relation,
        page_side=page_side,
        mutation=mutation,
        ground_truth_text=ground_truth_text,
    )


def _record_skipped_relation(
    locations: tuple[_WordLocation, ...],
    *,
    graph: MatchGraph,
    relation: MatchRelation,
    page_side: LegacyDocumentSide,
    mutation: LegacyProjectionMutation,
) -> None:
    """Write non-destructive provenance for a relation retained in the graph."""
    for location in locations:
        _write_evidence(
            location.word,
            graph=graph,
            relation=relation,
            page_side=page_side,
            mutation=mutation,
            ground_truth_text=location.word.ground_truth_text,
        )


def _write_evidence(
    word: _MatchableWord,
    *,
    graph: MatchGraph,
    relation: MatchRelation,
    page_side: LegacyDocumentSide,
    mutation: LegacyProjectionMutation,
    ground_truth_text: str,
) -> None:
    """Write typed graph provenance without changing other word state."""
    graph_id = graph.graph_id
    relation_id = relation.relation_id
    if graph_id is None or relation_id is None:
        msg = "validated match graphs and relations require content IDs"
        raise ValueError(msg)
    evidence = LegacyMatchEvidence(
        match_type=_legacy_match_type(mutation),
        match_score=_match_score(word.text, ground_truth_text),
        match_graph_id=graph_id,
        match_relation_id=relation_id,
        match_side=page_side.value,
        match_source_token_ids=relation.source_token_ids,
        match_target_token_ids=relation.target_token_ids,
        match_projection_mutation=mutation.value,
    )
    word.ground_truth_match_keys.update(evidence)


def _match_score(page_text: str, ground_truth_text: str) -> int:
    """Return a deterministic integer score compatible with legacy evidence."""
    return round(100 * SequenceMatcher(None, page_text, ground_truth_text).ratio())


def _legacy_match_type(mutation: LegacyProjectionMutation) -> str:
    """Return the existing legacy category for one projection mutation."""
    if mutation is LegacyProjectionMutation.COMBINED_PAGE_FRAGMENTS:
        return MatchType.LINE_REPLACE_WORD_REPLACE_COMBINED.value
    return MatchType.LINE_REPLACE_WORD_REPLACE.value
