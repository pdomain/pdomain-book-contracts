"""Byte-preserving PGDP F2 tokenization."""

from __future__ import annotations

import hashlib
from bisect import bisect_left
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import regex

from pdomain_book_contracts.sources.pgdp.offsets import (
    DecodedF2Character,
    read_lexical_json,
    read_lexical_page,
)
from pdomain_book_contracts.typography.records import Grapheme
from pdomain_book_contracts.typography.spans import CanonicalModel, SourceSlice

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pdomain_book_contracts.sources.pgdp.offsets import (
        LexicalF2Index,
        LexicalF2Page,
    )

F2_TOKENIZER_VERSION = f"f2-tokenizer-1+regex-{regex.__version__}"
_KNOWN_TAGS = frozenset({"i", "b", "sc", "g", "f", "u"})
_BLOCK_MARKERS = {
    "/*": "block_open",
    "*/": "block_close",
    "/#": "block_open",
    "#/": "block_close",
}


class F2TokenKind(StrEnum):
    """Syntactic items recognized before F2 style resolution."""

    TEXT = "text"
    OPEN_TAG = "open_tag"
    CLOSE_TAG = "close_tag"
    NOTE = "note"
    BLOCK_OPEN = "block_open"
    BLOCK_CLOSE = "block_close"
    SUPERSCRIPT = "superscript"
    SUBSCRIPT = "subscript"
    NORMALIZATION = "normalization"
    UNKNOWN = "unknown"


class F2NormalizationKind(StrEnum):
    """Auditable text transformations applied during lexical tokenization."""

    LETTER_SPACE_REMOVED = "letter_space_removed"


class F2NormalizationOperation(CanonicalModel):
    """One source-preserving transformation from F2 controls to visible text."""

    kind: F2NormalizationKind
    source_slices: tuple[SourceSlice, ...]
    replacement_text: str


class F2Token(CanonicalModel):
    """One lossless F2 lexical token."""

    kind: F2TokenKind
    text: str
    source_slices: tuple[SourceSlice, ...]
    visible_text: str
    normalization_kind: F2NormalizationKind | None = None


class F2Warning(CanonicalModel):
    """A local parse warning with exact source evidence."""

    code: str
    source_slices: tuple[SourceSlice, ...]


class F2PageTokens(CanonicalModel):
    """Visible graphemes and lexical controls for one independently parsed page."""

    tokenizer_version: str
    artifact_sha256: str
    visible_text: str
    graphemes: tuple[Grapheme, ...]
    tokens: tuple[F2Token, ...]
    normalizations: tuple[F2NormalizationOperation, ...] = ()
    warnings: tuple[F2Warning, ...]
    warning_codes: tuple[str, ...]
    delimiter_scan_count: int = 0
    opaque_tag_scan_count: int = 0


class F2JsonPage(CanonicalModel):
    """A lexically located F2 page and its isolated tokenization."""

    page_key: str
    decoded_text: str
    decoded_page_utf8_sha256: str
    lexical_value_byte_range: tuple[int, int]
    characters: tuple[DecodedF2Character, ...]
    parsed: F2PageTokens


class F2JsonDocument(CanonicalModel):
    """All pages parsed from one exact F2 JSON artifact."""

    artifact_sha256: str
    pages: tuple[F2JsonPage, ...]


def _slice_for_characters(
    characters: Sequence[DecodedF2Character],
) -> tuple[SourceSlice, ...]:
    return tuple(character.source_slice for character in characters)


def _direct_characters(page_bytes: bytes) -> tuple[str, tuple[DecodedF2Character, ...]]:
    artifact_sha256 = hashlib.sha256(page_bytes).hexdigest()
    try:
        decoded = page_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        msg = "F2 page bytes must be valid UTF-8"
        raise ValueError(msg) from error
    characters: list[DecodedF2Character] = []
    byte_start = 0
    for character in decoded:
        byte_end = byte_start + len(character.encode())
        characters.append(
            DecodedF2Character(
                text=character,
                source_slice=SourceSlice(
                    artifact_sha256=artifact_sha256,
                    byte_start=byte_start,
                    byte_end=byte_end,
                ),
            )
        )
        byte_start = byte_end
    return artifact_sha256, tuple(characters)


def _append_graphemes(
    visible_characters: Sequence[DecodedF2Character],
    artifact_sha256: str,
    *,
    merge_contiguous_source_slices: bool,
) -> tuple[str, tuple[Grapheme, ...]]:
    visible_text = "".join(character.text for character in visible_characters)
    graphemes: list[Grapheme] = []
    character_index = 0
    # regex.findall()'s stub returns list[Any] (its true return shape depends
    # on the pattern's capture-group config); this pattern has no groups, so
    # narrow the actual list[str] result once here rather than letting Any
    # spread into grapheme_text below (reportAny, strict in this package
    # but not enabled in pdomain-book-tools — found landing Task 4 Step 3).
    found_graphemes: list[str] = regex.findall(r"\X", visible_text)
    for grapheme_text in found_graphemes:
        length = len(grapheme_text)
        members = visible_characters[character_index : character_index + length]
        if "".join(member.text for member in members) != grapheme_text:
            msg = "grapheme segmentation lost source character boundaries"
            raise ValueError(msg)
        source_slices: list[SourceSlice] = []
        for source_slice in _slice_for_characters(members):
            if (
                merge_contiguous_source_slices
                and source_slices
                and source_slices[-1].artifact_sha256 == source_slice.artifact_sha256
                and source_slices[-1].byte_end == source_slice.byte_start
            ):
                previous = source_slices.pop()
                source_slices.append(
                    SourceSlice(
                        artifact_sha256=previous.artifact_sha256,
                        byte_start=previous.byte_start,
                        byte_end=source_slice.byte_end,
                    )
                )
            else:
                source_slices.append(source_slice)
        graphemes.append(
            Grapheme(
                index=len(graphemes),
                text=grapheme_text,
                source_slices=tuple(source_slices),
                normalized_from=None,
            )
        )
        character_index += length
    if character_index != len(visible_characters):
        msg = "grapheme segmentation did not consume every visible character"
        raise ValueError(msg)
    return visible_text, tuple(graphemes)


def _is_inline_tag(text: str) -> tuple[bool, str] | None:
    tag = _opaque_tag_parts(text)
    if tag is None or tag[1] not in _KNOWN_TAGS:
        return None
    closing, tag_name = tag
    expected = f"</{tag_name}>" if closing else f"<{tag_name}>"
    if text != expected:
        return None
    return tag


@dataclass(frozen=True)
class _DelimiterIndex:
    """One-pass lookup tables for all delimiters scanned by the tokenizer."""

    note_ends: tuple[int | None, ...]
    script_ends: tuple[int | None, ...]
    scan_count: int


def _next_delimiter_ends(
    characters: Sequence[DecodedF2Character], delimiter: str
) -> tuple[int | None, ...]:
    ends: list[int | None] = [None] * (len(characters) + 1)
    next_end: int | None = None
    for index in range(len(characters) - 1, -1, -1):
        if characters[index].text == delimiter:
            next_end = index + 1
        ends[index] = next_end
    return tuple(ends)


def _build_delimiter_index(
    characters: Sequence[DecodedF2Character],
) -> _DelimiterIndex:
    return _DelimiterIndex(
        note_ends=_next_delimiter_ends(characters, "]"),
        script_ends=_next_delimiter_ends(characters, "}"),
        scan_count=len(characters) * 2,
    )


@dataclass(frozen=True)
class _OpaqueTagBoundary:
    """One valid opaque tag boundary found during a linear lexical pass."""

    end: int
    closing: bool
    name: str


@dataclass(frozen=True)
class _OpaqueTagIndex:
    """Precomputed opaque tag boundaries and matching closing-tag positions."""

    boundaries_by_start: dict[int, _OpaqueTagBoundary]
    closing_starts_by_name: dict[str, tuple[int, ...]]
    closing_ends_by_name: dict[str, tuple[int, ...]]
    scan_count: int


def _opaque_tag_parts(text: str) -> tuple[bool, str] | None:
    if not text.startswith("<") or not text.endswith(">"):
        return None
    content = text[1:-1]
    closing = content.startswith("/")
    body = content[1:] if closing else content
    tag_name_end = next(
        (index for index, character in enumerate(body) if character.isspace()),
        len(body),
    )
    tag_name = body[:tag_name_end]
    if not tag_name or any(character in "</\t\r\n" for character in tag_name):
        return None
    return closing, tag_name


def _build_opaque_tag_index(
    characters: Sequence[DecodedF2Character],
) -> _OpaqueTagIndex:
    boundaries: dict[int, _OpaqueTagBoundary] = {}
    closing_starts: dict[str, list[int]] = {}
    closing_ends: dict[str, list[int]] = {}
    index = 0
    scan_count = 0
    while index < len(characters):
        scan_count += 1
        if characters[index].text != "<":
            index += 1
            continue
        start = index
        cursor = index + 1
        closing = False
        if cursor < len(characters) and characters[cursor].text == "/":
            closing = True
            cursor += 1
            scan_count += 1
        name_start = cursor
        while cursor < len(characters):
            current = characters[cursor].text
            if current.isspace() or current in "</>":
                break
            cursor += 1
            scan_count += 1
        tag_name = "".join(
            character.text for character in characters[name_start:cursor]
        )
        if not tag_name or any(character in "</\t\r\n" for character in tag_name):
            index = start + 1
            continue
        while cursor < len(characters) and characters[cursor].text != ">":
            if characters[cursor].text == "<":
                break
            cursor += 1
            scan_count += 1
        if cursor >= len(characters) or characters[cursor].text != ">":
            index = cursor
            continue
        end = cursor + 1
        boundary = _OpaqueTagBoundary(end=end, closing=closing, name=tag_name)
        boundaries[start] = boundary
        if closing:
            closing_starts.setdefault(tag_name, []).append(start)
            closing_ends.setdefault(tag_name, []).append(end)
        index = end
    return _OpaqueTagIndex(
        boundaries_by_start=boundaries,
        closing_starts_by_name={
            tag_name: tuple(starts) for tag_name, starts in closing_starts.items()
        },
        closing_ends_by_name={
            tag_name: tuple(ends) for tag_name, ends in closing_ends.items()
        },
        scan_count=scan_count,
    )


def _find_unknown_tag_close(
    *,
    start: int,
    tag_name: str,
    opaque_tag_index: _OpaqueTagIndex,
) -> tuple[int, int] | None:
    starts = opaque_tag_index.closing_starts_by_name.get(tag_name, ())
    ends = opaque_tag_index.closing_ends_by_name.get(tag_name, ())
    candidate_index = bisect_left(starts, start)
    if candidate_index == len(starts):
        return None
    return starts[candidate_index], ends[candidate_index]


def _tokenize_characters(
    characters: tuple[DecodedF2Character, ...],
    artifact_sha256: str,
    *,
    merge_contiguous_source_slices: bool,
) -> F2PageTokens:
    tokens: list[F2Token] = []
    normalizations: list[F2NormalizationOperation] = []
    warnings: list[F2Warning] = []
    visible: list[DecodedF2Character] = []
    text_run: list[DecodedF2Character] = []
    open_tags: list[tuple[str, tuple[SourceSlice, ...]]] = []
    delimiter_index = _build_delimiter_index(characters)
    opaque_tag_index = _build_opaque_tag_index(characters)

    def flush_text_run() -> None:
        if not text_run:
            return
        text = "".join(character.text for character in text_run)
        tokens.append(
            F2Token(
                kind=F2TokenKind.TEXT,
                text=text,
                source_slices=_slice_for_characters(text_run),
                visible_text=text,
            )
        )
        text_run.clear()

    def add_warning(code: str, selected: Sequence[DecodedF2Character]) -> None:
        warnings.append(
            F2Warning(code=code, source_slices=_slice_for_characters(selected))
        )

    index = 0
    while index < len(characters):
        character = characters[index]
        next_text = characters[index + 1].text if index + 1 < len(characters) else ""
        if character.text == "[" and next_text == "*":
            note_end = delimiter_index.note_ends[index + 2]
            if (
                note_end is not None
                and index + 2 < len(characters)
                and characters[index + 2].text == "*"
            ):
                flush_text_run()
                selected = list(characters[index:note_end])
                tokens.append(
                    F2Token(
                        kind=F2TokenKind.NOTE,
                        text="".join(item.text for item in selected),
                        source_slices=_slice_for_characters(selected),
                        visible_text="",
                    )
                )
                index = note_end
                continue
            if index + 2 < len(characters) and characters[index + 2].text == "*":
                flush_text_run()
                selected = list(characters[index:])
                raw_text = "".join(item.text for item in selected)
                tokens.append(
                    F2Token(
                        kind=F2TokenKind.UNKNOWN,
                        text=raw_text,
                        source_slices=_slice_for_characters(selected),
                        visible_text=raw_text,
                    )
                )
                add_warning("unclosed_note", selected)
                visible.extend(selected)
                index = len(characters)
                continue
        marker = character.text + next_text
        marker_kind = _BLOCK_MARKERS.get(marker)
        if marker_kind is not None:
            flush_text_run()
            selected = list(characters[index : index + 2])
            tokens.append(
                F2Token(
                    kind=F2TokenKind(marker_kind),
                    text=marker,
                    source_slices=_slice_for_characters(selected),
                    visible_text="",
                )
            )
            index += 2
            continue
        if character.text == "<":
            opaque_tag = opaque_tag_index.boundaries_by_start.get(index)
            if opaque_tag is not None:
                tag_end = opaque_tag.end
                selected = list(characters[index:tag_end])
                tag_text = "".join(item.text for item in selected)
                tag = _is_inline_tag(tag_text)
                if tag is not None:
                    flush_text_run()
                    closing, tag_name = tag
                    token_kind = (
                        F2TokenKind.CLOSE_TAG if closing else F2TokenKind.OPEN_TAG
                    )
                    tokens.append(
                        F2Token(
                            kind=token_kind,
                            text=tag_text,
                            source_slices=_slice_for_characters(selected),
                            visible_text="",
                        )
                    )
                    if closing:
                        if not open_tags or open_tags[-1][0] != tag_name:
                            add_warning("mismatched_close_tag", selected)
                        else:
                            open_tags.pop()
                    else:
                        open_tags.append((tag_name, _slice_for_characters(selected)))
                    index = tag_end
                    continue
                unknown_tag = _opaque_tag_parts(tag_text)
                if unknown_tag is not None and not unknown_tag[0]:
                    flush_text_run()
                    tokens.append(
                        F2Token(
                            kind=F2TokenKind.UNKNOWN,
                            text=tag_text,
                            source_slices=_slice_for_characters(selected),
                            visible_text=tag_text,
                        )
                    )
                    add_warning("unknown_construct", selected)
                    visible.extend(selected)
                    closing_tag = _find_unknown_tag_close(
                        start=tag_end,
                        tag_name=unknown_tag[1],
                        opaque_tag_index=opaque_tag_index,
                    )
                    if closing_tag is None:
                        body = list(characters[tag_end:])
                        if body:
                            body_text = "".join(item.text for item in body)
                            tokens.append(
                                F2Token(
                                    kind=F2TokenKind.UNKNOWN,
                                    text=body_text,
                                    source_slices=_slice_for_characters(body),
                                    visible_text=body_text,
                                )
                            )
                            visible.extend(body)
                        add_warning("unclosed_unknown_tag", selected)
                        index = len(characters)
                        continue
                    closing_start, closing_end = closing_tag
                    body = list(characters[tag_end:closing_start])
                    if body:
                        body_text = "".join(item.text for item in body)
                        tokens.append(
                            F2Token(
                                kind=F2TokenKind.UNKNOWN,
                                text=body_text,
                                source_slices=_slice_for_characters(body),
                                visible_text=body_text,
                            )
                        )
                        visible.extend(body)
                    closing = list(characters[closing_start:closing_end])
                    closing_text = "".join(item.text for item in closing)
                    tokens.append(
                        F2Token(
                            kind=F2TokenKind.UNKNOWN,
                            text=closing_text,
                            source_slices=_slice_for_characters(closing),
                            visible_text=closing_text,
                        )
                    )
                    visible.extend(closing)
                    index = closing_end
                    continue
                flush_text_run()
                tokens.append(
                    F2Token(
                        kind=F2TokenKind.UNKNOWN,
                        text=tag_text,
                        source_slices=_slice_for_characters(selected),
                        visible_text=tag_text,
                    )
                )
                add_warning("unknown_construct", selected)
                visible.extend(selected)
                index = tag_end
                continue
            remaining = list(characters[index:])
            if len(remaining) > 1 and remaining[1].text.isalpha():
                flush_text_run()
                raw_text = "".join(item.text for item in remaining)
                tokens.append(
                    F2Token(
                        kind=F2TokenKind.UNKNOWN,
                        text=raw_text,
                        source_slices=_slice_for_characters(remaining),
                        visible_text=raw_text,
                    )
                )
                add_warning("invalid_construct", remaining)
                visible.extend(remaining)
                index = len(characters)
                continue
        if character.text in {"^", "_"}:
            token_kind = (
                F2TokenKind.SUPERSCRIPT
                if character.text == "^"
                else F2TokenKind.SUBSCRIPT
            )
            if next_text == "{":
                closing = delimiter_index.script_ends[index + 2]
                if closing is not None and closing > index + 3:
                    flush_text_run()
                    selected = list(characters[index:closing])
                    content = list(characters[index + 2 : closing - 1])
                    tokens.append(
                        F2Token(
                            kind=token_kind,
                            text="".join(item.text for item in selected),
                            source_slices=_slice_for_characters(selected),
                            visible_text="".join(item.text for item in content),
                        )
                    )
                    visible.extend(content)
                    index = closing
                    continue
                flush_text_run()
                selected = list(characters[index:])
                raw_text = "".join(item.text for item in selected)
                tokens.append(
                    F2Token(
                        kind=F2TokenKind.UNKNOWN,
                        text=raw_text,
                        source_slices=_slice_for_characters(selected),
                        visible_text=raw_text,
                    )
                )
                add_warning("invalid_construct", selected)
                visible.extend(selected)
                index = len(characters)
                continue
            if next_text and not next_text.isspace() and next_text not in "<>[]{}":
                flush_text_run()
                selected = list(characters[index : index + 2])
                tokens.append(
                    F2Token(
                        kind=token_kind,
                        text="".join(item.text for item in selected),
                        source_slices=_slice_for_characters(selected),
                        visible_text=next_text,
                    )
                )
                visible.append(characters[index + 1])
                index += 2
                continue
            if not next_text:
                flush_text_run()
                tokens.append(
                    F2Token(
                        kind=F2TokenKind.UNKNOWN,
                        text=character.text,
                        source_slices=(character.source_slice,),
                        visible_text=character.text,
                    )
                )
                add_warning("invalid_construct", [character])
                visible.append(character)
                index += 1
                continue
        if character.text == " " and any(tag == "g" for tag, _ in open_tags):
            flush_text_run()
            source_slices = (character.source_slice,)
            normalizations.append(
                F2NormalizationOperation(
                    kind=F2NormalizationKind.LETTER_SPACE_REMOVED,
                    source_slices=source_slices,
                    replacement_text="",
                )
            )
            tokens.append(
                F2Token(
                    kind=F2TokenKind.NORMALIZATION,
                    text=character.text,
                    source_slices=source_slices,
                    visible_text="",
                    normalization_kind=F2NormalizationKind.LETTER_SPACE_REMOVED,
                )
            )
            index += 1
            continue
        visible.append(character)
        text_run.append(character)
        index += 1
    flush_text_run()
    for _tag_name, source_slices in open_tags:
        warnings.append(F2Warning(code="unclosed_tag", source_slices=source_slices))
    visible_text, graphemes = _append_graphemes(
        visible,
        artifact_sha256,
        merge_contiguous_source_slices=merge_contiguous_source_slices,
    )
    return F2PageTokens(
        tokenizer_version=F2_TOKENIZER_VERSION,
        artifact_sha256=artifact_sha256,
        visible_text=visible_text,
        graphemes=graphemes,
        tokens=tuple(tokens),
        normalizations=tuple(normalizations),
        warnings=tuple(warnings),
        warning_codes=tuple(warning.code for warning in warnings),
        delimiter_scan_count=delimiter_index.scan_count,
        opaque_tag_scan_count=opaque_tag_index.scan_count,
    )


def tokenize_f2(page_bytes: bytes) -> F2PageTokens:
    """Tokenize one already-decoded F2 page while retaining raw byte slices."""
    artifact_sha256, characters = _direct_characters(page_bytes)
    return _tokenize_characters(
        characters,
        artifact_sha256,
        merge_contiguous_source_slices=True,
    )


def _tokenize_lexical_page(page: LexicalF2Page, artifact_sha256: str) -> F2JsonPage:
    return F2JsonPage(
        page_key=page.page_key,
        decoded_text=page.decoded_text,
        decoded_page_utf8_sha256=page.decoded_page_utf8_sha256,
        lexical_value_byte_range=page.lexical_value_byte_range,
        characters=page.characters,
        parsed=_tokenize_characters(
            page.characters,
            artifact_sha256,
            merge_contiguous_source_slices=False,
        ),
    )


def read_f2_json(artifact_bytes: bytes) -> F2JsonDocument:
    """Read full F2 JSON bytes and tokenize every page without reserialization."""
    lexical_document = read_lexical_json(artifact_bytes)
    return F2JsonDocument(
        artifact_sha256=lexical_document.artifact_sha256,
        pages=tuple(
            _tokenize_lexical_page(page, lexical_document.artifact_sha256)
            for page in lexical_document.pages
        ),
    )


def read_f2_json_page(
    artifact_bytes: bytes,
    page_key: str,
    index: LexicalF2Index,
) -> F2JsonPage:
    """Tokenize exactly one page from a lightweight lexical F2 index."""
    lexical_page = read_lexical_page(artifact_bytes, page_key, index)
    return _tokenize_lexical_page(lexical_page, index.artifact_sha256)
