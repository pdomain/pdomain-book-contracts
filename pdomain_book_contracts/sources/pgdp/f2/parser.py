"""Semantic F2 parsing into the portable typography page contract."""

from __future__ import annotations

import base64
import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pdomain_book_contracts.sources.pgdp.f2.project_rules import ProjectRuleRegistry
from pdomain_book_contracts.sources.pgdp.f2.tokens import F2TokenKind, read_f2_json_page
from pdomain_book_contracts.sources.pgdp.f2.warnings import (
    F2ParseWarning,
    warning_blocks_training,
)
from pdomain_book_contracts.sources.pgdp.offsets import read_lexical_index
from pdomain_book_contracts.typography.labels import (
    ConfidenceTier,
    KnowledgeState,
    LabelSource,
    StyleLabel,
)
from pdomain_book_contracts.typography.records import (
    ArtifactRef,
    Grapheme,
    ParserControlEvidence,
    ParserControlKind,
    ParserNormalizationEvidence,
    ParserNormalizationKind,
    ParserNoteEvidence,
    ParserNoteStatus,
    TextIdentity,
    TypographyPageRecord,
)
from pdomain_book_contracts.typography.spans import (
    SourceSlice,
    StyleSpan,
    split_graphemes,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pdomain_book_contracts.sources.pgdp.f2.tokens import (
        F2JsonPage,
        F2PageTokens,
        F2Token,
    )
    from pdomain_book_contracts.sources.pgdp.offsets import LexicalF2Index

_STANDARD_TAG_LABELS = {
    "i": StyleLabel.ITALIC,
    "b": StyleLabel.BOLD,
    "sc": StyleLabel.SMALL_CAPS,
    "g": StyleLabel.LETTER_SPACED,
}
_STYLE_TAGS = frozenset({*_STANDARD_TAG_LABELS, "f", "u"})
_BLOCK_CONTEXT = {"/*": "poetry_block", "/#": "display_block"}
_BLOCK_OPEN_BY_CLOSE = {"*/": "/*", "#/": "/#"}


@dataclass
class _ActiveStyle:
    tag_name: str
    raw_text: str
    start: int
    source_slices: list[SourceSlice] = field(default_factory=list)


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _style_for_tag(
    tag_name: str,
    *,
    project_id: str | None,
    project_comments_bytes: bytes | None,
    rule_registry: ProjectRuleRegistry,
) -> tuple[StyleLabel, KnowledgeState, ConfidenceTier, str | None, tuple[str, ...]]:
    standard_label = _STANDARD_TAG_LABELS.get(tag_name)
    if standard_label is not None:
        warnings: tuple[str, ...] = ()
        if tag_name == "sc":
            warnings = (F2ParseWarning.SMALL_CAPS_CASE_NORMALIZED,)
        return (
            standard_label,
            KnowledgeState.POSITIVE,
            ConfidenceTier.GOLD,
            None,
            warnings,
        )
    rule = rule_registry.resolve(project_id, project_comments_bytes, tag_name)
    if rule is not None:
        return (
            rule.label,
            KnowledgeState.POSITIVE,
            ConfidenceTier.GOLD,
            rule.rule_ref,
            (),
        )
    if tag_name == "f":
        return (
            StyleLabel.FONT_OTHER_REVIEWED,
            KnowledgeState.UNKNOWN,
            ConfidenceTier.QUARANTINE,
            None,
            (F2ParseWarning.AMBIGUOUS_FONT_CHANGE,),
        )
    return (
        StyleLabel.UNDERLINE,
        KnowledgeState.UNKNOWN,
        ConfidenceTier.QUARANTINE,
        None,
        (F2ParseWarning.UNAPPROVED_UNDERLINE,),
    )


def _span_from_active(
    active: _ActiveStyle,
    *,
    end: int,
    project_id: str | None,
    project_comments_bytes: bytes | None,
    rule_registry: ProjectRuleRegistry,
    extra_warnings: Sequence[str] = (),
) -> StyleSpan | None:
    if active.start == end:
        return None
    label, state, tier, rule_ref, warnings = _style_for_tag(
        active.tag_name,
        project_id=project_id,
        project_comments_bytes=project_comments_bytes,
        rule_registry=rule_registry,
    )
    return StyleSpan(
        label=label,
        start=active.start,
        end=end,
        state=state,
        label_source=LabelSource.F2,
        confidence_tier=tier,
        source_slices=tuple(active.source_slices),
        rule_ref=rule_ref,
        semantic_reason=None,
        warnings=(*warnings, *extra_warnings),
    )


def _tag_name(token: F2Token) -> str:
    text = token.text
    if text.startswith("</"):
        return text[2:-1]
    return text[1:-1]


def _project_comments_artifact(
    *,
    project_comments_bytes: bytes | None,
    supplied_artifact: ArtifactRef | None,
) -> ArtifactRef | None:
    if project_comments_bytes is None:
        if supplied_artifact is not None:
            msg = "project_comments_artifact requires project_comments_bytes"
            raise ValueError(msg)
        return None
    comments_hash = hashlib.sha256(project_comments_bytes).hexdigest()
    if supplied_artifact is None:
        msg = "project_comments_artifact is required with project_comments_bytes"
        raise ValueError(msg)
    if supplied_artifact.sha256 != comments_hash:
        msg = "project_comments_artifact hash does not match project_comments_bytes"
        raise ValueError(msg)
    return supplied_artifact


def _parse_tokens(
    parsed: F2PageTokens,
    *,
    project_id: str | None,
    project_comments_bytes: bytes | None,
    rule_registry: ProjectRuleRegistry,
) -> tuple[
    tuple[StyleSpan, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[ParserNoteEvidence, ...],
    tuple[ParserNormalizationEvidence, ...],
    tuple[ParserControlEvidence, ...],
]:
    active: list[_ActiveStyle] = []
    style_spans: list[StyleSpan] = []
    warnings = list(parsed.warning_codes)
    structural_context: list[str] = []
    parser_notes: list[ParserNoteEvidence] = []
    normalization_operations: list[ParserNormalizationEvidence] = []
    parser_controls: list[ParserControlEvidence] = []
    grapheme_index = 0
    active_blocks: list[str] = []

    for token in parsed.tokens:
        for open_style in active:
            open_style.source_slices.extend(token.source_slices)
        if token.kind is F2TokenKind.OPEN_TAG:
            tag_name = _tag_name(token)
            if tag_name in _STYLE_TAGS:
                active.append(
                    _ActiveStyle(
                        tag_name=tag_name,
                        raw_text=token.text,
                        start=grapheme_index,
                        source_slices=list(token.source_slices),
                    )
                )
            continue
        if token.kind is F2TokenKind.CLOSE_TAG:
            tag_name = _tag_name(token)
            if tag_name in _STYLE_TAGS and active and active[-1].tag_name == tag_name:
                closed = active.pop()
                span = _span_from_active(
                    closed,
                    end=grapheme_index,
                    project_id=project_id,
                    project_comments_bytes=project_comments_bytes,
                    rule_registry=rule_registry,
                )
                if span is not None:
                    style_spans.append(span)
                    for warning in span.warnings:
                        _append_unique(warnings, warning)
            continue
        if token.kind is F2TokenKind.NOTE:
            _append_unique(warnings, F2ParseWarning.NOTE_QUARANTINE)
            content = token.text[3:-1]
            parser_notes.append(
                ParserNoteEvidence(
                    raw_text=token.text,
                    page_review_content=content,
                    question_status=(
                        ParserNoteStatus.QUESTION
                        if "?" in content
                        else ParserNoteStatus.COMMENT
                    ),
                    source_slices=token.source_slices,
                )
            )
            continue
        if token.kind is F2TokenKind.UNKNOWN and token.text.startswith("[**"):
            _append_unique(warnings, F2ParseWarning.NOTE_QUARANTINE)
            content = token.text[3:-1] if token.text.endswith("]") else token.text[3:]
            parser_notes.append(
                ParserNoteEvidence(
                    raw_text=token.text,
                    page_review_content=content,
                    question_status=(
                        ParserNoteStatus.QUESTION
                        if "?" in content
                        else ParserNoteStatus.COMMENT
                    ),
                    source_slices=token.source_slices,
                )
            )
            continue
        if token.kind is F2TokenKind.NORMALIZATION:
            _append_unique(warnings, F2ParseWarning.LETTER_SPACE_REMOVED)
            normalization_operations.append(
                ParserNormalizationEvidence(
                    kind=ParserNormalizationKind.LETTER_SPACE_REMOVED,
                    source_slices=token.source_slices,
                    replacement_text=token.visible_text,
                    grapheme_indices=(),
                )
            )
            continue
        if token.kind is F2TokenKind.SUPERSCRIPT or token.kind is F2TokenKind.SUBSCRIPT:
            width = len(split_graphemes(token.visible_text))
            if width > 0:
                label = (
                    StyleLabel.SUPERSCRIPT
                    if token.kind is F2TokenKind.SUPERSCRIPT
                    else StyleLabel.SUBSCRIPT
                )
                style_spans.append(
                    StyleSpan(
                        label=label,
                        start=grapheme_index,
                        end=grapheme_index + width,
                        state=KnowledgeState.POSITIVE,
                        label_source=LabelSource.F2,
                        confidence_tier=ConfidenceTier.GOLD,
                        source_slices=token.source_slices,
                        rule_ref=None,
                        semantic_reason=None,
                        warnings=(),
                    )
                )
            grapheme_index += width
            continue
        if token.kind is F2TokenKind.BLOCK_OPEN:
            context = _BLOCK_CONTEXT[token.text]
            active_blocks.append(token.text)
            _append_unique(structural_context, context)
            continue
        if token.kind is F2TokenKind.BLOCK_CLOSE:
            expected_open = _BLOCK_OPEN_BY_CLOSE[token.text]
            if not active_blocks:
                _append_unique(warnings, F2ParseWarning.UNMATCHED_BLOCK)
            elif active_blocks[-1] != expected_open:
                _append_unique(warnings, F2ParseWarning.CROSSED_BLOCK)
            else:
                active_blocks.pop()
            continue
        grapheme_index += len(split_graphemes(token.visible_text))

    while active:
        unclosed = active.pop()
        _label, _state, _tier, _rule_ref, style_warnings = _style_for_tag(
            unclosed.tag_name,
            project_id=project_id,
            project_comments_bytes=project_comments_bytes,
            rule_registry=rule_registry,
        )
        parser_controls.append(
            ParserControlEvidence(
                kind=ParserControlKind.UNCLOSED_STYLE_TAG,
                tag_name=unclosed.tag_name,
                raw_text=unclosed.raw_text,
                source_slices=tuple(unclosed.source_slices),
            )
        )
        for warning in style_warnings:
            _append_unique(warnings, warning)
        _append_unique(warnings, F2ParseWarning.UNCLOSED_TAG)
    if active_blocks:
        _append_unique(warnings, F2ParseWarning.UNCLOSED_BLOCK)
    for span in style_spans:
        if span.label is not StyleLabel.SMALL_CAPS:
            continue
        for grapheme_index in range(span.start, span.end):
            grapheme = parsed.graphemes[grapheme_index]
            normalized_text = grapheme.text.casefold()
            if normalized_text == grapheme.text:
                continue
            normalization_operations.append(
                ParserNormalizationEvidence(
                    kind=ParserNormalizationKind.SMALL_CAPS_CASE_NORMALIZED,
                    source_slices=grapheme.source_slices,
                    replacement_text=normalized_text,
                    grapheme_indices=(grapheme_index,),
                )
            )
    return (
        tuple(style_spans),
        tuple(warnings),
        tuple(structural_context),
        tuple(parser_notes),
        tuple(normalization_operations),
        tuple(parser_controls),
    )


def _visible_page_content(parsed: F2PageTokens) -> tuple[str, tuple[Grapheme, ...]]:
    source_grapheme_index = 0
    visible_graphemes: list[Grapheme] = []
    for token in parsed.tokens:
        width = len(split_graphemes(token.visible_text))
        token_graphemes = parsed.graphemes[
            source_grapheme_index : source_grapheme_index + width
        ]
        source_grapheme_index += width
        if token.kind is F2TokenKind.UNKNOWN and token.text.startswith("[**"):
            continue
        for source_grapheme in token_graphemes:
            visible_graphemes.append(
                Grapheme(
                    index=len(visible_graphemes),
                    text=source_grapheme.text,
                    source_slices=source_grapheme.source_slices,
                    normalized_from=source_grapheme.normalized_from,
                )
            )
    if source_grapheme_index != len(parsed.graphemes):
        msg = "F2 tokens did not account for every parsed grapheme"
        raise ValueError(msg)
    visible_text = "".join(grapheme.text for grapheme in visible_graphemes)
    return visible_text, tuple(visible_graphemes)


def _training_eligible(warnings: Sequence[str]) -> bool:
    return not any(warning_blocks_training(code) for code in warnings)


# ``read_lexical_index`` and ``read_f2_json_page`` are named here deliberately.
# They are imported rather than defined, but ``F2Parser.parse_page`` calls them
# through this module's globals, so they are part of what this module exposes.
__all__ = ["F2Parser", "read_f2_json_page", "read_lexical_index"]


class F2Parser:
    """Build page-local typography records from lossless PGDP F2 tokens."""

    def __init__(
        self,
        rule_registry: ProjectRuleRegistry | None = None,
        *,
        document_cache_size: int = 8,
    ) -> None:
        if document_cache_size < 1:
            msg = "document_cache_size must be at least one"
            raise ValueError(msg)
        self._rule_registry = rule_registry or ProjectRuleRegistry()
        self._document_cache_size = document_cache_size
        self._index_cache: OrderedDict[str, LexicalF2Index] = OrderedDict()

    def _read_index(self, artifact_bytes: bytes) -> LexicalF2Index:
        artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
        cached = self._index_cache.get(artifact_sha256)
        if cached is not None:
            self._index_cache.move_to_end(artifact_sha256)
            return cached
        index = read_lexical_index(artifact_bytes)
        self._index_cache[artifact_sha256] = index
        if len(self._index_cache) > self._document_cache_size:
            self._index_cache.popitem(last=False)
        return index

    def parse_page(
        self,
        *,
        identity: TextIdentity,
        guideline_version: str,
        f2_artifact_bytes: bytes,
        page_key: str,
        project_comments_bytes: bytes | None = None,
        project_comments_artifact: ArtifactRef | None = None,
    ) -> TypographyPageRecord:
        """Parse one F2 page without invoking the legacy PGDP result processor."""
        if not guideline_version:
            msg = "guideline_version must not be empty"
            raise ValueError(msg)
        comments_artifact = _project_comments_artifact(
            project_comments_bytes=project_comments_bytes,
            supplied_artifact=project_comments_artifact,
        )
        index = self._read_index(f2_artifact_bytes)
        page = read_f2_json_page(f2_artifact_bytes, page_key, index)
        return self._record_from_json_page(
            page=page,
            artifact_bytes=f2_artifact_bytes,
            artifact_sha256=index.artifact_sha256,
            identity=identity,
            guideline_version=guideline_version,
            project_comments_bytes=project_comments_bytes,
            project_comments_artifact=comments_artifact,
        )

    def _record_from_json_page(
        self,
        *,
        page: F2JsonPage,
        artifact_bytes: bytes,
        artifact_sha256: str,
        identity: TextIdentity,
        guideline_version: str,
        project_comments_bytes: bytes | None,
        project_comments_artifact: ArtifactRef | None,
    ) -> TypographyPageRecord:
        (
            style_spans,
            warnings,
            structural_context,
            parser_notes,
            normalization_operations,
            parser_controls,
        ) = _parse_tokens(
            page.parsed,
            project_id=identity.project_id,
            project_comments_bytes=project_comments_bytes,
            rule_registry=self._rule_registry,
        )
        parsed_text, graphemes = _visible_page_content(page.parsed)
        return TypographyPageRecord(
            schema_version="1.0",
            identity=identity,
            original_f2_artifact_base64=base64.b64encode(artifact_bytes).decode(
                "ascii"
            ),
            original_f2_artifact_sha256=artifact_sha256,
            f2_page_key=page.page_key,
            f2_page_value_lexical_byte_range=page.lexical_value_byte_range,
            f2_decoded_page_utf8_sha256=page.decoded_page_utf8_sha256,
            parsed_text=parsed_text,
            graphemes=graphemes,
            ocr_tokens=(),
            style_spans=style_spans,
            structural_context=structural_context,
            parser_warnings=warnings,
            parser_notes=parser_notes,
            normalization_operations=normalization_operations,
            parser_controls=parser_controls,
            training_eligible=_training_eligible(warnings),
            alignments=(),
            project_comments_artifact=project_comments_artifact,
            guideline_version=guideline_version,
        )
