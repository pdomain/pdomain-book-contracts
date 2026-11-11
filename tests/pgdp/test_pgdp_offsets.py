from __future__ import annotations

import hashlib

import pytest

from pdomain_book_contracts.sources.pgdp.offsets import (
    LexicalF2Index,
    LexicalF2PageIndex,
    read_lexical_index,
    read_lexical_json,
    read_lexical_page,
)

_SIMPLE = b'{"p1": "ab"}'

_MALFORMED: list[tuple[bytes, str]] = [
    (b"", "must be a JSON object"),
    (b"   ", "must be a JSON object"),
    (b'["a"]', "must be a JSON object"),
    (b"{abc: 1}", "expected a JSON string"),
    (b'{"a" "b"}', "followed by a colon"),
    (b'{"a"', "followed by a colon"),
    (b'{"a":', "values must be JSON strings"),
    (b'{"a": 1}', "values must be JSON strings"),
    (b'{"a": "x",}', "trailing comma"),
    (b'{"a": "x" "b": "y"}', "must end with a JSON object close"),
    (b'{"a": "x"', "must end with a JSON object close"),
    (b'{"a": "x"} tail', "trailing data"),
    (b'{"a": "x", "a": "y"}', "duplicate F2 page key: 'a'"),
    (b'{"a": "x\x01"}', "unescaped control"),
    (b'{"a": "\\q"}', "invalid JSON escape"),
    (b'{"a": "\\', "ends inside an escape"),
    (b'{"a": "abc', "unterminated JSON string"),
    (b'{"a": "\\u12', "four hexadecimal digits"),
    (b'{"a": "\\u12zz"}', "hexadecimal digits"),
    (b'{"a": "\\ud83d"}', "high surrogate must be followed"),
    (b'{"a": "\\ud83dx"}', "high surrogate must be followed"),
    (b'{"a": "\\ud83d\\u12', "four hexadecimal digits"),
    (b'{"a": "\\ud83d\\u12zz"}', "hexadecimal digits"),
    (b'{"a": "\\ud83d\\u0041"}', "high surrogate must be followed"),
    (b'{"a": "\\udc00"}', "low surrogate must follow"),
    (b'{"a": "\xff"}', "invalid UTF-8"),
    (b'{"a": "\xc3("}', "invalid UTF-8"),
    (b'{"a": "\xc3"}', "invalid UTF-8"),
]


def test_json_reads_page_text_and_value_range() -> None:
    document = read_lexical_json(_SIMPLE)
    assert document.artifact_sha256 == hashlib.sha256(_SIMPLE).hexdigest()
    (page,) = document.pages
    assert page.page_key == "p1"
    assert page.decoded_text == "ab"
    assert page.lexical_value_byte_range == (7, 11)
    assert _SIMPLE[7:11] == b'"ab"'
    assert page.decoded_page_utf8_sha256 == hashlib.sha256(b"ab").hexdigest()


def test_json_character_slices_point_at_the_exact_source_bytes() -> None:
    (page,) = read_lexical_json(_SIMPLE).pages
    assert [c.text for c in page.characters] == ["a", "b"]
    assert [
        (c.source_slice.byte_start, c.source_slice.byte_end) for c in page.characters
    ] == [
        (8, 9),
        (9, 10),
    ]
    assert {c.source_slice.artifact_sha256 for c in page.characters} == {
        hashlib.sha256(_SIMPLE).hexdigest()
    }


def test_json_multibyte_characters_span_all_their_bytes() -> None:
    payload = '{"k": "aé€\U0001f600"}'.encode()
    (page,) = read_lexical_json(payload).pages
    assert page.decoded_text == "aé€\U0001f600"
    widths = [
        c.source_slice.byte_end - c.source_slice.byte_start for c in page.characters
    ]
    assert widths == [1, 2, 3, 4]
    for character in page.characters:
        raw = payload[
            character.source_slice.byte_start : character.source_slice.byte_end
        ]
        assert raw.decode() == character.text


def test_json_simple_escapes_decode_and_keep_two_byte_slices() -> None:
    payload = b'{"k": "\\"\\\\\\/\\b\\f\\n\\r\\t"}'
    (page,) = read_lexical_json(payload).pages
    assert page.decoded_text == '"\\/\b\f\n\r\t'
    assert all(
        c.source_slice.byte_end - c.source_slice.byte_start == 2
        for c in page.characters
    )


def test_json_unicode_escape_is_one_character_over_six_bytes() -> None:
    payload = b'{"k": "x\\u00e9\\u00E9"}'
    (page,) = read_lexical_json(payload).pages
    assert page.decoded_text == "xéé"
    assert [
        (c.source_slice.byte_start, c.source_slice.byte_end) for c in page.characters
    ] == [
        (7, 8),
        (8, 14),
        (14, 20),
    ]


def test_json_surrogate_pair_escape_decodes_to_one_character() -> None:
    payload = b'{"k": "\\ud83d\\ude00!"}'
    (page,) = read_lexical_json(payload).pages
    assert page.decoded_text == "\U0001f600!"
    emoji = page.characters[0]
    assert (emoji.source_slice.byte_start, emoji.source_slice.byte_end) == (7, 19)


def test_json_escaped_keys_are_decoded() -> None:
    (page,) = read_lexical_json(b'{"a\\u0062": "x"}').pages
    assert page.page_key == "ab"


def test_json_tolerates_whitespace_and_keeps_page_order() -> None:
    payload = b' \n{ "b" :\t"1" ,\r\n "a" : "2" }\n '
    document = read_lexical_json(payload)
    assert [(p.page_key, p.decoded_text) for p in document.pages] == [
        ("b", "1"),
        ("a", "2"),
    ]


@pytest.mark.parametrize("payload", [b"{}", b" { } "])
def test_empty_object_has_no_pages(payload: bytes) -> None:
    assert read_lexical_json(payload).pages == ()
    assert read_lexical_index(payload).pages == ()


@pytest.mark.parametrize(("payload", "message"), _MALFORMED)
def test_json_rejects_malformed_artifacts(payload: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        read_lexical_json(payload)


@pytest.mark.parametrize(("payload", "message"), _MALFORMED)
def test_index_rejects_malformed_artifacts(payload: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        read_lexical_index(payload)


def test_index_agrees_with_full_read_on_ranges() -> None:
    payload = '{"one": "a\\u00e9\\ud83d\\ude00", "two": "€\\n"}'.encode()
    index = read_lexical_index(payload)
    document = read_lexical_json(payload)
    assert index.artifact_sha256 == document.artifact_sha256
    assert [(p.page_key, p.lexical_value_byte_range) for p in index.pages] == [
        (p.page_key, p.lexical_value_byte_range) for p in document.pages
    ]


def test_read_page_matches_the_page_from_a_full_read() -> None:
    payload = b'{"p1": "ab", "p2": "c\\u00e9"}'
    index = read_lexical_index(payload)
    expected = {p.page_key: p for p in read_lexical_json(payload).pages}
    for key, page in expected.items():
        assert read_lexical_page(payload, key, index) == page


def test_read_page_rejects_index_from_another_artifact() -> None:
    index = read_lexical_index(_SIMPLE)
    with pytest.raises(ValueError, match="does not match the supplied F2 artifact"):
        read_lexical_page(b'{"p1": "ac"}', "p1", index)


def test_read_page_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="does not contain page key 'zz'"):
        read_lexical_page(_SIMPLE, "zz", read_lexical_index(_SIMPLE))


def test_read_page_rejects_index_range_that_ends_early() -> None:
    index = read_lexical_index(_SIMPLE)
    forged = LexicalF2Index(
        artifact_sha256=index.artifact_sha256,
        pages=(LexicalF2PageIndex(page_key="p1", lexical_value_byte_range=(7, 10)),),
    )
    with pytest.raises(ValueError, match="page range does not match"):
        read_lexical_page(_SIMPLE, "p1", forged)


def test_read_page_rejects_index_range_not_starting_at_a_string() -> None:
    index = read_lexical_index(_SIMPLE)
    forged = LexicalF2Index(
        artifact_sha256=index.artifact_sha256,
        pages=(LexicalF2PageIndex(page_key="p1", lexical_value_byte_range=(8, 11)),),
    )
    with pytest.raises(ValueError, match="expected a JSON string"):
        read_lexical_page(_SIMPLE, "p1", forged)
