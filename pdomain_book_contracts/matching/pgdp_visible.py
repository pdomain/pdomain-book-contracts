"""Visible PGDP and OCR adapters preserving physical words and raw source slices."""

from __future__ import annotations

import math
from typing import Annotated, Self

from pydantic import Field, model_validator

from pdomain_book_contracts.matching.models import (
    ArtifactRange,
    MatchDocument,
    MatchLine,
    MatchPage,
    MatchToken,
)
from pdomain_book_contracts.sources.pgdp.f2.tokens import F2PageTokens, tokenize_f2
from pdomain_book_contracts.typography.spans import (
    CanonicalModel,
    SourceSlice,
    split_graphemes,
)

_Index = Annotated[int, Field(strict=True, ge=0)]
_Identifier = Annotated[str, Field(strict=True, min_length=1)]


class PgdpSourceWord(CanonicalModel):
    """An existing stored word identity linked by original artifact slices."""

    word_id: _Identifier
    text: str
    source_slices: tuple[SourceSlice, ...]

    @model_validator(mode="after")
    def _require_slices(self) -> Self:
        if not self.source_slices:
            raise ValueError("stored source words require original source_slices")
        return self


class PgdpTokenLookup(CanonicalModel):
    """Visible-token location and explicitly supplied persisted word identities."""

    token_id: _Identifier
    visible_grapheme_range: tuple[_Index, _Index]
    source_word_ids: tuple[_Identifier, ...] = ()

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        if self.visible_grapheme_range[0] >= self.visible_grapheme_range[1]:
            raise ValueError("visible_grapheme_range must be nonempty and ordered")
        return self


class PgdpOcrWord(CanonicalModel):
    """One immutable supplied OCR word, line identity, and optional box snapshot."""

    token_id: _Identifier
    text: _Identifier
    line_id: _Identifier
    box: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def _validate_box(self) -> Self:
        if self.box is not None and (
            not all(math.isfinite(v) for v in self.box)
            or self.box[0] > self.box[2]
            or self.box[1] > self.box[3]
        ):
            raise ValueError("OCR box must be finite ordered left/top/right/bottom")
        return self


class PgdpVisibleDocument(CanonicalModel):
    """Matching text with raw-source lookup or unchanged OCR word snapshots."""

    document: MatchDocument
    visible_text: str
    token_lookup: tuple[PgdpTokenLookup, ...]
    ocr_words: tuple[PgdpOcrWord, ...] = ()

    @model_validator(mode="after")
    def _validate_lookup(self) -> Self:
        tokens = tuple(
            t
            for page in self.document.pages
            for line in page.lines
            for t in line.tokens
        )
        if tuple(item.token_id for item in self.token_lookup) != tuple(
            t.token_id for t in tokens
        ):
            raise ValueError("token lookup must cover the document in physical order")
        graphemes = split_graphemes(self.visible_text)
        for item, token in zip(self.token_lookup, tokens, strict=True):
            start, end = item.visible_grapheme_range
            if end > len(graphemes) or "".join(graphemes[start:end]) != token.text:
                raise ValueError(
                    "token lookup range must reproduce its visible token text"
                )
        if self.ocr_words and tuple(
            (w.token_id, w.text) for w in self.ocr_words
        ) != tuple((t.token_id, t.text) for t in tokens):
            raise ValueError(
                "OCR word snapshots must match unchanged document order and text"
            )
        return self


def _overlaps(left: SourceSlice, right: SourceSlice) -> bool:
    return (
        left.artifact_sha256 == right.artifact_sha256
        and left.byte_start < right.byte_end
        and right.byte_start < left.byte_end
    )


def match_document_from_pgdp_tokens(
    parsed: F2PageTokens,
    *,
    document_id: str,
    page_id: str,
    artifact_id: str,
    source_words: tuple[PgdpSourceWord, ...] = (),
) -> PgdpVisibleDocument:
    """Adapt parsed visible graphemes using actual lexical source byte evidence."""
    ids = tuple(word.word_id for word in source_words)
    if len(set(ids)) != len(ids):
        raise ValueError("source_words contains duplicate stored word IDs")
    tokens: list[MatchToken] = []
    lines: list[MatchLine] = []
    lookups: list[PgdpTokenLookup] = []
    selected: list[int] = []
    line_index = 0

    def flush_token() -> None:
        if not selected:
            return
        graphemes = tuple(parsed.graphemes[i] for i in selected)
        token_id = f"{document_id}:{page_id}:g{selected[0]}-{selected[-1] + 1}"
        source_slices = tuple(s for g in graphemes for s in g.source_slices)
        tokens.append(
            MatchToken(
                token_id=token_id,
                text="".join(g.text for g in graphemes),
                artifact_ranges=tuple(
                    ArtifactRange(
                        artifact_id=artifact_id,
                        artifact_sha256=s.artifact_sha256,
                        byte_start=s.byte_start,
                        byte_end=s.byte_end,
                        grapheme_start=g.index,
                        grapheme_end=g.index + 1,
                    )
                    for g in graphemes
                    for s in g.source_slices
                ),
            )
        )
        lookups.append(
            PgdpTokenLookup(
                token_id=token_id,
                visible_grapheme_range=(selected[0], selected[-1] + 1),
                source_word_ids=tuple(
                    w.word_id
                    for w in source_words
                    if any(
                        _overlaps(s, original)
                        for s in source_slices
                        for original in w.source_slices
                    )
                ),
            )
        )
        selected.clear()

    def flush_line() -> None:
        nonlocal line_index
        flush_token()
        if tokens:
            lines.append(
                MatchLine(
                    line_id=f"{document_id}:{page_id}:line{line_index}",
                    tokens=tuple(tokens),
                )
            )
            tokens.clear()
        line_index += 1

    for grapheme in parsed.graphemes:
        if grapheme.text.isspace():
            flush_token()
            if "\n" in grapheme.text or "\r" in grapheme.text:
                flush_line()
        else:
            selected.append(grapheme.index)
    flush_line()
    return PgdpVisibleDocument(
        document=MatchDocument(
            document_id=document_id,
            pages=(MatchPage(page_id=page_id, lines=tuple(lines)),),
            warnings=parsed.warning_codes,
        ),
        visible_text=parsed.visible_text,
        token_lookup=tuple(lookups),
    )


def match_document_from_pgdp_text(
    data: bytes,
    *,
    document_id: str,
    page_id: str,
    artifact_id: str,
    source_words: tuple[PgdpSourceWord, ...] = (),
) -> PgdpVisibleDocument:
    """Parse F2/P3 controls before constructing a visible matching document."""
    return match_document_from_pgdp_tokens(
        tokenize_f2(data),
        document_id=document_id,
        page_id=page_id,
        artifact_id=artifact_id,
        source_words=source_words,
    )


def match_document_from_ocr_words(
    words: tuple[PgdpOcrWord, ...],
    *,
    document_id: str,
    page_id: str,
) -> PgdpVisibleDocument:
    """Keep supplied OCR word IDs, boxes, order, and contiguous line groups."""
    lines: list[MatchLine] = []
    tokens: list[MatchToken] = []
    current_line: str | None = None
    lookups: list[PgdpTokenLookup] = []
    visible_parts: list[str] = []
    offset = 0
    for word in words:
        if current_line != word.line_id:
            if tokens and current_line is not None:
                lines.append(MatchLine(line_id=current_line, tokens=tuple(tokens)))
                tokens.clear()
            current_line = word.line_id
        if visible_parts:
            visible_parts.append(" ")
            offset += 1
        width = len(split_graphemes(word.text))
        lookups.append(
            PgdpTokenLookup(
                token_id=word.token_id, visible_grapheme_range=(offset, offset + width)
            )
        )
        tokens.append(MatchToken(token_id=word.token_id, text=word.text))
        visible_parts.append(word.text)
        offset += width
    if tokens and current_line is not None:
        lines.append(MatchLine(line_id=current_line, tokens=tuple(tokens)))
    return PgdpVisibleDocument(
        document=MatchDocument(
            document_id=document_id,
            pages=(MatchPage(page_id=page_id, lines=tuple(lines)),),
        ),
        visible_text="".join(visible_parts),
        token_lookup=tuple(lookups),
        ocr_words=words,
    )
