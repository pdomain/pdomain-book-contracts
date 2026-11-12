from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from pdomain_book_contracts.matching import (
    MatchDocument,
    MatchLine,
    MatchPage,
    MatchPolicy,
    MatchQuarantineReason,
    MatchRelationKind,
    MatchToken,
)
from pdomain_book_contracts.matching.pgdp_bounded import (
    PgdpAlignmentWindow,
    PgdpBoundedMatch,
    PgdpBoundedStrategy,
    match_pgdp_documents_bounded,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

_ANCHOR_A = ("alpha", "bravo", "charlie")
_ANCHOR_B = ("delta", "echo", "foxtrot")


def _document(prefix: str, pages: Sequence[Sequence[Sequence[str]]]) -> MatchDocument:
    counter = 0
    built_pages: list[MatchPage] = []
    for page_index, lines in enumerate(pages):
        built_lines: list[MatchLine] = []
        for line_index, words in enumerate(lines):
            tokens: list[MatchToken] = []
            for word in words:
                tokens.append(MatchToken(token_id=f"{prefix}{counter}", text=word))
                counter += 1
            built_lines.append(
                MatchLine(
                    line_id=f"{prefix}-p{page_index}-l{line_index}",
                    tokens=tuple(tokens),
                )
            )
        built_pages.append(
            MatchPage(page_id=f"{prefix}-p{page_index}", lines=tuple(built_lines))
        )
    return MatchDocument(document_id=prefix, pages=tuple(built_pages))


def _flat(prefix: str, words: Sequence[str]) -> MatchDocument:
    return _document(prefix, [[words]])


def _policy(
    *,
    max_state_count: int = 10_000,
    max_transition_count: int = 100_000,
    max_grapheme_state_count: int = 100_000,
    max_grapheme_work_count: int = 1_000_000,
) -> MatchPolicy:
    return MatchPolicy(
        policy_id="bounded-edges",
        version="1",
        low_margin_threshold=0.0,
        max_merge_size=2,
        max_state_count=max_state_count,
        max_transition_count=max_transition_count,
        max_grapheme_state_count=max_grapheme_state_count,
        max_grapheme_work_count=max_grapheme_work_count,
    )


def _two_gap_documents() -> tuple[MatchDocument, MatchDocument]:
    source = _flat("s", (*_ANCHOR_A, "x", *_ANCHOR_B, "y"))
    target = _flat("t", (*_ANCHOR_A, "z", *_ANCHOR_B, "w"))
    return source, target


def _match(
    source: MatchDocument, target: MatchDocument, policy: MatchPolicy
) -> PgdpBoundedMatch:
    return match_pgdp_documents_bounded(source=source, target=target, policy=policy)


def test_anchors_split_the_documents_into_anchor_and_residual_windows() -> None:
    source, target = _two_gap_documents()
    result = _match(source, target, _policy())
    assert result.strategy is PgdpBoundedStrategy.UNIQUE_EXACT_ANCHORS
    assert [w.is_anchor for w in result.windows] == [True, False, True, False]
    assert [w.source_token_range for w in result.windows] == [
        (0, 3),
        (3, 4),
        (4, 7),
        (7, 8),
    ]
    assert [w.target_token_range for w in result.windows] == [
        (0, 3),
        (3, 4),
        (4, 7),
        (7, 8),
    ]
    assert result.graph.source_document == source
    assert result.graph.target_document == target
    assert result.total_state_count == sum(
        w.graph.search_evidence.state_count
        for w in result.windows
        if w.graph.search_evidence is not None
    )


def test_assembled_relations_follow_window_order_and_cover_both_documents() -> None:
    source, target = _two_gap_documents()
    result = _match(source, target, _policy())
    relations = result.graph.best_alternative.relations
    assert [t for r in relations for t in r.source_token_ids] == sorted(
        source.token_ids(), key=lambda token_id: int(token_id[1:])
    )
    assert result.graph.best_alternative.total_cost == sum(
        w.graph.best_alternative.total_cost for w in result.windows
    )
    assert all(
        relation.kind is MatchRelationKind.ONE_TO_ONE
        for window in result.windows
        if window.is_anchor
        for relation in window.graph.best_alternative.relations
    )


def test_windows_over_a_multi_page_document_keep_original_line_and_page_ids() -> None:
    source = _document("s", [[_ANCHOR_A, ("x",)], [_ANCHOR_B, ("y",)]])
    target = _document("t", [[_ANCHOR_A, ("z",)], [_ANCHOR_B, ("w",)]])
    result = _match(source, target, _policy())
    residual = result.windows[1]
    assert not residual.is_anchor
    window_pages = residual.graph.source_document.pages
    assert [p.page_id for p in window_pages] == ["s-p0"]
    assert [line.line_id for line in window_pages[0].lines] == ["s-p0-l1"]
    anchor_b = result.windows[2].graph.source_document
    assert [p.page_id for p in anchor_b.pages] == ["s-p1"]
    assert [[t.text for t in line.tokens] for line in anchor_b.pages[0].lines] == [
        list(_ANCHOR_B)
    ]
    assert result.graph.source_document == source


def test_anchor_budget_that_does_not_fit_falls_back_to_the_whole_document() -> None:
    source, target = _two_gap_documents()
    anchor_graphemes = sum(len(w) for w in (*_ANCHOR_A, *_ANCHOR_B))
    result = _match(source, target, _policy(max_transition_count=anchor_graphemes))
    assert result.strategy is PgdpBoundedStrategy.WHOLE_DOCUMENT
    assert len(result.windows) == 1
    assert not result.windows[0].is_anchor
    assert result.windows[0].source_token_range == (0, 8)


def test_a_token_longer_than_the_grapheme_state_bound_disables_anchoring() -> None:
    source, target = _two_gap_documents()
    result = _match(source, target, _policy(max_grapheme_state_count=5))
    assert result.strategy is PgdpBoundedStrategy.WHOLE_DOCUMENT
    assert not any(w.is_anchor for w in result.windows)
    assert (
        MatchQuarantineReason.GRAPHEME_STATE_LIMIT_EXHAUSTED
        in result.graph.quarantine_reasons
    )


@pytest.mark.parametrize(
    ("policy", "reason"),
    [
        (_policy(max_state_count=1), MatchQuarantineReason.STATE_LIMIT_EXHAUSTED),
        (
            _policy(max_transition_count=34),
            MatchQuarantineReason.TRANSITION_LIMIT_EXHAUSTED,
        ),
        (
            _policy(max_grapheme_work_count=34),
            MatchQuarantineReason.GRAPHEME_STATE_LIMIT_EXHAUSTED,
        ),
    ],
)
def test_a_spent_budget_leaves_later_windows_unsearched_but_still_complete(
    policy: MatchPolicy, reason: MatchQuarantineReason
) -> None:
    source, target = _two_gap_documents()
    result = _match(source, target, policy)
    last = result.windows[-1]
    assert not last.is_anchor
    assert last.source_token_range == (7, 8)
    assert last.graph.search_evidence is None
    assert not last.graph.accepted
    assert reason in last.graph.quarantine_reasons
    assert "global bounded budget was spent" in last.graph.warnings[0]
    assert [r.kind for r in last.graph.best_alternative.relations] == [
        MatchRelationKind.SOURCE_ONLY,
        MatchRelationKind.TARGET_ONLY,
    ]
    assert last.graph.best_alternative.total_cost == 2.0
    assert not result.graph.accepted
    assert reason in result.graph.quarantine_reasons
    assert result.graph.source_document == source
    assert result.graph.target_document == target


def test_unsearched_window_costs_follow_the_policy_gap_costs() -> None:
    source = _flat("s", (*_ANCHOR_A, "x", *_ANCHOR_B, "yyy"))
    target = _flat("t", (*_ANCHOR_A, "z", *_ANCHOR_B, "ww"))
    policy = MatchPolicy(
        policy_id="costs",
        version="1",
        low_margin_threshold=0.0,
        max_merge_size=2,
        max_state_count=1,
        max_transition_count=100_000,
        source_only_cost=2.0,
        target_only_cost=3.0,
    )
    last = _match(source, target, policy).windows[-1]
    assert last.graph.best_alternative.total_cost == 3 * 2.0 + 2 * 3.0


def test_unsearched_window_with_only_source_tokens_has_only_source_relations() -> None:
    source = _flat("s", (*_ANCHOR_A, "x", *_ANCHOR_B, "tail"))
    target = _flat("t", (*_ANCHOR_A, "z", *_ANCHOR_B))
    last = _match(source, target, _policy(max_state_count=1)).windows[-1]
    assert last.target_token_range == (7, 7)
    assert [r.kind for r in last.graph.best_alternative.relations] == [
        MatchRelationKind.SOURCE_ONLY
    ]
    assert last.graph.target_document.pages == ()


def test_match_result_round_trips_through_canonical_json() -> None:
    source, target = _two_gap_documents()
    result = _match(source, target, _policy(max_state_count=1))
    assert PgdpBoundedMatch.from_json_bytes(result.to_json_bytes()) == result


def test_window_rejects_reversed_or_empty_token_ranges() -> None:
    source, target = _two_gap_documents()
    graph = _match(source, target, _policy()).graph
    with pytest.raises(ValidationError, match="token ranges must be ordered"):
        PgdpAlignmentWindow(
            source_token_range=(3, 1),
            target_token_range=(0, 1),
            graph=graph,
            is_anchor=False,
        )
    with pytest.raises(ValidationError, match="token ranges must be ordered"):
        PgdpAlignmentWindow(
            source_token_range=(0, 1),
            target_token_range=(2, 1),
            graph=graph,
            is_anchor=False,
        )
    with pytest.raises(ValidationError, match="must contain source or target tokens"):
        PgdpAlignmentWindow(
            source_token_range=(2, 2),
            target_token_range=(5, 5),
            graph=graph,
            is_anchor=False,
        )
    window = PgdpAlignmentWindow(
        source_token_range=(2, 2),
        target_token_range=(5, 6),
        graph=graph,
        is_anchor=False,
    )
    assert window.target_token_range == (5, 6)


def test_overlapping_unique_anchors_keep_only_the_earliest_and_match_the_rest() -> None:
    words = ("one", "two", "three", "four")
    result = _match(_flat("s", words), _flat("t", words), _policy())
    assert [(w.source_token_range, w.is_anchor) for w in result.windows] == [
        ((0, 3), True),
        ((3, 4), False),
    ]
    assert result.graph.accepted
    assert [r.kind for r in result.graph.best_alternative.relations] == [
        MatchRelationKind.ONE_TO_ONE
    ] * 4
    assert result.graph.best_alternative.total_cost == 0.0
