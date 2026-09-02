"""Lossless lexical access to JSON-encoded PGDP F2 page strings."""

from __future__ import annotations

import hashlib
import string

from pdomain_book_tools.typography.spans import CanonicalModel, SourceSlice


class DecodedF2Character(CanonicalModel):
    """One decoded JSON character and the bytes that produced it."""

    text: str
    source_slice: SourceSlice


class LexicalF2Page(CanonicalModel):
    """A page value read from F2 JSON without reserializing the artifact."""

    page_key: str
    decoded_text: str
    decoded_page_utf8_sha256: str
    lexical_value_byte_range: tuple[int, int]
    characters: tuple[DecodedF2Character, ...]


class LexicalF2Document(CanonicalModel):
    """A complete F2 artifact with lexical page-value evidence."""

    artifact_sha256: str
    pages: tuple[LexicalF2Page, ...]


class LexicalF2PageIndex(CanonicalModel):
    """Lightweight location data for one page value in an F2 artifact."""

    page_key: str
    lexical_value_byte_range: tuple[int, int]


class LexicalF2Index(CanonicalModel):
    """Bounded-cache-safe lexical index without decoded page characters."""

    artifact_sha256: str
    pages: tuple[LexicalF2PageIndex, ...]


_JSON_WHITESPACE = frozenset(b" \t\r\n")
_SIMPLE_ESCAPES = {
    ord('"'): '"',
    ord("\\"): "\\",
    ord("/"): "/",
    ord("b"): "\b",
    ord("f"): "\f",
    ord("n"): "\n",
    ord("r"): "\r",
    ord("t"): "\t",
}


def _skip_whitespace(payload: bytes, index: int) -> int:
    while index < len(payload) and payload[index] in _JSON_WHITESPACE:
        index += 1
    return index


def _source_slice(artifact_sha256: str, start: int, end: int) -> SourceSlice:
    return SourceSlice(
        artifact_sha256=artifact_sha256,
        byte_start=start,
        byte_end=end,
    )


def _utf8_width(first_byte: int) -> int:
    if first_byte < 0x80:
        return 1
    if 0xC2 <= first_byte <= 0xDF:
        return 2
    if 0xE0 <= first_byte <= 0xEF:
        return 3
    if 0xF0 <= first_byte <= 0xF4:
        return 4
    msg = "invalid UTF-8 byte in F2 JSON string"
    raise ValueError(msg)


def _decode_json_string(
    payload: bytes, start: int, artifact_sha256: str
) -> tuple[int, tuple[DecodedF2Character, ...]]:
    if start >= len(payload) or payload[start] != ord('"'):
        msg = "expected a JSON string"
        raise ValueError(msg)
    index = start + 1
    characters: list[DecodedF2Character] = []
    while index < len(payload):
        current = payload[index]
        if current == ord('"'):
            return index + 1, tuple(characters)
        if current < 0x20:
            msg = "JSON strings cannot contain unescaped control bytes"
            raise ValueError(msg)
        if current == ord("\\"):
            escape_start = index
            index += 1
            if index >= len(payload):
                msg = "JSON string ends inside an escape"
                raise ValueError(msg)
            escaped = payload[index]
            if escaped == ord("u"):
                first_end = index + 5
                if first_end > len(payload):
                    msg = "JSON unicode escape must contain four hexadecimal digits"
                    raise ValueError(msg)
                digits = payload[index + 1 : first_end]
                if any(byte not in string.hexdigits.encode() for byte in digits):
                    msg = "JSON unicode escape must contain hexadecimal digits"
                    raise ValueError(msg)
                codepoint = int(digits.decode("ascii"), 16)
                index = first_end
                if 0xD800 <= codepoint <= 0xDBFF:
                    if payload[index : index + 2] != b"\\u":
                        msg = "high surrogate must be followed by a low surrogate"
                        raise ValueError(msg)
                    second_end = index + 6
                    if second_end > len(payload):
                        msg = "JSON unicode escape must contain four hexadecimal digits"
                        raise ValueError(msg)
                    low_digits = payload[index + 2 : second_end]
                    if any(
                        byte not in string.hexdigits.encode() for byte in low_digits
                    ):
                        msg = "JSON unicode escape must contain hexadecimal digits"
                        raise ValueError(msg)
                    low_surrogate = int(low_digits.decode("ascii"), 16)
                    if not 0xDC00 <= low_surrogate <= 0xDFFF:
                        msg = "high surrogate must be followed by a low surrogate"
                        raise ValueError(msg)
                    codepoint = (
                        0x10000
                        + (codepoint - 0xD800) * 0x400
                        + (low_surrogate - 0xDC00)
                    )
                    index = second_end
                elif 0xDC00 <= codepoint <= 0xDFFF:
                    msg = "low surrogate must follow a high surrogate"
                    raise ValueError(msg)
                characters.append(
                    DecodedF2Character(
                        text=chr(codepoint),
                        source_slice=_source_slice(
                            artifact_sha256, escape_start, index
                        ),
                    )
                )
                continue
            decoded = _SIMPLE_ESCAPES.get(escaped)
            if decoded is None:
                msg = "invalid JSON escape"
                raise ValueError(msg)
            index += 1
            characters.append(
                DecodedF2Character(
                    text=decoded,
                    source_slice=_source_slice(artifact_sha256, escape_start, index),
                )
            )
            continue
        width = _utf8_width(current)
        end = index + width
        try:
            decoded_text = payload[index:end].decode("utf-8")
        except UnicodeDecodeError as error:
            msg = "invalid UTF-8 byte in F2 JSON string"
            raise ValueError(msg) from error
        characters.append(
            DecodedF2Character(
                text=decoded_text,
                source_slice=_source_slice(artifact_sha256, index, end),
            )
        )
        index = end
    msg = "unterminated JSON string"
    raise ValueError(msg)


def _skip_json_string(payload: bytes, start: int) -> int:
    """Validate and skip one JSON string without retaining decoded characters."""
    if start >= len(payload) or payload[start] != ord('"'):
        msg = "expected a JSON string"
        raise ValueError(msg)
    index = start + 1
    while index < len(payload):
        current = payload[index]
        if current == ord('"'):
            return index + 1
        if current < 0x20:
            msg = "JSON strings cannot contain unescaped control bytes"
            raise ValueError(msg)
        if current == ord("\\"):
            index += 1
            if index >= len(payload):
                msg = "JSON string ends inside an escape"
                raise ValueError(msg)
            escaped = payload[index]
            if escaped == ord("u"):
                first_end = index + 5
                if first_end > len(payload):
                    msg = "JSON unicode escape must contain four hexadecimal digits"
                    raise ValueError(msg)
                digits = payload[index + 1 : first_end]
                if any(byte not in string.hexdigits.encode() for byte in digits):
                    msg = "JSON unicode escape must contain hexadecimal digits"
                    raise ValueError(msg)
                codepoint = int(digits.decode("ascii"), 16)
                index = first_end
                if 0xD800 <= codepoint <= 0xDBFF:
                    if payload[index : index + 2] != b"\\u":
                        msg = "high surrogate must be followed by a low surrogate"
                        raise ValueError(msg)
                    second_end = index + 6
                    if second_end > len(payload):
                        msg = "JSON unicode escape must contain four hexadecimal digits"
                        raise ValueError(msg)
                    low_digits = payload[index + 2 : second_end]
                    if any(
                        byte not in string.hexdigits.encode() for byte in low_digits
                    ):
                        msg = "JSON unicode escape must contain hexadecimal digits"
                        raise ValueError(msg)
                    low_surrogate = int(low_digits.decode("ascii"), 16)
                    if not 0xDC00 <= low_surrogate <= 0xDFFF:
                        msg = "high surrogate must be followed by a low surrogate"
                        raise ValueError(msg)
                    index = second_end
                elif 0xDC00 <= codepoint <= 0xDFFF:
                    msg = "low surrogate must follow a high surrogate"
                    raise ValueError(msg)
                continue
            if escaped not in _SIMPLE_ESCAPES:
                msg = "invalid JSON escape"
                raise ValueError(msg)
            index += 1
            continue
        width = _utf8_width(current)
        end = index + width
        try:
            payload[index:end].decode("utf-8")
        except UnicodeDecodeError as error:
            msg = "invalid UTF-8 byte in F2 JSON string"
            raise ValueError(msg) from error
        index = end
    msg = "unterminated JSON string"
    raise ValueError(msg)


def read_lexical_f2_index(artifact_bytes: bytes) -> LexicalF2Index:
    """Index all F2 page strings without retaining their decoded character maps."""
    artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    index = _skip_whitespace(artifact_bytes, 0)
    if index >= len(artifact_bytes) or artifact_bytes[index] != ord("{"):
        msg = "F2 artifact must be a JSON object"
        raise ValueError(msg)
    index = _skip_whitespace(artifact_bytes, index + 1)
    pages: list[LexicalF2PageIndex] = []
    page_keys: set[str] = set()
    while index < len(artifact_bytes) and artifact_bytes[index] != ord("}"):
        index, key_characters = _decode_json_string(
            artifact_bytes, index, artifact_sha256
        )
        page_key = "".join(character.text for character in key_characters)
        if page_key in page_keys:
            msg = f"duplicate F2 page key: {page_key!r}"
            raise ValueError(msg)
        page_keys.add(page_key)
        index = _skip_whitespace(artifact_bytes, index)
        if index >= len(artifact_bytes) or artifact_bytes[index] != ord(":"):
            msg = "F2 page key must be followed by a colon"
            raise ValueError(msg)
        value_start = _skip_whitespace(artifact_bytes, index + 1)
        if value_start >= len(artifact_bytes) or artifact_bytes[value_start] != ord(
            '"'
        ):
            msg = "F2 page values must be JSON strings"
            raise ValueError(msg)
        value_end = _skip_json_string(artifact_bytes, value_start)
        pages.append(
            LexicalF2PageIndex(
                page_key=page_key,
                lexical_value_byte_range=(value_start, value_end),
            )
        )
        index = _skip_whitespace(artifact_bytes, value_end)
        if index < len(artifact_bytes) and artifact_bytes[index] == ord(","):
            index = _skip_whitespace(artifact_bytes, index + 1)
            if index < len(artifact_bytes) and artifact_bytes[index] == ord("}"):
                msg = "F2 artifact must not contain a trailing comma"
                raise ValueError(msg)
            continue
        break
    if index >= len(artifact_bytes) or artifact_bytes[index] != ord("}"):
        msg = "F2 artifact must end with a JSON object close"
        raise ValueError(msg)
    if _skip_whitespace(artifact_bytes, index + 1) != len(artifact_bytes):
        msg = "F2 artifact must not contain trailing data"
        raise ValueError(msg)
    return LexicalF2Index(artifact_sha256=artifact_sha256, pages=tuple(pages))


def read_lexical_f2_page(
    artifact_bytes: bytes,
    page_key: str,
    index: LexicalF2Index,
) -> LexicalF2Page:
    """Decode one indexed page, retaining the source map only for that page."""
    artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    if artifact_sha256 != index.artifact_sha256:
        msg = "lexical index does not match the supplied F2 artifact"
        raise ValueError(msg)
    page_index = next(
        (candidate for candidate in index.pages if candidate.page_key == page_key),
        None,
    )
    if page_index is None:
        msg = f"F2 artifact does not contain page key {page_key!r}"
        raise ValueError(msg)
    start, expected_end = page_index.lexical_value_byte_range
    end, characters = _decode_json_string(artifact_bytes, start, artifact_sha256)
    if end != expected_end:
        msg = "lexical index page range does not match the supplied F2 artifact"
        raise ValueError(msg)
    decoded_text = "".join(character.text for character in characters)
    return LexicalF2Page(
        page_key=page_key,
        decoded_text=decoded_text,
        decoded_page_utf8_sha256=hashlib.sha256(decoded_text.encode()).hexdigest(),
        lexical_value_byte_range=page_index.lexical_value_byte_range,
        characters=characters,
    )


def read_lexical_f2_json(artifact_bytes: bytes) -> LexicalF2Document:
    """Read F2 pages and retain exact artifact locations for every character."""
    artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    index = _skip_whitespace(artifact_bytes, 0)
    if index >= len(artifact_bytes) or artifact_bytes[index] != ord("{"):
        msg = "F2 artifact must be a JSON object"
        raise ValueError(msg)
    index = _skip_whitespace(artifact_bytes, index + 1)
    pages: list[LexicalF2Page] = []
    page_keys: set[str] = set()
    while index < len(artifact_bytes) and artifact_bytes[index] != ord("}"):
        index, key_characters = _decode_json_string(
            artifact_bytes, index, artifact_sha256
        )
        page_key = "".join(character.text for character in key_characters)
        if page_key in page_keys:
            msg = f"duplicate F2 page key: {page_key!r}"
            raise ValueError(msg)
        page_keys.add(page_key)
        index = _skip_whitespace(artifact_bytes, index)
        if index >= len(artifact_bytes) or artifact_bytes[index] != ord(":"):
            msg = "F2 page key must be followed by a colon"
            raise ValueError(msg)
        value_start = _skip_whitespace(artifact_bytes, index + 1)
        if value_start >= len(artifact_bytes) or artifact_bytes[value_start] != ord(
            '"'
        ):
            msg = "F2 page values must be JSON strings"
            raise ValueError(msg)
        value_end, characters = _decode_json_string(
            artifact_bytes, value_start, artifact_sha256
        )
        pages.append(
            LexicalF2Page(
                page_key=page_key,
                decoded_text="".join(character.text for character in characters),
                decoded_page_utf8_sha256=hashlib.sha256(
                    "".join(character.text for character in characters).encode()
                ).hexdigest(),
                lexical_value_byte_range=(value_start, value_end),
                characters=characters,
            )
        )
        index = _skip_whitespace(artifact_bytes, value_end)
        if index < len(artifact_bytes) and artifact_bytes[index] == ord(","):
            index = _skip_whitespace(artifact_bytes, index + 1)
            if index < len(artifact_bytes) and artifact_bytes[index] == ord("}"):
                msg = "F2 artifact must not contain a trailing comma"
                raise ValueError(msg)
            continue
        break
    if index >= len(artifact_bytes) or artifact_bytes[index] != ord("}"):
        msg = "F2 artifact must end with a JSON object close"
        raise ValueError(msg)
    if _skip_whitespace(artifact_bytes, index + 1) != len(artifact_bytes):
        msg = "F2 artifact must not contain trailing data"
        raise ValueError(msg)
    return LexicalF2Document(artifact_sha256=artifact_sha256, pages=tuple(pages))
