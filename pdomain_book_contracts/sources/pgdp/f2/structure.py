"""F2 layout evidence derived from lossless page tokens."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from pdomain_book_contracts.layout.text_hints import LayoutTextHint, LayoutTextLine
from pdomain_book_contracts.sources.pgdp.f2.tokens import F2PageTokens, F2TokenKind

_TAG_NAME = re.compile(r"^</?\s*([^\s>/]+)")
_ATTRIBUTE = re.compile(
    r"""\s+([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?"""
)
_HintKind = Literal["poetry", "blockquote", "table_candidate", "column_flow"]
_BLOCK_OPEN: dict[str, _HintKind] = {"/*": "poetry", "/#": "blockquote"}
_BLOCK_CLOSE = {"*/": "/*", "#/": "/#"}
_STRUCTURAL_CHILDREN = {
    "table": frozenset({"tr"}),
    "tr": frozenset({"td", "th"}),
    "td": frozenset({"table"}),
    "th": frozenset({"table"}),
}


@dataclass
class _OpenBlock:
    kind: _HintKind
    marker: str
    grapheme_start: int


@dataclass
class _Table:
    attributes: list[tuple[str, str]]
    grapheme_start: int
    rows: list[tuple[str, ...]] = field(default_factory=list)
    cells: list[str] = field(default_factory=list)
    cell_start: int | None = None
    row_open: bool = False
    nested_depth: int = 1
    tag_stack: list[str] = field(default_factory=lambda: ["table"])


def _grapheme_boundaries(parsed: F2PageTokens) -> dict[int, int]:
    boundaries = {0: 0}
    character_offset = 0
    for index, grapheme in enumerate(parsed.graphemes, start=1):
        character_offset += len(grapheme.text)
        boundaries[character_offset] = index
    if character_offset != len(parsed.visible_text):
        msg = "F2 graphemes do not reconstruct visible text"
        raise ValueError(msg)
    return boundaries


def _tag_name(text: str) -> str | None:
    match = _TAG_NAME.match(text)
    if match is None:
        return None
    return match.group(1)


def _attributes(text: str) -> tuple[tuple[str, str], ...]:
    tag_end = text.rfind(">")
    body = text[:tag_end] if tag_end >= 0 else text
    attributes: list[tuple[str, str]] = []
    for match in _ATTRIBUTE.finditer(body):
        key = match.group(1)
        if key.startswith("/"):
            continue
        value = next(
            (group for group in match.groups()[1:] if group is not None),
            "",
        )
        attributes.append((key, value))
    return tuple(attributes)


def _structural_attributes(text: str, tag_name: str) -> tuple[tuple[str, str], ...]:
    return tuple((f"{tag_name}.{key}", value) for key, value in _attributes(text))


def _source_text(parsed: F2PageTokens, start: int, end: int) -> str:
    return "".join(grapheme.text for grapheme in parsed.graphemes[start:end])


def _lines(text: str) -> tuple[LayoutTextLine, ...]:
    lines: list[LayoutTextLine] = []
    stanza_index = 0
    for line in text.splitlines():
        stripped = line.lstrip(" \t")
        if not stripped:
            stanza_index += 1
            continue
        prefix = line[: len(line) - len(stripped)]
        indent_hint = (
            f"{len(prefix)} spaces"
            if prefix and set(prefix) == {" "}
            else prefix or None
        )
        lines.append(
            LayoutTextLine(
                text=stripped,
                stanza_index=stanza_index,
                indent_hint=indent_hint,
            )
        )
    return tuple(lines)


def _close_cell(table: _Table, parsed: F2PageTokens, grapheme_index: int) -> None:
    if table.cell_start is None:
        return
    table.cells.append(_source_text(parsed, table.cell_start, grapheme_index))
    table.cell_start = None


def _close_row(table: _Table, parsed: F2PageTokens, grapheme_index: int) -> None:
    _close_cell(table, parsed, grapheme_index)
    if table.row_open:
        table.rows.append(tuple(table.cells))
    table.cells.clear()
    table.row_open = False


def _allows_structural_child(table: _Table, tag_name: str) -> bool:
    return tag_name in _STRUCTURAL_CHILDREN.get(table.tag_stack[-1], ())


def layout_hints_from_tokens(
    parsed: F2PageTokens, *, source_ref: str
) -> tuple[LayoutTextHint, ...]:
    """Produce source-relative layout hints without resolving scan geometry."""
    hints: list[LayoutTextHint] = []
    blocks: list[_OpenBlock] = []
    table: _Table | None = None
    grapheme_boundaries = _grapheme_boundaries(parsed)
    visible_character_offset = 0
    for token in parsed.tokens:
        grapheme_index = grapheme_boundaries.get(visible_character_offset)
        if token.kind is F2TokenKind.BLOCK_OPEN:
            kind = _BLOCK_OPEN.get(token.text)
            if kind is not None and grapheme_index is not None:
                blocks.append(
                    _OpenBlock(
                        kind=kind,
                        marker=token.text,
                        grapheme_start=grapheme_index,
                    )
                )
            elif kind is not None:
                blocks.clear()
            continue
        if token.kind is F2TokenKind.BLOCK_CLOSE:
            expected = _BLOCK_CLOSE.get(token.text)
            if grapheme_index is None:
                blocks.clear()
                continue
            if expected is not None and blocks and blocks[-1].marker == expected:
                block = blocks.pop()
                text = _source_text(parsed, block.grapheme_start, grapheme_index)
                if text:
                    hints.append(
                        LayoutTextHint(
                            kind=block.kind,
                            source="f2",
                            text=text,
                            lines=_lines(text),
                            source_ref=source_ref,
                            grapheme_range=(block.grapheme_start, grapheme_index),
                        )
                    )
            elif expected is not None:
                blocks.clear()
            continue
        if token.kind in {F2TokenKind.STRUCTURAL_OPEN, F2TokenKind.STRUCTURAL_CLOSE}:
            tag_name = _tag_name(token.text)
            if tag_name is None or grapheme_index is None:
                continue
            if token.kind is F2TokenKind.STRUCTURAL_OPEN:
                if tag_name == "table":
                    if table is None:
                        table = _Table(list(_attributes(token.text)), grapheme_index)
                    elif not _allows_structural_child(table, tag_name):
                        table = None
                    else:
                        table.tag_stack.append(tag_name)
                        table.nested_depth += 1
                        table.attributes.extend(
                            _structural_attributes(token.text, "nested_table")
                        )
                elif table is not None:
                    if not _allows_structural_child(table, tag_name):
                        table = None
                        continue
                    table.tag_stack.append(tag_name)
                    attribute_tag = (
                        tag_name if table.nested_depth == 1 else f"nested_{tag_name}"
                    )
                    table.attributes.extend(
                        _structural_attributes(token.text, attribute_tag)
                    )
                    if table.nested_depth == 1:
                        if tag_name == "tr":
                            _close_row(table, parsed, grapheme_index)
                            table.row_open = True
                        elif tag_name in {"td", "th"}:
                            _close_cell(table, parsed, grapheme_index)
                            if not table.row_open:
                                table.row_open = True
                            table.cell_start = grapheme_index
                continue
            if table is None:
                continue
            if table.tag_stack[-1] != tag_name:
                table = None
                continue
            if tag_name == "table":
                table.tag_stack.pop()
                table.nested_depth -= 1
                if table.nested_depth == 0:
                    _close_row(table, parsed, grapheme_index)
                    text = _source_text(parsed, table.grapheme_start, grapheme_index)
                    if text:
                        hints.append(
                            LayoutTextHint(
                                kind="table_candidate",
                                source="f2",
                                text=text,
                                lines=_lines(text),
                                source_ref=source_ref,
                                grapheme_range=(table.grapheme_start, grapheme_index),
                                attributes=tuple(table.attributes),
                                table_rows=tuple(table.rows),
                            )
                        )
                    table = None
            else:
                if table.nested_depth == 1:
                    if tag_name in {"td", "th"}:
                        _close_cell(table, parsed, grapheme_index)
                    elif tag_name == "tr":
                        _close_row(table, parsed, grapheme_index)
                table.tag_stack.pop()
            continue
        visible_character_offset += len(token.visible_text)
    return tuple(hints)
