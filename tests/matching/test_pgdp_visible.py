from __future__ import annotations

from pdomain_book_contracts.matching.pgdp_visible import (
    PgdpOcrWord,
    PgdpSourceWord,
    match_document_from_ocr_words,
    match_document_from_pgdp_text,
    match_document_from_pgdp_tokens,
)
from pdomain_book_contracts.sources.pgdp.f2.tokens import read_f2_json, tokenize_f2


def test_visible_adapter_uses_raw_json_bytes_and_stored_word_ids() -> None:
    raw = b'{"page":"<i>caf\\u00e9</i> next"}'
    parsed = read_f2_json(raw).pages[0].parsed
    first_slices = tuple(s for g in parsed.graphemes[:4] for s in g.source_slices)
    result = match_document_from_pgdp_tokens(
        parsed,
        document_id="f2",
        page_id="page",
        artifact_id="rounds/F2.json",
        source_words=(
            PgdpSourceWord(
                word_id="persisted-old-id", text="caf\u00e9", source_slices=first_slices
            ),
        ),
    )
    assert result.visible_text == "caf\u00e9 next"
    assert result.token_lookup[0].source_word_ids == ("persisted-old-id",)
    token = result.document.pages[0].lines[0].tokens[0]
    assert token.text == "caf\u00e9"
    assert (
        raw[token.artifact_ranges[-1].byte_start : token.artifact_ranges[-1].byte_end]
        == b"\\u00e9"
    )
    assert result.token_lookup[0].visible_grapheme_range == (0, 4)


def test_p3_formatter_notes_are_not_words() -> None:
    result = match_document_from_pgdp_text(
        b"11[** ,]717 and 25,[** ,]860",
        document_id="p3",
        page_id="15.png",
        artifact_id="P3",
    )
    assert result.visible_text == "11717 and 25,860"
    assert [t.text for line in result.document.pages[0].lines for t in line.tokens] == [
        "11717",
        "and",
        "25,860",
    ]


def test_split_clusters_and_discontiguous_source_word_slices() -> None:
    parsed = tokenize_f2("a<i>\u0301</i>b".encode())
    result = match_document_from_pgdp_tokens(
        parsed, document_id="f2", page_id="p", artifact_id="f2"
    )
    assert result.token_lookup[0].visible_grapheme_range == (0, 2)
    assert {
        r.grapheme_start
        for r in result.document.pages[0].lines[0].tokens[0].artifact_ranges
    } == {0, 1}


def test_ocr_adapter_keeps_ids_boxes_order_and_line_groups() -> None:
    first_id, second_id = "ocr-a", "ocr-b"
    words = (
        PgdpOcrWord(token_id=first_id, text="11", line_id="line-1", box=(1, 2, 3, 4)),
        PgdpOcrWord(token_id=second_id, text="717", line_id="line-1", box=(5, 2, 9, 4)),
    )
    result = match_document_from_ocr_words(words, document_id="ocr", page_id="scan")
    assert result.document.token_ids() == frozenset({"ocr-a", "ocr-b"})
    assert result.ocr_words == words
    assert [t.text for t in result.document.pages[0].lines[0].tokens] == ["11", "717"]
    assert all(not t.artifact_ranges for t in result.document.pages[0].lines[0].tokens)


def test_source_identity_lookup_does_not_rederive_id_from_corrected_word_text() -> None:
    parsed = tokenize_f2(b"<i>new</i> word")
    old_word = PgdpSourceWord(
        word_id="persisted-before-correction",
        text="old",
        source_slices=tuple(s for g in parsed.graphemes[:3] for s in g.source_slices),
    )
    result = match_document_from_pgdp_tokens(
        parsed,
        document_id="f2",
        page_id="p",
        artifact_id="f2",
        source_words=(old_word,),
    )
    assert result.token_lookup[0].source_word_ids == (old_word.word_id,)
    assert result.document.pages[0].lines[0].tokens[0].text == "new"


def test_visible_document_wire_rejects_unknown_lookup_token() -> None:
    import pytest

    from pdomain_book_contracts.matching.pgdp_visible import PgdpVisibleDocument

    result = match_document_from_pgdp_text(
        b"word", document_id="f2", page_id="p", artifact_id="f2"
    )
    wire = result.model_dump(mode="json")
    wire["token_lookup"] = [{"token_id": "unknown", "visible_grapheme_range": [0, 4]}]
    with pytest.raises(ValueError, match="lookup"):
        PgdpVisibleDocument.model_validate(wire)
