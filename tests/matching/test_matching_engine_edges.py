from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pdomain_book_contracts.matching import (
    MatchDocument,
    MatchGraph,
    MatchLine,
    MatchOperationKind,
    MatchPage,
    MatchPolicy,
    MatchQuarantineReason,
    MatchRelationKind,
    MatchToken,
    match_documents,
)
from pdomain_book_contracts.matching.pgdp_continuations import (
    PgdpContinuation,
    decode_pgdp_continuations,
)
from pdomain_book_contracts.matching.pgdp_visible import match_document_from_pgdp_text

if TYPE_CHECKING:
    from collections.abc import Sequence

_SHY = chr(0xAD)


def _doc(prefix: str, words: Sequence[str]) -> MatchDocument:
    tokens = tuple(
        MatchToken(token_id=f"{prefix}{index}", text=word)
        for index, word in enumerate(words)
    )
    if not tokens:
        return MatchDocument(document_id=prefix, pages=())
    return MatchDocument(
        document_id=prefix,
        pages=(
            MatchPage(
                page_id=f"{prefix}-page",
                lines=(MatchLine(line_id=f"{prefix}-line", tokens=tokens),),
            ),
        ),
    )


def _policy(**overrides: float) -> MatchPolicy:
    values: dict[str, float] = {
        "low_margin_threshold": 0.0,
        "max_merge_size": 3,
        "max_state_count": 10_000,
        "max_transition_count": 100_000,
    }
    return MatchPolicy.model_validate(
        {"policy_id": "engine-edges", "version": "1", **values, **overrides}
    )


def _match(
    source: Sequence[str], target: Sequence[str], **overrides: float
) -> MatchGraph:
    return match_documents(
        _doc("s", source), _doc("t", target), policy=_policy(**overrides)
    )


def test_two_empty_documents_match_with_a_single_empty_path() -> None:
    graph = _match([], [])
    assert graph.accepted
    assert graph.best_alternative.relations == ()
    assert graph.best_alternative.total_cost == 0.0
    assert graph.runner_up_alternative is None
    assert graph.runner_up_margin is None


@pytest.mark.parametrize(
    ("source", "target", "kind", "cost"),
    [
        (["abc"], [], MatchRelationKind.SOURCE_ONLY, 3.0),
        ([], ["abcd"], MatchRelationKind.TARGET_ONLY, 4.0),
    ],
)
def test_a_document_against_nothing_is_one_unambiguous_path(
    source: list[str], target: list[str], kind: MatchRelationKind, cost: float
) -> None:
    graph = _match(source, target)
    assert graph.accepted
    assert [r.kind for r in graph.best_alternative.relations] == [kind]
    assert graph.best_alternative.total_cost == cost
    assert graph.runner_up_alternative is None


def test_equal_cost_alternatives_are_quarantined_as_a_tie() -> None:
    graph = _match(["Hello", "extra", "world"], ["Hello", "world"])
    assert graph.runner_up_margin == 0.0
    assert not graph.accepted
    assert graph.quarantine_reasons == (MatchQuarantineReason.TIE,)


def test_margin_below_the_threshold_is_low_margin_but_equal_is_accepted() -> None:
    low = _match(["ab", "cd"], ["ab", "cd"], low_margin_threshold=4.5)
    assert low.runner_up_margin == 4.0
    assert low.quarantine_reasons == (MatchQuarantineReason.LOW_MARGIN,)
    exact = _match(["ab", "cd"], ["ab", "cd"], low_margin_threshold=4.0)
    assert exact.accepted
    assert exact.quarantine_reasons == ()


def test_a_tie_below_a_positive_threshold_reports_both_reasons_once() -> None:
    graph = _match(
        ["Hello", "extra", "world"], ["Hello", "world"], low_margin_threshold=1.0
    )
    assert graph.quarantine_reasons == (
        MatchQuarantineReason.TIE,
        MatchQuarantineReason.LOW_MARGIN,
    )


def test_matching_does_not_change_the_input_documents() -> None:
    source, target = _doc("s", ["Hello", "extra"]), _doc("t", ["Hello"])
    graph = match_documents(source, target, policy=_policy())
    assert graph.source_document == source
    assert graph.target_document == target


def test_total_cost_is_symmetric_when_source_and_target_swap() -> None:
    forward = _match(["colour", "grey"], ["color", "gray"])
    backward = _match(["color", "gray"], ["colour", "grey"])
    assert forward.best_alternative.total_cost == backward.best_alternative.total_cost


def test_comparison_is_case_insensitive_but_keeps_raw_operations() -> None:
    graph = _match(["Hello"], ["HELLO"])
    assert graph.best_alternative.total_cost == 0.0
    operations = graph.best_alternative.relations[0].operations
    assert [op.kind for op in operations] == [MatchOperationKind.MATCH] * 5


def test_policy_costs_price_each_kind_of_edit() -> None:
    assert (
        _match(["ab"], ["ab"], exact_match_cost=0.5).best_alternative.total_cost == 1.0
    )
    assert (
        _match(["ab"], ["ax"], substitution_cost=1.5).best_alternative.total_cost == 1.5
    )
    deletion = _match(["abc"], ["ab"], source_only_cost=0.25, substitution_cost=5.0)
    assert deletion.best_alternative.total_cost == 0.25
    insertion = _match(["ab"], ["abc"], target_only_cost=0.75, substitution_cost=5.0)
    assert insertion.best_alternative.total_cost == 0.75


def test_soft_hyphens_are_kept_as_raw_edits_that_cost_nothing() -> None:
    graph = _match(["a" + _SHY + "b"], ["ab"])
    assert graph.best_alternative.total_cost == 0.0
    operations = graph.best_alternative.relations[0].operations
    assert [
        (op.kind, op.source_grapheme_range, op.target_grapheme_range)
        for op in operations
    ] == [
        (MatchOperationKind.MATCH, (0, 1), (0, 1)),
        (MatchOperationKind.SOURCE_ONLY_DELETION, (1, 2), (1, 1)),
        (MatchOperationKind.MATCH, (2, 3), (1, 2)),
    ]


def test_soft_hyphen_in_the_target_is_an_insertion_in_raw_coordinates() -> None:
    graph = _match(["ab"], ["a" + _SHY + "b"])
    operations = graph.best_alternative.relations[0].operations
    assert [
        (op.kind, op.source_grapheme_range, op.target_grapheme_range)
        for op in operations
    ] == [
        (MatchOperationKind.MATCH, (0, 1), (0, 1)),
        (MatchOperationKind.TARGET_ONLY_INSERTION, (1, 1), (1, 2)),
        (MatchOperationKind.MATCH, (1, 2), (2, 3)),
    ]


def test_trailing_soft_hyphens_are_covered_by_raw_edits() -> None:
    source_side = _match(["ab" + _SHY], ["ab"]).best_alternative.relations[0].operations
    assert source_side[-1].kind is MatchOperationKind.SOURCE_ONLY_DELETION
    assert source_side[-1].source_grapheme_range == (2, 3)
    target_side = _match(["ab"], ["ab" + _SHY]).best_alternative.relations[0].operations
    assert target_side[-1].kind is MatchOperationKind.TARGET_ONLY_INSERTION
    assert target_side[-1].target_grapheme_range == (2, 3)


def test_transition_limit_after_a_complete_path_still_quarantines_the_graph() -> None:
    graph = _match(["a"], ["a"], max_transition_count=3)
    assert not graph.accepted
    assert MatchQuarantineReason.TRANSITION_LIMIT_EXHAUSTED in graph.quarantine_reasons
    assert [r.kind for r in graph.best_alternative.relations] == [
        MatchRelationKind.ONE_TO_ONE
    ]
    assert graph.warnings[0].startswith("bounded matcher stopped after")
    assert graph.search_evidence is not None
    assert graph.search_evidence.transition_count == 3


def test_state_limit_after_a_complete_path_still_quarantines_the_graph() -> None:
    graph = _match(["a"], ["a"], max_state_count=2)
    assert not graph.accepted
    assert MatchQuarantineReason.STATE_LIMIT_EXHAUSTED in graph.quarantine_reasons
    assert graph.best_alternative.total_cost == 0.0
    assert graph.search_evidence is not None
    assert graph.search_evidence.state_count == 2


def test_grapheme_budget_exhaustion_returns_a_review_only_fallback() -> None:
    graph = _match(["abc", "de"], ["abc", "de"], max_grapheme_state_count=1)
    assert not graph.accepted
    assert graph.quarantine_reasons == (
        MatchQuarantineReason.GRAPHEME_STATE_LIMIT_EXHAUSTED,
    )
    kinds = [r.kind for r in graph.best_alternative.relations]
    assert (
        kinds
        == [MatchRelationKind.SOURCE_ONLY] * 2 + [MatchRelationKind.TARGET_ONLY] * 2
    )
    assert graph.best_alternative.total_cost == 10.0
    assert graph.best_alternative.warnings == ("bounded search fallback",)
    assert graph.runner_up_alternative is None
    assert graph.search_evidence is not None
    assert graph.search_evidence.best_complete_path is None


def test_fallback_prices_unmatched_text_with_the_policy_gap_costs() -> None:
    graph = _match(
        ["abc"],
        ["de"],
        max_grapheme_state_count=1,
        source_only_cost=2.0,
        target_only_cost=3.0,
    )
    assert graph.best_alternative.total_cost == 3 * 2.0 + 2 * 3.0


def _pgdp(text: bytes, document_id: str, artifact: str) -> MatchDocument:
    return match_document_from_pgdp_text(
        text, document_id=document_id, page_id="081.png", artifact_id=artifact
    ).document


def _continuations() -> tuple[MatchDocument, tuple[PgdpContinuation, ...]]:
    f2 = _pgdp(b"foo*bar", "f2", "F2")
    p3 = _pgdp(b"foo*bar", "p3", "P3")
    return f2, decode_pgdp_continuations(f2, p3).continuations


def test_resolved_continuation_removes_the_marker_from_matching_cost() -> None:
    f2, continuations = _continuations()
    target = _pgdp(b"foobar", "t", "T")
    without = match_documents(f2, target, policy=_policy())
    assert without.best_alternative.total_cost == 1.0
    f2_edge = continuations[0]
    assert f2_edge.round_evidence[0].round.value == "f2"
    graph = match_documents(f2, target, policy=_policy(), pgdp_continuations=(f2_edge,))
    assert graph.accepted
    assert graph.best_alternative.total_cost == 0.0
    assert graph.source_document.pages[0].lines[0].tokens[0].text == "foobar"
    references = graph.best_alternative.relations[0].continuation_references
    assert [r.continuation_id for r in references] == [f2_edge.continuation_id]
    assert references[0].left_fragment_text == "foo"
    assert references[0].right_fragment_text == "bar"
    assert references[0].decision == "preserve_punctuation"
    assert len(references[0].evidence_sha256) == 64


def test_continuation_for_other_documents_is_quarantined_not_ignored() -> None:
    f2, continuations = _continuations()
    graph = match_documents(
        _pgdp(b"zzz", "o", "O"),
        _pgdp(b"foobar", "t", "T"),
        policy=_policy(),
        pgdp_continuations=continuations[:1],
    )
    assert not graph.accepted
    assert graph.quarantine_reasons == (
        MatchQuarantineReason.INCOMPATIBLE_CONTINUATION,
    )
    assert f2.token_ids().isdisjoint(graph.source_document.token_ids())


def test_duplicate_continuations_are_reported_and_quarantined() -> None:
    f2, continuations = _continuations()
    edge = continuations[0]
    graph = match_documents(
        f2,
        _pgdp(b"foobar", "t", "T"),
        policy=_policy(),
        pgdp_continuations=(edge, edge),
    )
    assert not graph.accepted
    assert MatchQuarantineReason.INCOMPATIBLE_CONTINUATION in graph.quarantine_reasons
    assert f"duplicate PGDP continuation {edge.continuation_id}" in graph.warnings


def test_ambiguous_hyphen_continuation_is_unresolved_and_quarantined() -> None:
    f2 = _pgdp(b"foo-*\nbar", "f2", "F2")
    p3 = _pgdp(b"foo-*\nbar", "p3", "P3")
    edges = decode_pgdp_continuations(f2, p3).continuations
    assert edges[0].decision.value == "ambiguous"
    graph = match_documents(
        f2,
        _pgdp(b"foo-bar", "t", "T"),
        policy=_policy(),
        pgdp_continuations=edges[:1],
    )
    assert not graph.accepted
    assert MatchQuarantineReason.UNRESOLVED_CONTINUATION in graph.quarantine_reasons
    assert f"unresolved PGDP continuation {edges[0].continuation_id}" in graph.warnings


def test_continuation_that_cannot_build_its_surface_is_quarantined_with_the_error() -> (
    None
):
    f2, continuations = _continuations()
    original = f2.pages[0].lines[0].tokens[0]
    changed = MatchDocument(
        document_id="f2",
        pages=(
            MatchPage(
                page_id=f2.pages[0].page_id,
                lines=(
                    MatchLine(
                        line_id=f2.pages[0].lines[0].line_id,
                        tokens=(
                            MatchToken(
                                token_id=original.token_id,
                                text="fxo*bar",
                                artifact_ranges=original.artifact_ranges,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    graph = match_documents(
        changed,
        _pgdp(b"foobar", "t", "T"),
        policy=_policy(),
        pgdp_continuations=continuations[:1],
    )
    assert not graph.accepted
    assert MatchQuarantineReason.INCOMPATIBLE_CONTINUATION in graph.quarantine_reasons
    assert any(
        warning.startswith("could not build PGDP matching surface")
        and "fragment does not match" in warning
        for warning in graph.warnings
    )


@pytest.mark.parametrize(
    ("source", "target"), [("\u00df", "ss"), ("ss", "\u00df"), ("\ufb01", "fi")]
)
def test_letters_that_casefold_to_several_graphemes_match_as_one_raw_edit(
    source: str, target: str
) -> None:
    graph = _match([source], [target])
    assert graph.best_alternative.total_cost == 0.0
    operations = graph.best_alternative.relations[0].operations
    assert len(operations) == 1
    assert operations[0].kind is MatchOperationKind.MATCH
    assert operations[0].source_grapheme_range == (0, len(source))
    assert operations[0].target_grapheme_range == (0, len(target))


def test_a_partly_different_expansion_is_one_raw_substitution() -> None:
    graph = _match(["\u00df"], ["sx"])
    assert graph.best_alternative.total_cost == 1.0
    operations = graph.best_alternative.relations[0].operations
    assert [
        (op.kind, op.source_grapheme_range, op.target_grapheme_range)
        for op in operations
    ] == [(MatchOperationKind.SUBSTITUTION, (0, 1), (0, 2))]
