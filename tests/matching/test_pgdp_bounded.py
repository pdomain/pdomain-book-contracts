from __future__ import annotations

import pytest

from pdomain_book_contracts.matching import (
    MatchDocument,
    MatchLine,
    MatchPage,
    MatchPolicy,
    MatchQuarantineReason,
    MatchRelationKind,
    MatchToken,
    match_documents,
)
from pdomain_book_contracts.matching.pgdp_bounded import (
    PgdpBoundedStrategy,
    match_pgdp_documents_bounded,
)
from pdomain_book_contracts.matching.pgdp_continuations import decode_pgdp_continuations
from pdomain_book_contracts.matching.pgdp_visible import match_document_from_pgdp_text


def _policy(
    *,
    max_state_count: int = 10_000,
    max_transition_count: int = 100_000,
    max_grapheme_work_count: int = 1_000,
) -> MatchPolicy:
    return MatchPolicy(
        policy_id="bounded-test",
        version="1",
        low_margin_threshold=0.0,
        max_merge_size=2,
        max_state_count=max_state_count,
        max_transition_count=max_transition_count,
        max_grapheme_work_count=max_grapheme_work_count,
    )


def _document(document_id: str, words: tuple[str, ...]) -> MatchDocument:
    return MatchDocument(
        document_id=document_id,
        pages=(
            MatchPage(
                page_id=f"{document_id}-page",
                lines=(
                    MatchLine(
                        line_id=f"{document_id}-line",
                        tokens=tuple(
                            MatchToken(token_id=f"{document_id}-{index}", text=word)
                            for index, word in enumerate(words)
                        ),
                    ),
                ),
            ),
        ),
    )


def test_unique_exact_anchors_avoid_large_exact_page_grapheme_exhaustion() -> None:
    words = tuple(f"token-{index:02d}" for index in range(18))
    source = _document("f2", words)
    target = _document("p3", words)
    policy = _policy(max_grapheme_work_count=1_000)

    unbounded_shape = match_documents(source, target, policy=policy)
    result = match_pgdp_documents_bounded(source=source, target=target, policy=policy)

    assert (
        MatchQuarantineReason.GRAPHEME_STATE_LIMIT_EXHAUSTED
        in unbounded_shape.quarantine_reasons
    )
    assert result.strategy is PgdpBoundedStrategy.UNIQUE_EXACT_ANCHORS
    assert result.graph.accepted
    assert result.graph.source_document == source
    assert result.graph.target_document == target
    assert all(window.is_anchor for window in result.windows)
    assert all(window.graph.accepted for window in result.windows)
    assert result.graph.search_evidence is None
    assert "anchor-conditioned" in result.graph.warnings[0]


def test_split_join_falls_back_to_the_core_matcher_without_changing_ids() -> None:
    source = _document("f2", ("11", "717"))
    target = _document("p3", ("11717",))

    result = match_pgdp_documents_bounded(
        source=source, target=target, policy=_policy(max_grapheme_work_count=10_000)
    )

    assert result.strategy is PgdpBoundedStrategy.WHOLE_DOCUMENT
    assert result.graph.accepted
    relation = result.graph.best_alternative.relations[0]
    assert relation.kind is MatchRelationKind.SOURCES_TO_ONE
    assert relation.source_token_ids == ("f2-0", "f2-1")
    assert relation.target_token_ids == ("p3-0",)
    assert result.graph.source_document.token_ids() == source.token_ids()
    assert result.graph.target_document.token_ids() == target.token_ids()


def test_repeated_text_is_never_used_as_an_anchor() -> None:
    repeated = ("same",) * 12

    result = match_pgdp_documents_bounded(
        source=_document("f2", repeated),
        target=_document("p3", repeated),
        policy=_policy(max_grapheme_work_count=100_000),
    )

    assert result.strategy is PgdpBoundedStrategy.WHOLE_DOCUMENT
    assert not any(window.is_anchor for window in result.windows)


def test_residual_exhaustion_is_explicit_and_stops_at_the_remaining_budget() -> None:
    source = _document("f2", ("one", "two", "wrong", "four", "five", "six"))
    target = _document("p3", ("one", "two", "right", "four", "five", "six"))
    policy = _policy(max_state_count=1, max_grapheme_work_count=100_000)

    result = match_pgdp_documents_bounded(source=source, target=target, policy=policy)

    assert not result.graph.accepted
    assert (
        MatchQuarantineReason.STATE_LIMIT_EXHAUSTED in result.graph.quarantine_reasons
    )
    assert any(
        MatchQuarantineReason.STATE_LIMIT_EXHAUSTED in window.graph.quarantine_reasons
        for window in result.windows
    )
    assert result.total_state_count == policy.max_state_count
    assert result.graph.source_document == source
    assert result.graph.target_document == target


@pytest.mark.parametrize(
    ("words", "expected_ranges"),
    [
        (
            ("a", "b", "c", "d", "e", "f"),
            (((0, 3), (0, 3)), ((3, 6), (3, 6))),
        ),
    ],
)
def test_anchor_windows_expose_global_token_index_ranges(
    words: tuple[str, ...],
    expected_ranges: tuple[tuple[tuple[int, int], tuple[int, int]], ...],
) -> None:
    result = match_pgdp_documents_bounded(
        source=_document("f2", words),
        target=_document("p3", words),
        policy=_policy(),
    )

    assert (
        tuple(
            (window.source_token_range, window.target_token_range)
            for window in result.windows
        )
        == expected_ranges
    )


def test_continuation_abstention_returns_the_core_surface_graph() -> None:
    source = match_document_from_pgdp_text(
        b"foo*bar", document_id="f2", page_id="081.png", artifact_id="F2"
    ).document
    target = match_document_from_pgdp_text(
        b"foo*bar", document_id="p3", page_id="081.png", artifact_id="P3"
    ).document
    continuations = decode_pgdp_continuations(source, target).continuations

    result = match_pgdp_documents_bounded(
        source=source,
        target=target,
        policy=_policy(max_grapheme_work_count=100_000),
        continuations=continuations,
    )

    assert result.strategy is PgdpBoundedStrategy.CONTINUATION_ABSTENTION
    assert result.graph == result.windows[0].graph
    assert result.graph.search_evidence is not None
