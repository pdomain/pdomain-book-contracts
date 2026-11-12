from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from pdomain_book_contracts.matching.models import (
    ArtifactRange,
    MatchDocument,
    MatchLine,
    MatchPage,
    MatchToken,
)
from pdomain_book_contracts.matching.pgdp_continuations import (
    PgdpContinuation,
    PgdpContinuationBoundary,
    PgdpContinuationDecision,
    PgdpContinuationDecode,
    PgdpContinuationQuarantineReason,
    PgdpLogicalCandidate,
    PgdpMarkerEvidence,
    PgdpPhysicalFragment,
    PgdpQuarantinedMarker,
    PgdpRound,
    PgdpRoundContinuationEvidence,
    PgdpUnmappedMarkerEvidence,
    build_pgdp_surface_document,
    decode_pgdp_continuations,
)

_ID = "tok"
_HASHES = {"f2": "11" * 32, "p3": "22" * 32}


@dataclass(frozen=True)
class _Bare:
    """A word whose graphemes have no exact artifact ranges."""

    text: str


_Word = str | _Bare
_Doc = tuple[tuple[tuple[_Word, ...], ...], ...]


def _range(round_: str, offset: int, *, width: int = 1) -> ArtifactRange:
    return ArtifactRange(
        artifact_id=f"{round_}.json",
        artifact_sha256=_HASHES[round_],
        byte_start=offset,
        byte_end=offset + 1,
        grapheme_start=offset,
        grapheme_end=offset + width,
    )


def _doc(
    round_: str,
    pages: _Doc,
    *,
    id_prefix: str | None = None,
    page_ids: tuple[str, ...] = (),
) -> MatchDocument:
    prefix = id_prefix or round_
    offset = 0
    built_pages: list[MatchPage] = []
    for page_index, lines in enumerate(pages, start=1):
        page_id = page_ids[page_index - 1] if page_ids else f"p{page_index}"
        built_lines: list[MatchLine] = []
        for line_index, words in enumerate(lines):
            tokens: list[MatchToken] = []
            for word_index, word in enumerate(words):
                text = word.text if isinstance(word, _Bare) else word
                ranges: tuple[ArtifactRange, ...] = ()
                if not isinstance(word, _Bare):
                    ranges = tuple(
                        _range(round_, offset + position)
                        for position in range(len(text))
                    )
                offset += len(text)
                tokens.append(
                    MatchToken(
                        token_id=f"{prefix}-p{page_index}-l{line_index}-w{word_index}",
                        text=text,
                        artifact_ranges=ranges,
                    )
                )
            built_lines.append(
                MatchLine(line_id=f"{page_id}-l{line_index}", tokens=tuple(tokens))
            )
        built_pages.append(MatchPage(page_id=page_id, lines=tuple(built_lines)))
    return MatchDocument(document_id=round_, pages=tuple(built_pages))


def _one_line(*words: _Word) -> _Doc:
    return ((words,),)


def _decode(pages: _Doc, *, page_ids: tuple[str, ...] = ()) -> PgdpContinuationDecode:
    return decode_pgdp_continuations(
        _doc("f2", pages, page_ids=page_ids), _doc("p3", pages, page_ids=page_ids)
    )


def _decode_f2_only(pages: _Doc) -> PgdpContinuationDecode:
    return decode_pgdp_continuations(_doc("f2", pages), _doc("p3", _one_line("x")))


def _reasons(decode: PgdpContinuationDecode) -> list[PgdpContinuationQuarantineReason]:
    return [marker.reason for marker in decode.quarantined_markers]


def _fragment(text: str, token_id: str, offset: int) -> PgdpPhysicalFragment:
    return PgdpPhysicalFragment(
        text=text,
        token_id=token_id,
        page_id="p1",
        line_id="p1-l0",
        grapheme_ranges=tuple(_range("f2", offset + i) for i in range(len(text))),
    )


def _manual_continuation(
    *,
    left: PgdpPhysicalFragment,
    right: PgdpPhysicalFragment,
    marker_offset: int,
    decision: PgdpContinuationDecision = PgdpContinuationDecision.PRESERVE_PUNCTUATION,
) -> PgdpContinuation:
    marker = PgdpMarkerEvidence(
        round=PgdpRound.F2, marker_ranges=(_range("f2", marker_offset),)
    )
    return PgdpContinuation(
        left_fragment=left,
        right_fragment=right,
        boundary=PgdpContinuationBoundary.SAME_LINE,
        marker_evidence=(marker,),
        round_evidence=(
            PgdpRoundContinuationEvidence(
                round=PgdpRound.F2,
                left_fragment=left,
                right_fragment=right,
                marker_evidence=marker,
            ),
        ),
        logical_candidates=(
            PgdpLogicalCandidate(text=left.text + right.text, decision=decision),
        ),
        decision=decision,
    )


def test_inline_marker_joins_the_two_halves_of_one_physical_token() -> None:
    decode = _decode(_one_line("foo*bar"))
    assert len(decode.continuations) == 1
    edge = decode.continuations[0]
    assert (edge.left_fragment.text, edge.right_fragment.text) == ("foo", "bar")
    assert {edge.left_fragment.token_id, edge.right_fragment.token_id} == {
        "f2-p1-l0-w0"
    }
    assert edge.boundary is PgdpContinuationBoundary.SAME_LINE
    assert edge.decision is PgdpContinuationDecision.PRESERVE_PUNCTUATION
    assert [c.text for c in edge.logical_candidates] == ["foobar"]
    assert decode.quarantined_markers == ()


def test_matching_rounds_merge_into_one_edge_with_both_rounds_of_evidence() -> None:
    edge = _decode(_one_line("foo*bar")).continuations[0]
    assert [m.round for m in edge.marker_evidence] == [PgdpRound.F2, PgdpRound.P3]
    assert [e.round for e in edge.round_evidence] == [PgdpRound.F2, PgdpRound.P3]
    assert edge.round_evidence[0].left_fragment == edge.left_fragment
    assert [edge.round_evidence[1].left_fragment.token_id] == ["p3-p1-l0-w0"]
    assert edge.marker_evidence[0].marker_count == 1
    assert edge.quarantine_reasons == ()
    assert edge.marker_evidence[0].marker_ranges[0].artifact_id == "f2.json"
    assert edge.marker_evidence[1].marker_ranges[0].artifact_id == "p3.json"


def test_marker_at_a_token_end_joins_the_next_token_on_the_same_line() -> None:
    edge = _decode(_one_line("foo*", "bar")).continuations[0]
    assert (edge.left_fragment.text, edge.right_fragment.text) == ("foo", "bar")
    assert edge.left_fragment.token_id != edge.right_fragment.token_id
    assert edge.boundary is PgdpContinuationBoundary.SAME_LINE


def test_marker_at_a_token_start_joins_the_previous_token() -> None:
    edge = _decode(_one_line("foo", "*bar")).continuations[0]
    assert (edge.left_fragment.text, edge.right_fragment.text) == ("foo", "bar")
    assert edge.boundary is PgdpContinuationBoundary.SAME_LINE
    assert edge.marker_evidence[0].marker_count == 1


def test_markers_on_both_sides_of_a_break_form_one_edge_with_two_markers() -> None:
    decode = _decode(_one_line("foo*", "*bar"))
    assert len(decode.continuations) == 1
    edge = decode.continuations[0]
    assert (edge.left_fragment.text, edge.right_fragment.text) == ("foo", "bar")
    assert edge.marker_evidence[0].marker_count == 2
    assert decode.quarantined_markers == ()


def test_marker_across_a_line_break_is_a_line_boundary() -> None:
    edge = _decode((((("foo*",), ("bar",))),)).continuations[0]
    assert edge.boundary is PgdpContinuationBoundary.LINE
    assert (edge.left_fragment.line_id, edge.right_fragment.line_id) == (
        "p1-l0",
        "p1-l1",
    )


def test_marker_across_consecutive_pages_is_a_page_boundary() -> None:
    edge = _decode((((("foo*",),)), (("bar",),))).continuations[0]
    assert edge.boundary is PgdpContinuationBoundary.PAGE
    assert (edge.left_fragment.page_id, edge.right_fragment.page_id) == ("p1", "p2")


def test_marker_across_a_blank_line_or_missing_page_is_not_adjacent() -> None:
    blank_line = _decode(((("foo*",), (), ("bar",)),))
    assert blank_line.continuations == ()
    assert (
        _reasons(blank_line)
        == [PgdpContinuationQuarantineReason.NONADJACENT_MARKERS] * 2
    )
    blank_page = _decode((((("foo*",),)), (()), (("bar",),)))
    assert blank_page.continuations == ()
    assert (
        _reasons(blank_page)
        == [PgdpContinuationQuarantineReason.NONADJACENT_MARKERS] * 2
    )


@pytest.mark.parametrize(
    ("page_ids", "boundary"),
    [
        (("page-7", "page-8"), PgdpContinuationBoundary.PAGE),
        (("page-9", "page-10"), PgdpContinuationBoundary.PAGE),
        (("page-7", "page-9"), None),
        (("page-8", "page-7"), None),
        (("front", "back"), PgdpContinuationBoundary.PAGE),
        (("front", "page-2"), PgdpContinuationBoundary.PAGE),
    ],
)
def test_page_boundary_needs_consecutive_trailing_page_numbers_when_ids_have_them(
    page_ids: tuple[str, str], boundary: PgdpContinuationBoundary | None
) -> None:
    decode = _decode((((("foo*",),)), (("bar",),)), page_ids=page_ids)
    if boundary is None:
        assert decode.continuations == ()
        assert (
            _reasons(decode)
            == [PgdpContinuationQuarantineReason.NONADJACENT_MARKERS] * 2
        )
    else:
        assert [e.boundary for e in decode.continuations] == [boundary]


def test_leading_marker_after_a_blank_line_is_not_adjacent_to_the_previous_token() -> (
    None
):
    decode = _decode(((("foo",), (), ("*bar",)),))
    assert decode.continuations == ()
    assert (
        _reasons(decode) == [PgdpContinuationQuarantineReason.NONADJACENT_MARKERS] * 2
    )


def test_leading_marker_after_an_unmapped_token_has_no_exact_left_fragment() -> None:
    decode = _decode(_one_line(_Bare("foo"), "*bar"))
    assert decode.continuations == ()
    assert _reasons(decode) == [PgdpContinuationQuarantineReason.EMPTY_FRAGMENT] * 2


def test_hyphen_before_a_marker_is_ambiguous_with_three_ordered_candidates() -> None:
    edge = _decode(_one_line("foo-*", "bar")).continuations[0]
    assert edge.decision is PgdpContinuationDecision.AMBIGUOUS
    assert [(c.text, c.decision) for c in edge.logical_candidates] == [
        ("foobar", PgdpContinuationDecision.JOIN_WITHOUT_HYPHEN),
        ("foo-bar", PgdpContinuationDecision.KEEP_HYPHEN),
        ("foo- bar", PgdpContinuationDecision.LEAVE_SEPARATE),
    ]


def test_double_hyphen_is_punctuation_not_a_word_break() -> None:
    edge = _decode(_one_line("foo--*", "bar")).continuations[0]
    assert edge.decision is PgdpContinuationDecision.PRESERVE_PUNCTUATION
    assert [c.text for c in edge.logical_candidates] == ["foo--bar"]


def test_markers_with_no_neighbour_are_quarantined_not_dropped() -> None:
    leading = _decode(_one_line("*bar", "x"))
    assert leading.continuations == ()
    assert (
        _reasons(leading)
        == [PgdpContinuationQuarantineReason.ORPHAN_LEADING_MARKER] * 2
    )
    trailing = _decode(_one_line("x", "foo*"))
    assert trailing.continuations == ()
    assert (
        _reasons(trailing)
        == [PgdpContinuationQuarantineReason.ORPHAN_TRAILING_MARKER] * 2
    )


def test_quarantined_marker_keeps_the_exact_marker_range() -> None:
    decode = _decode(_one_line("x", "foo*"))
    marker = decode.quarantined_markers[0].marker_evidence
    assert marker is not None
    assert marker.round is PgdpRound.F2
    assert marker.marker_ranges[0].grapheme_start == 4
    assert decode.quarantined_markers[0].unmapped_marker_evidence is None


def test_a_lone_marker_has_no_fragment_to_join() -> None:
    decode = _decode(_one_line("foo", "*"))
    assert decode.continuations == ()
    assert _reasons(decode) == [PgdpContinuationQuarantineReason.EMPTY_FRAGMENT] * 2


def test_a_marker_followed_by_only_a_marker_leaves_the_first_one_empty_fragment() -> (
    None
):
    decode = _decode(_one_line("foo*", "*"))
    assert decode.continuations == ()
    assert PgdpContinuationQuarantineReason.EMPTY_FRAGMENT in _reasons(decode)


def test_marker_without_exact_source_ranges_keeps_unmapped_evidence() -> None:
    decode = _decode(_one_line(_Bare("foo*bar")))
    assert decode.continuations == ()
    assert (
        _reasons(decode) == [PgdpContinuationQuarantineReason.SOURCE_RANGE_MISMATCH] * 2
    )
    unmapped = decode.quarantined_markers[0].unmapped_marker_evidence
    assert unmapped is not None
    assert unmapped.round is PgdpRound.F2
    assert [unmapped.token_id] == ["f2-p1-l0-w0"]
    assert unmapped.marker_grapheme_index == 3
    assert unmapped.token_artifact_ranges == ()
    assert decode.quarantined_markers[0].marker_evidence is None


def test_a_range_covering_two_graphemes_is_not_exact() -> None:
    token = MatchToken(
        token_id=_ID,
        text="a*",
        artifact_ranges=(_range("f2", 0, width=2), _range("f2", 2)),
    )
    document = MatchDocument(
        document_id="f2",
        pages=(
            MatchPage(page_id="p1", lines=(MatchLine(line_id="l0", tokens=(token,)),)),
        ),
    )
    decode = decode_pgdp_continuations(document, _doc("p3", _one_line("x")))
    assert _reasons(decode) == [PgdpContinuationQuarantineReason.SOURCE_RANGE_MISMATCH]


def test_an_unmapped_follower_of_a_trailing_marker_quarantines_both_markers() -> None:
    decode = _decode(_one_line("foo*", _Bare("*bar")))
    assert decode.continuations == ()
    assert PgdpContinuationQuarantineReason.SOURCE_RANGE_MISMATCH in _reasons(decode)
    assert PgdpContinuationQuarantineReason.EMPTY_FRAGMENT in _reasons(decode)


def test_a_round_seen_by_only_one_side_still_yields_an_edge() -> None:
    f2_only = _decode_f2_only(_one_line("foo*bar"))
    assert [e.round for e in f2_only.continuations[0].round_evidence] == [PgdpRound.F2]
    p3_only = decode_pgdp_continuations(
        _doc("f2", _one_line("x")), _doc("p3", _one_line("foo*bar"))
    )
    assert [e.round for e in p3_only.continuations[0].round_evidence] == [PgdpRound.P3]


def test_rounds_that_disagree_at_one_place_are_marked_as_a_round_conflict() -> None:
    decode = decode_pgdp_continuations(
        _doc("f2", _one_line("foo*bar")), _doc("p3", _one_line("fo*obar"))
    )
    assert len(decode.continuations) == 1
    edge = decode.continuations[0]
    assert edge.quarantine_reasons == (PgdpContinuationQuarantineReason.ROUND_CONFLICT,)
    assert (edge.left_fragment.text, edge.right_fragment.text) == ("foo", "bar")
    assert [e.round for e in edge.round_evidence] == [PgdpRound.F2, PgdpRound.P3]


def test_two_edges_at_one_boundary_pair_up_in_reading_order() -> None:
    decode = _decode(_one_line("a*b", "c*d"))
    assert [
        (e.left_fragment.text, e.right_fragment.text) for e in decode.continuations
    ] == [
        ("a", "b"),
        ("c", "d"),
    ]
    assert all(len(e.round_evidence) == 2 for e in decode.continuations)


def test_decoding_leaves_inputs_unchanged_and_round_trips_through_json() -> None:
    f2 = _doc("f2", _one_line("foo*", "bar", "x-*", "y"))
    p3 = _doc("p3", _one_line("foo*", "bar", "x-*", "y"))
    f2_before, p3_before = f2.to_json_bytes(), p3.to_json_bytes()
    decode = decode_pgdp_continuations(f2, p3)
    assert (f2.to_json_bytes(), p3.to_json_bytes()) == (f2_before, p3_before)
    assert len(decode.continuations) == 2
    assert PgdpContinuationDecode.from_json_bytes(decode.to_json_bytes()) == decode
    assert decode == decode_pgdp_continuations(f2, p3)


def test_surface_removes_inline_markers_and_their_ranges_only() -> None:
    pages = _one_line("foo*bar", "baz")
    document = _doc("f2", pages)
    decode = _decode(pages)
    surface = build_pgdp_surface_document(document, decode.continuations)
    tokens = surface.pages[0].lines[0].tokens
    assert [t.text for t in tokens] == ["foobar", "baz"]
    original = document.pages[0].lines[0].tokens[0]
    assert tokens[0].token_id == original.token_id
    assert tokens[0].artifact_ranges == (
        original.artifact_ranges[:3] + original.artifact_ranges[4:]
    )
    assert tokens[1] == document.pages[0].lines[0].tokens[1]
    assert surface.document_id == document.document_id


def test_surface_removes_markers_at_both_ends_of_a_break() -> None:
    pages = _one_line("foo*", "*bar")
    surface = build_pgdp_surface_document(
        _doc("p3", pages), _decode(pages).continuations
    )
    assert [t.text for t in surface.pages[0].lines[0].tokens] == ["foo", "bar"]


def test_surface_ignores_continuations_from_another_document() -> None:
    continuations = _decode(_one_line("foo*bar")).continuations
    other = _doc("f2", _one_line("plain", "words"), id_prefix="other")
    assert build_pgdp_surface_document(other, continuations) == other


def test_surface_refuses_an_ambiguous_continuation() -> None:
    pages = _one_line("foo-*", "bar")
    with pytest.raises(ValueError, match="ambiguous continuation"):
        build_pgdp_surface_document(_doc("f2", pages), _decode(pages).continuations)


def test_surface_refuses_evidence_that_only_partly_matches_the_document() -> None:
    continuations = _decode(_one_line("foo*", "bar")).continuations
    partial = _doc("f2", _one_line("foo*"))
    with pytest.raises(ValueError, match="only partially matches"):
        build_pgdp_surface_document(partial, continuations)


def test_surface_refuses_evidence_matching_two_rounds_of_one_document() -> None:
    pages = _one_line("foo*bar")
    shared_f2 = _doc("f2", pages, id_prefix="same")
    shared_p3 = _doc("p3", pages, id_prefix="same")
    continuations = decode_pgdp_continuations(shared_f2, shared_p3).continuations
    with pytest.raises(ValueError, match="matches multiple rounds"):
        build_pgdp_surface_document(shared_f2, continuations)


def test_surface_refuses_a_fragment_that_differs_from_the_document() -> None:
    continuations = _decode(_one_line("foo*bar")).continuations
    changed = _doc("f2", _one_line("fxo*bar"))
    with pytest.raises(ValueError, match="fragment does not match"):
        build_pgdp_surface_document(changed, continuations)


def test_surface_refuses_a_marker_range_that_is_not_a_star() -> None:
    continuations = _decode(_one_line("foo*bar")).continuations
    changed = _doc("f2", _one_line("foo+bar"))
    with pytest.raises(ValueError, match="marker does not match"):
        build_pgdp_surface_document(changed, continuations)


def test_surface_refuses_duplicate_marker_evidence() -> None:
    pages = _one_line("foo*bar")
    edge = _decode(pages).continuations[0]
    with pytest.raises(ValueError, match="conflicting continuation marker"):
        build_pgdp_surface_document(_doc("f2", pages), (edge, edge))


def test_surface_refuses_duplicate_source_ranges() -> None:
    shared = _range("f2", 0)
    document = MatchDocument(
        document_id="f2",
        pages=(
            MatchPage(
                page_id="p1",
                lines=(
                    MatchLine(
                        line_id="l0",
                        tokens=(
                            MatchToken(
                                token_id=_ID, text="x", artifact_ranges=(shared,)
                            ),
                            MatchToken(
                                token_id=_ID + "2", text="y", artifact_ranges=(shared,)
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match="globally unique"):
        build_pgdp_surface_document(document, ())


def test_surface_refuses_tokens_without_one_range_per_grapheme() -> None:
    document = _doc("f2", _one_line(_Bare("foo")))
    with pytest.raises(ValueError, match="one source range per grapheme"):
        build_pgdp_surface_document(document, ())


def test_surface_refuses_to_empty_a_physical_token() -> None:
    document = _doc("f2", _one_line("a", "*", "b"))
    tokens = document.pages[0].lines[0].tokens
    left = PgdpPhysicalFragment(
        text="a",
        token_id=tokens[0].token_id,
        page_id="p1",
        line_id="p1-l0",
        grapheme_ranges=tokens[0].artifact_ranges,
    )
    right = PgdpPhysicalFragment(
        text="b",
        token_id=tokens[2].token_id,
        page_id="p1",
        line_id="p1-l0",
        grapheme_ranges=tokens[2].artifact_ranges,
    )
    edge = _manual_continuation(left=left, right=right, marker_offset=1)
    with pytest.raises(ValueError, match="empty physical token"):
        build_pgdp_surface_document(document, (edge,))


def test_fragment_requires_one_single_grapheme_range_per_grapheme() -> None:
    with pytest.raises(ValidationError, match="one source range per grapheme"):
        PgdpPhysicalFragment(
            text="ab",
            token_id=_ID,
            page_id="p",
            line_id="l",
            grapheme_ranges=(_range("f2", 0),),
        )
    with pytest.raises(ValidationError, match="each cover one grapheme"):
        PgdpPhysicalFragment(
            text="a",
            token_id=_ID,
            page_id="p",
            line_id="l",
            grapheme_ranges=(_range("f2", 0, width=2),),
        )


@pytest.mark.parametrize("field", ["text", "token_id", "page_id", "line_id"])
def test_fragment_rejects_empty_text_fields(field: str) -> None:
    values = {"text": "a", "token_id": _ID, "page_id": "p", "line_id": "l"}
    values[field] = ""
    with pytest.raises(ValidationError, match="must not be empty"):
        PgdpPhysicalFragment(
            text=values["text"],
            token_id=values["token_id"],
            page_id=values["page_id"],
            line_id=values["line_id"],
            grapheme_ranges=(_range("f2", 0),) if field != "text" else (),
        )


def test_marker_evidence_needs_at_least_one_single_grapheme_marker() -> None:
    with pytest.raises(ValidationError, match="at least one marker range"):
        PgdpMarkerEvidence(round=PgdpRound.F2, marker_ranges=())
    with pytest.raises(ValidationError, match="each cover one grapheme"):
        PgdpMarkerEvidence(
            round=PgdpRound.F2, marker_ranges=(_range("f2", 0, width=2),)
        )


def test_logical_candidate_rejects_empty_text() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        PgdpLogicalCandidate(text="", decision=PgdpContinuationDecision.KEEP_HYPHEN)


def test_round_evidence_marker_round_must_match_the_declared_round() -> None:
    fragment = _fragment("a", "t", 0)
    with pytest.raises(ValidationError, match="must use the declared round"):
        PgdpRoundContinuationEvidence(
            round=PgdpRound.P3,
            left_fragment=fragment,
            right_fragment=fragment,
            marker_evidence=PgdpMarkerEvidence(
                round=PgdpRound.F2, marker_ranges=(_range("f2", 5),)
            ),
        )


def test_quarantined_marker_needs_exactly_one_evidence_form() -> None:
    marker = PgdpMarkerEvidence(round=PgdpRound.F2, marker_ranges=(_range("f2", 0),))
    unmapped = PgdpUnmappedMarkerEvidence(
        round=PgdpRound.F2,
        token_id=_ID,
        page_id="p",
        line_id="l",
        marker_grapheme_index=0,
        token_artifact_ranges=(),
    )
    reason = PgdpContinuationQuarantineReason.EMPTY_FRAGMENT
    with pytest.raises(ValidationError, match="exactly one evidence representation"):
        PgdpQuarantinedMarker(
            marker_evidence=marker, unmapped_marker_evidence=unmapped, reason=reason
        )
    with pytest.raises(ValidationError, match="exactly one evidence representation"):
        PgdpQuarantinedMarker(
            marker_evidence=None, unmapped_marker_evidence=None, reason=reason
        )


@pytest.mark.parametrize("field", ["token_id", "page_id", "line_id"])
def test_unmapped_marker_rejects_empty_identifiers(field: str) -> None:
    values = {"token_id": _ID, "page_id": "p", "line_id": "l"}
    values[field] = ""
    with pytest.raises(ValidationError, match="must not be empty"):
        PgdpUnmappedMarkerEvidence(
            round=PgdpRound.F2,
            token_id=values["token_id"],
            page_id=values["page_id"],
            line_id=values["line_id"],
            marker_grapheme_index=0,
            token_artifact_ranges=(),
        )


def test_unmapped_marker_rejects_a_negative_grapheme_index() -> None:
    with pytest.raises(ValidationError):
        PgdpUnmappedMarkerEvidence(
            round=PgdpRound.F2,
            token_id=_ID,
            page_id="p",
            line_id="l",
            marker_grapheme_index=-1,
            token_artifact_ranges=(),
        )


def _valid_edge() -> PgdpContinuation:
    return _manual_continuation(
        left=_fragment("ab", "t1", 0), right=_fragment("cd", "t2", 3), marker_offset=2
    )


def _edge_payload(edge: PgdpContinuation) -> dict[str, object]:
    return dict(edge.model_dump())


def test_continuation_identity_is_content_derived_and_tamper_evident() -> None:
    edge = _valid_edge()
    assert edge.continuation_id is not None
    assert len(edge.continuation_id) == 64
    assert edge == _valid_edge()
    other = _manual_continuation(
        left=_fragment("ab", "t1", 0), right=_fragment("ce", "t2", 3), marker_offset=2
    )
    assert other.continuation_id != edge.continuation_id
    payload = _edge_payload(edge)
    payload["continuation_id"] = "0" * 64
    with pytest.raises(ValidationError, match="does not match the canonical payload"):
        PgdpContinuation.model_validate(payload)
    payload["continuation_id"] = edge.continuation_id
    assert PgdpContinuation.model_validate(payload) == edge


def test_continuation_copy_with_new_fragment_refreshes_evidence_and_identity() -> None:
    edge = _valid_edge()
    replacement = _fragment("xy", "t3", 10)
    copied = edge.model_copy(update={"right_fragment": replacement})
    assert copied.right_fragment == replacement
    assert copied.round_evidence[0].right_fragment == replacement
    assert copied.left_fragment == edge.left_fragment
    assert copied.continuation_id != edge.continuation_id
    left_copy = edge.model_copy(update={"left_fragment": replacement})
    assert left_copy.round_evidence[0].left_fragment == replacement


def test_continuation_copy_without_fragment_changes_keeps_the_evidence() -> None:
    edge = _valid_edge()
    copied = edge.model_copy(update={"quarantine_reasons": ()})
    assert copied == edge
    assert edge.model_copy() == edge


def test_continuation_rejects_a_stale_fragment_against_its_authoritative_round() -> (
    None
):
    edge = _valid_edge()
    payload = _edge_payload(edge)
    payload["continuation_id"] = None
    payload["right_fragment"] = _fragment("xy", "t3", 10)
    with pytest.raises(ValidationError, match="authoritative fragments"):
        PgdpContinuation.model_validate(payload)


def test_continuation_requires_marker_and_round_evidence() -> None:
    payload = _edge_payload(_valid_edge())
    payload["continuation_id"] = None
    payload["marker_evidence"] = ()
    with pytest.raises(ValidationError, match="require marker evidence"):
        PgdpContinuation.model_validate(payload)
    payload = _edge_payload(_valid_edge())
    payload["continuation_id"] = None
    payload["round_evidence"] = ()
    with pytest.raises(ValidationError, match="complete per-round evidence"):
        PgdpContinuation.model_validate(payload)


def test_continuation_allows_one_record_per_round() -> None:
    edge = _valid_edge()
    payload = _edge_payload(edge)
    payload["continuation_id"] = None
    payload["marker_evidence"] = edge.marker_evidence * 2
    with pytest.raises(ValidationError, match="one marker evidence record per round"):
        PgdpContinuation.model_validate(payload)
    payload = _edge_payload(edge)
    payload["continuation_id"] = None
    payload["round_evidence"] = edge.round_evidence * 2
    with pytest.raises(ValidationError, match="one complete evidence record per round"):
        PgdpContinuation.model_validate(payload)


def test_continuation_round_orders_must_agree() -> None:
    merged = _decode(_one_line("foo*bar")).continuations[0]
    payload = _edge_payload(merged)
    payload["continuation_id"] = None
    payload["round_evidence"] = tuple(reversed(merged.round_evidence))
    with pytest.raises(ValidationError, match="order must exactly match"):
        PgdpContinuation.model_validate(payload)


def test_continuation_marker_must_equal_its_round_record_marker() -> None:
    edge = _valid_edge()
    payload = _edge_payload(edge)
    payload["continuation_id"] = None
    payload["marker_evidence"] = (
        PgdpMarkerEvidence(round=PgdpRound.F2, marker_ranges=(_range("f2", 9),)),
    )
    with pytest.raises(ValidationError, match="exactly match its same-round record"):
        PgdpContinuation.model_validate(payload)


def _candidate(text: str, decision: PgdpContinuationDecision) -> PgdpLogicalCandidate:
    return PgdpLogicalCandidate(text=text, decision=decision)


def test_continuation_logical_candidates_must_fit_the_decision() -> None:
    keep = PgdpContinuationDecision.KEEP_HYPHEN
    join = PgdpContinuationDecision.JOIN_WITHOUT_HYPHEN
    ambiguous = PgdpContinuationDecision.AMBIGUOUS
    cases: list[
        tuple[tuple[PgdpLogicalCandidate, ...], PgdpContinuationDecision, str]
    ] = [
        ((), keep, "at least one logical candidate"),
        (
            (_candidate("x", keep), _candidate("x", join)),
            ambiguous,
            "must be distinct",
        ),
        ((_candidate("x", keep),), ambiguous, "require multiple logical candidates"),
        (
            (_candidate("x", keep), _candidate("y", join)),
            keep,
            "exactly one logical candidate",
        ),
        ((_candidate("x", join),), keep, "must equal the continuation decision"),
    ]
    for candidates, decision, message in cases:
        payload = _edge_payload(_valid_edge())
        payload["continuation_id"] = None
        payload["logical_candidates"] = candidates
        payload["decision"] = decision
        with pytest.raises(ValidationError, match=message):
            PgdpContinuation.model_validate(payload)
