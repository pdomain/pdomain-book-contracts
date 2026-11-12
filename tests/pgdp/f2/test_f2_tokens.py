from __future__ import annotations

import hashlib
import json

import pytest

from pdomain_book_contracts.sources.pgdp.f2.tokens import (
    F2_TOKENIZER_VERSION,
    F2NormalizationKind,
    F2PageTokens,
    F2TokenKind,
    read_f2_json,
    read_f2_json_page,
    tokenize_f2,
)
from pdomain_book_contracts.sources.pgdp.offsets import read_lexical_index


def _kinds(parsed: F2PageTokens) -> list[tuple[str, str]]:
    return [(token.kind.value, token.text) for token in parsed.tokens]


def _tokenize(text: str) -> F2PageTokens:
    return tokenize_f2(text.encode())


_LOSSLESS_SAMPLES = [
    "plain text",
    "a<i>b</i>c",
    "<i>x</b>y",
    "[**note?] ok",
    "[**unclosed",
    "a<tb>b",
    "<table><tr><td>x</td></tr></table>",
    "<foo>bar</foo>z",
    "<foo>bar",
    "x^{2} y_{n} a^2 b_3",
    "a^{ ",
    "a^",
    "<g>a b c</g>",
    "/* x */ /# y #/",
    "a <b",
    "café <sc>Naïve</sc>\r\n",
]


@pytest.mark.parametrize("text", _LOSSLESS_SAMPLES)
def test_token_text_reassembles_the_exact_source(text: str) -> None:
    parsed = _tokenize(text)
    assert "".join(token.text for token in parsed.tokens) == text


@pytest.mark.parametrize("text", _LOSSLESS_SAMPLES)
def test_token_source_slices_cover_every_source_byte_exactly_once(text: str) -> None:
    raw = text.encode()
    parsed = tokenize_f2(raw)
    covered: list[int] = []
    for token in parsed.tokens:
        covered.extend(
            byte
            for source in token.source_slices
            for byte in range(source.byte_start, source.byte_end)
        )
    assert sorted(covered) == list(range(len(raw)))
    for token in parsed.tokens:
        rebuilt = b"".join(raw[s.byte_start : s.byte_end] for s in token.source_slices)
        assert rebuilt.decode() == token.text


def test_page_metadata_identifies_tokenizer_and_source_hash() -> None:
    raw = b"hello"
    parsed = tokenize_f2(raw)
    assert parsed.tokenizer_version == F2_TOKENIZER_VERSION
    assert parsed.artifact_sha256 == hashlib.sha256(raw).hexdigest()
    assert parsed.delimiter_scan_count == 2 * len(raw)


def test_empty_page_has_no_tokens_or_graphemes() -> None:
    parsed = tokenize_f2(b"")
    assert parsed.tokens == ()
    assert parsed.graphemes == ()
    assert parsed.visible_text == ""
    assert parsed.warning_codes == ()


def test_invalid_utf8_page_bytes_are_rejected() -> None:
    with pytest.raises(ValueError, match="must be valid UTF-8"):
        tokenize_f2(b"ok \xff")


def test_inline_tags_are_hidden_from_visible_text() -> None:
    parsed = _tokenize("a<i>b</i>c")
    assert parsed.visible_text == "abc"
    assert _kinds(parsed) == [
        ("text", "a"),
        ("open_tag", "<i>"),
        ("text", "b"),
        ("close_tag", "</i>"),
        ("text", "c"),
    ]
    assert parsed.warning_codes == ()


@pytest.mark.parametrize("tag", ["i", "b", "sc", "g", "f", "u"])
def test_every_known_inline_tag_is_recognised(tag: str) -> None:
    parsed = _tokenize(f"<{tag}>x</{tag}>")
    assert [token.kind for token in parsed.tokens] == [
        F2TokenKind.OPEN_TAG,
        F2TokenKind.TEXT,
        F2TokenKind.CLOSE_TAG,
    ]


def test_mismatched_close_tag_warns_and_leaves_open_tag_unclosed() -> None:
    parsed = _tokenize("<i>x</b>y")
    assert parsed.visible_text == "xy"
    assert parsed.warning_codes == ("mismatched_close_tag", "unclosed_tag")


def test_close_tag_without_open_warns() -> None:
    parsed = _tokenize("</i>")
    assert parsed.warning_codes == ("mismatched_close_tag",)
    assert parsed.visible_text == ""


def test_unclosed_tag_warning_points_at_the_open_tag_bytes() -> None:
    parsed = _tokenize("ab<i>x")
    (warning,) = parsed.warnings
    assert warning.code == "unclosed_tag"
    assert [(s.byte_start, s.byte_end) for s in warning.source_slices] == [
        (2, 3),
        (3, 4),
        (4, 5),
    ]


def test_nested_tags_close_in_order_without_warning() -> None:
    parsed = _tokenize("<b><i>x</i></b>")
    assert parsed.warning_codes == ()
    assert parsed.visible_text == "x"


def test_tag_with_attributes_is_unknown_not_inline() -> None:
    parsed = _tokenize("<i class='x'>t</i>")
    assert [token.kind for token in parsed.tokens] == [F2TokenKind.UNKNOWN] * 3
    assert parsed.visible_text == "<i class='x'>t</i>"
    assert parsed.warning_codes == ("unknown_construct",)


def test_structural_tags_are_hidden_and_keep_their_content() -> None:
    parsed = _tokenize("<table><tr><th>h</th><td>x</td></tr></table>")
    kinds = [token.kind for token in parsed.tokens]
    assert kinds[:3] == [
        F2TokenKind.STRUCTURAL_OPEN,
        F2TokenKind.STRUCTURAL_OPEN,
        F2TokenKind.STRUCTURAL_OPEN,
    ]
    assert kinds.count(F2TokenKind.STRUCTURAL_CLOSE) == 4
    assert parsed.visible_text == "hx"
    assert parsed.warning_codes == ()


def test_tb_is_a_control_with_no_visible_text() -> None:
    parsed = _tokenize("a<tb>b")
    assert _kinds(parsed) == [("text", "a"), ("control", "<tb>"), ("text", "b")]
    assert parsed.visible_text == "ab"


def test_unknown_tag_with_matching_close_is_visible_and_warned() -> None:
    parsed = _tokenize("<foo>bar</foo>z")
    assert _kinds(parsed) == [
        ("unknown", "<foo>"),
        ("unknown", "bar"),
        ("unknown", "</foo>"),
        ("text", "z"),
    ]
    assert parsed.visible_text == "<foo>bar</foo>z"
    assert parsed.warning_codes == ("unknown_construct",)


def test_unknown_tag_without_close_swallows_rest_of_page() -> None:
    parsed = _tokenize("<foo>bar <i>x</i>")
    assert _kinds(parsed) == [("unknown", "<foo>"), ("unknown", "bar <i>x</i>")]
    assert parsed.warning_codes == ("unknown_construct", "unclosed_unknown_tag")
    assert parsed.visible_text == "<foo>bar <i>x</i>"


def test_unknown_tag_at_end_of_page_has_no_body_token() -> None:
    parsed = _tokenize("<foo>")
    assert _kinds(parsed) == [("unknown", "<foo>")]
    assert parsed.warning_codes == ("unknown_construct", "unclosed_unknown_tag")


def test_unknown_tag_with_empty_body_has_no_body_token() -> None:
    parsed = _tokenize("<foo></foo>")
    assert _kinds(parsed) == [("unknown", "<foo>"), ("unknown", "</foo>")]


def test_stray_unknown_closing_tag_is_a_single_unknown_token() -> None:
    parsed = _tokenize("x</foo>y")
    assert _kinds(parsed) == [("text", "x"), ("unknown", "</foo>"), ("text", "y")]
    assert parsed.warning_codes == ("unknown_construct",)


@pytest.mark.parametrize("text", ["<i", "a <b", "a <b c"])
def test_unterminated_tag_start_is_invalid_and_swallows_rest(text: str) -> None:
    parsed = _tokenize(text)
    assert parsed.warning_codes == ("invalid_construct",)
    assert parsed.visible_text == text
    assert parsed.tokens[-1].kind is F2TokenKind.UNKNOWN


@pytest.mark.parametrize("text", ["a < b", " <3", "1 <\n2"])
def test_lone_angle_bracket_is_plain_text(text: str) -> None:
    parsed = _tokenize(text)
    assert parsed.warning_codes == ()
    assert parsed.visible_text == text
    assert [token.kind for token in parsed.tokens] == [F2TokenKind.TEXT]


def test_angle_bracket_before_a_tag_stays_visible() -> None:
    parsed = _tokenize("<<i>x</i>")
    assert parsed.visible_text == "<x"


def test_note_is_hidden_from_visible_text() -> None:
    parsed = _tokenize("[**note?] ok")
    assert _kinds(parsed) == [("note", "[**note?]"), ("text", " ok")]
    assert parsed.visible_text == " ok"


def test_single_star_bracket_is_not_a_note() -> None:
    parsed = _tokenize("[* not note]")
    assert _kinds(parsed) == [("text", "[* not note]")]


def test_unclosed_note_keeps_remaining_page_visible_and_warns() -> None:
    parsed = _tokenize("a [**unclosed <i>x")
    assert _kinds(parsed) == [("text", "a "), ("unknown", "[**unclosed <i>x")]
    assert parsed.warning_codes == ("unclosed_note",)
    assert parsed.visible_text == "a [**unclosed <i>x"


@pytest.mark.parametrize(
    ("marker", "kind"),
    [
        ("/*", F2TokenKind.BLOCK_OPEN),
        ("/#", F2TokenKind.BLOCK_OPEN),
        ("*/", F2TokenKind.BLOCK_CLOSE),
        ("#/", F2TokenKind.BLOCK_CLOSE),
    ],
)
def test_block_markers_are_hidden_controls(marker: str, kind: F2TokenKind) -> None:
    parsed = _tokenize(f"a{marker}b")
    assert [token.kind for token in parsed.tokens] == [
        F2TokenKind.TEXT,
        kind,
        F2TokenKind.TEXT,
    ]
    assert parsed.visible_text == "ab"


def test_braced_and_bare_scripts_expose_only_their_content() -> None:
    parsed = _tokenize("x^{2} y_{n} a^2 b_3")
    assert _kinds(parsed) == [
        ("text", "x"),
        ("superscript", "^{2}"),
        ("text", " y"),
        ("subscript", "_{n}"),
        ("text", " a"),
        ("superscript", "^2"),
        ("text", " b"),
        ("subscript", "_3"),
    ]
    assert parsed.visible_text == "x2 yn a2 b3"
    assert [
        t.visible_text for t in parsed.tokens if t.kind is F2TokenKind.SUPERSCRIPT
    ] == [
        "2",
        "2",
    ]


def test_braced_script_may_hold_several_characters() -> None:
    parsed = _tokenize("m^{th} and ^{é}")
    assert parsed.visible_text == "mth and é"


@pytest.mark.parametrize("text", ["a^{", "a^{ ", "a^{} b", "a_{x"])
def test_unterminated_or_empty_script_braces_are_invalid(text: str) -> None:
    parsed = _tokenize(text)
    assert parsed.warning_codes == ("invalid_construct",)
    assert parsed.visible_text == text
    assert parsed.tokens[-1].kind is F2TokenKind.UNKNOWN


def test_caret_at_end_of_page_is_invalid() -> None:
    parsed = _tokenize("a^")
    assert _kinds(parsed) == [("text", "a"), ("unknown", "^")]
    assert parsed.warning_codes == ("invalid_construct",)


@pytest.mark.parametrize("text", ["a^ b", "a_\nb", "a^>b", "a^]b", "a_}b"])
def test_script_marker_before_space_or_bracket_is_plain_text(text: str) -> None:
    parsed = _tokenize(text)
    assert parsed.warning_codes == ()
    assert parsed.visible_text == text


def test_letter_spaced_text_drops_spaces_and_records_the_operation() -> None:
    parsed = _tokenize("<g>a b</g> c")
    assert parsed.visible_text == "ab c"
    (operation,) = parsed.normalizations
    assert operation.kind is F2NormalizationKind.LETTER_SPACE_REMOVED
    assert operation.replacement_text == ""
    assert [(s.byte_start, s.byte_end) for s in operation.source_slices] == [(4, 5)]
    normalization_tokens = [
        t for t in parsed.tokens if t.kind is F2TokenKind.NORMALIZATION
    ]
    assert [t.text for t in normalization_tokens] == [" "]
    assert (
        normalization_tokens[0].normalization_kind
        is F2NormalizationKind.LETTER_SPACE_REMOVED
    )


def test_spaces_outside_letter_spacing_are_kept() -> None:
    parsed = _tokenize("a b <i>c d</i>")
    assert parsed.visible_text == "a b c d"
    assert parsed.normalizations == ()


def test_letter_spacing_applies_only_to_spaces_not_other_whitespace() -> None:
    assert _tokenize("<g>a\tb</g>").visible_text == "a\tb"


def test_graphemes_keep_combining_marks_with_their_base() -> None:
    parsed = tokenize_f2("éx".encode())
    assert [g.text for g in parsed.graphemes] == ["é", "x"]
    assert [g.index for g in parsed.graphemes] == [0, 1]


def test_direct_tokenization_merges_contiguous_grapheme_slices() -> None:
    parsed = tokenize_f2("é".encode())
    (grapheme,) = parsed.graphemes
    assert [(s.byte_start, s.byte_end) for s in grapheme.source_slices] == [(0, 3)]


def test_grapheme_slices_skip_hidden_markup_bytes() -> None:
    parsed = _tokenize("a<i>b</i>")
    assert [
        [(s.byte_start, s.byte_end) for s in g.source_slices] for g in parsed.graphemes
    ] == [[(0, 1)], [(4, 5)]]


def _json_artifact(pages: dict[str, str]) -> bytes:
    return json.dumps(pages, ensure_ascii=False).encode()


def test_read_f2_json_tokenizes_every_page_against_the_artifact_hash() -> None:
    artifact = _json_artifact({"001.png": "a<i>b</i>", "002.png": "x^{2}"})
    document = read_f2_json(artifact)
    assert document.artifact_sha256 == hashlib.sha256(artifact).hexdigest()
    assert [page.page_key for page in document.pages] == ["001.png", "002.png"]
    assert [page.parsed.visible_text for page in document.pages] == ["ab", "x2"]
    assert all(
        page.parsed.artifact_sha256 == document.artifact_sha256
        for page in document.pages
    )
    first = document.pages[0]
    assert first.decoded_text == "a<i>b</i>"
    assert artifact[first.lexical_value_byte_range[0]] == ord('"')


def test_read_f2_json_slices_point_into_the_json_bytes() -> None:
    artifact = _json_artifact({"p": "a\nb<i>c</i>"})
    (page,) = read_f2_json(artifact).pages
    for grapheme in page.parsed.graphemes:
        raw = b"".join(
            artifact[s.byte_start : s.byte_end] for s in grapheme.source_slices
        )
        assert raw in (b"a", b"\\n", b"b", b"c")


def test_read_f2_json_does_not_merge_escaped_character_slices() -> None:
    artifact = b'{"p": "e\\u0301"}'
    (page,) = read_f2_json(artifact).pages
    (grapheme,) = page.parsed.graphemes
    assert grapheme.text == "é"
    assert [(s.byte_start, s.byte_end) for s in grapheme.source_slices] == [
        (7, 8),
        (8, 14),
    ]


def test_read_f2_json_propagates_malformed_artifact() -> None:
    with pytest.raises(ValueError, match="must be a JSON object"):
        read_f2_json(b"[]")


def test_read_f2_json_page_equals_the_same_page_from_a_full_read() -> None:
    artifact = _json_artifact({"a": "<i>x", "b": "[**q?] y"})
    index = read_lexical_index(artifact)
    full = {page.page_key: page for page in read_f2_json(artifact).pages}
    assert read_f2_json_page(artifact, "b", index) == full["b"]
    assert read_f2_json_page(artifact, "a", index) == full["a"]


def test_read_f2_json_page_rejects_unknown_key() -> None:
    artifact = _json_artifact({"a": "x"})
    with pytest.raises(ValueError, match="does not contain page key 'zz'"):
        read_f2_json_page(artifact, "zz", read_lexical_index(artifact))
