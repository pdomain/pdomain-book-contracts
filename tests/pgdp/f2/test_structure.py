from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from pdomain_book_contracts.sources.pgdp.f2.parser import F2Parser
from pdomain_book_contracts.sources.pgdp.f2.structure import layout_hints_from_tokens
from pdomain_book_contracts.sources.pgdp.f2.tokens import tokenize_f2
from pdomain_book_contracts.typography.records import (
    ArtifactRef,
    ArtifactSource,
    TextIdentity,
)


def _identity(payload: bytes) -> TextIdentity:
    artifact = ArtifactRef(
        source=ArtifactSource.PGDP_F2,
        source_url=None,
        local_path="fixture/F2.json",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        sha256=hashlib.sha256(payload).hexdigest(),
        version="1",
        license_ref=None,
    )
    return TextIdentity(
        work_id="work",
        edition_id="edition",
        book_id="book",
        project_id=None,
        pg_ebook_id=None,
        se_repository=None,
        page_id="page",
        image_artifact=artifact,
        text_artifacts=(artifact,),
    )


def test_poetry_lines_keep_grapheme_range_and_indentation() -> None:
    parsed = tokenize_f2("/*  a\u0301lpha\n    beta*/".encode())

    hints = layout_hints_from_tokens(parsed, source_ref="rounds/F2.json#1")

    assert len(hints) == 1
    hint = hints[0]
    assert hint.kind == "poetry"
    assert hint.text == "  a\u0301lpha\n    beta"
    assert [line.text for line in hint.lines] == ["a\u0301lpha", "beta"]
    assert [line.indent_hint for line in hint.lines] == ["2 spaces", "4 spaces"]
    assert hint.grapheme_range == (0, 16)


def test_poetry_range_uses_global_grapheme_boundaries_across_inline_tags() -> None:
    parsed = tokenize_f2("/*a<i>\u0301</i>b*/".encode())

    hint = layout_hints_from_tokens(parsed, source_ref="rounds/F2.json#1")[0]

    assert "".join(grapheme.text for grapheme in parsed.graphemes) == "a\u0301b"
    assert hint.grapheme_range == (0, 2)


def test_marker_inside_a_grapheme_abstains_from_layout_evidence() -> None:
    parsed = tokenize_f2("a/*\u0301*/".encode())

    assert layout_hints_from_tokens(parsed, source_ref="rounds/F2.json#1") == ()


def test_display_block_is_candidate() -> None:
    parsed = tokenize_f2(b"/#display#/")

    hints = layout_hints_from_tokens(parsed, source_ref="rounds/F2.json#1")

    assert [(hint.kind, hint.text) for hint in hints] == [("blockquote", "display")]


def test_nested_table_keeps_only_outer_candidate_and_cell_text() -> None:
    parsed = tokenize_f2(
        b'<table class="outer"><tr class="row"><th style="bold">A <i>head</i></th><td>B<table><tr><td>C</td></tr></table></td></tr></table>'
    )

    hints = layout_hints_from_tokens(parsed, source_ref="rounds/F2.json#1")

    assert len(hints) == 1
    assert hints[0].kind == "table_candidate"
    assert hints[0].table_rows == (("A head", "BC"),)
    assert hints[0].attributes == (
        ("class", "outer"),
        ("tr.class", "row"),
        ("th.style", "bold"),
    )


def test_table_child_scanning_keeps_inline_styles_out_of_visible_text() -> None:
    parsed = tokenize_f2(b"<table><tr><td><i>emphasis</i></td></tr></table>")

    hints = layout_hints_from_tokens(parsed, source_ref="rounds/F2.json#1")

    assert parsed.visible_text == "emphasis"
    assert [token.kind.value for token in parsed.tokens] == [
        "structural_open",
        "structural_open",
        "structural_open",
        "open_tag",
        "text",
        "close_tag",
        "structural_close",
        "structural_close",
        "structural_close",
    ]
    assert hints[0].table_rows == (("emphasis",),)

    payload = b'{"page":"<i>plain</i>"}'
    record = F2Parser().parse_page(
        identity=_identity(payload),
        guideline_version="1",
        f2_artifact_bytes=payload,
        page_key="page",
    )

    assert record.parsed_text == "plain"
    assert [(span.start, span.end) for span in record.style_spans] == [(0, 5)]
    assert hashlib.sha256(record.to_json_bytes()).hexdigest() == (
        "6443ffe25d9d44a073bb47a714e9b7bcb9b8f2d651869e510772b2c11d1e776c"
    )


def test_parser_keeps_nested_table_inline_style_in_page_record() -> None:
    payload = b'{"page":"<table><tr><td><i>emphasis</i></td></tr></table>"}'

    record = F2Parser().parse_page(
        identity=_identity(payload),
        guideline_version="1",
        f2_artifact_bytes=payload,
        page_key="page",
    )

    assert record.parsed_text == "emphasis"
    assert [(span.start, span.end) for span in record.style_spans] == [(0, 8)]


def test_bare_crossed_and_unclosed_markers_produce_no_hint() -> None:
    cases = (b"*/ordinary", b"/*outer/#inner*/#/", b"/*unfinished")

    assert [
        layout_hints_from_tokens(tokenize_f2(case), source_ref="rounds/F2.json#1")
        for case in cases
    ] == [(), (), ()]


def test_mixed_indentation_preserves_the_source_prefix() -> None:
    parsed = tokenize_f2(b"/*\t  line*/")

    hint = layout_hints_from_tokens(parsed, source_ref="rounds/F2.json#1")[0]

    assert hint.lines[0].indent_hint == "\t  "


def test_blank_line_advances_the_poetry_stanza_index() -> None:
    parsed = tokenize_f2(b"/*first\n\nsecond*/")

    hint = layout_hints_from_tokens(parsed, source_ref="rounds/F2.json#1")[0]

    assert [line.stanza_index for line in hint.lines] == [0, 1]


def test_unclosed_table_does_not_swallow_following_text() -> None:
    parsed = tokenize_f2(b"<table><tr><td>cell</td></tr>after")

    hints = layout_hints_from_tokens(parsed, source_ref="rounds/F2.json#1")

    assert hints == ()
    assert parsed.visible_text.endswith("after")


def test_malformed_table_closes_abstain_and_later_table_recovers() -> None:
    malformed = (
        b"<table><tr><td>A</tr></td></table>",
        b"<table><tr><td>A</table></td></tr>",
    )

    assert [
        layout_hints_from_tokens(tokenize_f2(source), source_ref="rounds/F2.json#1")
        for source in malformed
    ] == [(), ()]

    recovered = tokenize_f2(
        b"<table><tr><td>A</tr></td></table><table><tr><td>B</td></tr></table>"
    )

    hints = layout_hints_from_tokens(recovered, source_ref="rounds/F2.json#1")

    assert [hint.table_rows for hint in hints] == [(("B",),)]
