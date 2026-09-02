from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import json
import math
import string
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal, Self, cast, override

from pydantic import Field, field_serializer, field_validator, model_validator
from pydantic_core import PydanticCustomError

from pdomain_book_tools.geometry.bounding_box import BoundingBox
from pdomain_book_tools.typography.exchange import ArtifactReference
from pdomain_book_tools.typography.normalization import ComparisonOperation
from pdomain_book_tools.typography.spans import (
    CanonicalModel,
    SourceSlice,
    StyleSpan,
    split_graphemes,
)

_StrictIndex = Annotated[int, Field(strict=True)]
_Probability = Annotated[float, Field(ge=0.0, le=1.0)]
TYPOGRAPHY_PAGE_RECORD_LEGACY_SCHEMA_VERSION: Literal["1.0"] = "1.0"
TYPOGRAPHY_PAGE_RECORD_EXTERNAL_F2_SCHEMA_VERSION: Literal["1.1"] = "1.1"


def _validate_sha256(value: str, field_name: str) -> str:
    if len(value) != 64 or any(char not in string.hexdigits for char in value):
        msg = f"{field_name} must be a 64-character hexadecimal SHA-256"
        raise ValueError(msg)
    return value.lower()


def _validate_half_open_range(value: tuple[int, int], field_name: str) -> None:
    start, end = value
    if start < 0 or start >= end:
        msg = f"{field_name} must be a nonempty half-open range"
        raise ValueError(msg)


def _freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return _freeze_mapping(cast("Mapping[str, object]", value))
    if isinstance(value, (list, tuple)):
        items = cast("list[object] | tuple[object, ...]", value)
        return tuple(_freeze_json(item) for item in items)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    msg = f"unsupported alignment alternative value: {type(value).__name__}"
    raise ValueError(msg)


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(
        {str(key): _freeze_json(item) for key, item in value.items()}
    )


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return _thaw_mapping(cast("Mapping[str, object]", value))
    if isinstance(value, tuple):
        items = cast("tuple[object, ...]", value)
        return [_thaw_json(item) for item in items]
    return value


def _thaw_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return {str(key): _thaw_json(item) for key, item in value.items()}


def _model_input(value: object) -> object:
    if isinstance(value, CanonicalModel):
        return value.model_dump(mode="json", warnings="none")
    if isinstance(value, Mapping):
        mapping = cast("Mapping[object, object]", value)
        return {str(key): _model_input(item) for key, item in mapping.items()}
    if isinstance(value, (list, tuple)):
        items = cast("list[object] | tuple[object, ...]", value)
        return [_model_input(item) for item in items]
    return value


def _parse_json_object_member_ranges(
    artifact_bytes: bytes,
) -> tuple[dict[str, object], dict[str, tuple[int, int]]]:
    text = artifact_bytes.decode("utf-8")
    decoder = json.JSONDecoder()
    position = 0
    byte_offsets = [0]
    for character in text:
        byte_offsets.append(byte_offsets[-1] + len(character.encode("utf-8")))

    def skip_whitespace(index: int) -> int:
        while index < len(text) and text[index].isspace():
            index += 1
        return index

    position = skip_whitespace(position)
    if position >= len(text) or text[position] != "{":
        msg = "F2 artifact must be a JSON object"
        raise ValueError(msg)
    position += 1
    members: dict[str, object] = {}
    ranges: dict[str, tuple[int, int]] = {}
    position = skip_whitespace(position)
    while position < len(text) and text[position] != "}":
        key_value, position = decoder.raw_decode(text, position)
        if not isinstance(key_value, str):
            msg = "F2 page keys must be JSON strings"
            raise TypeError(msg)
        if key_value in members:
            msg = f"F2 artifact contains duplicate page key {key_value!r}"
            raise ValueError(msg)
        position = skip_whitespace(position)
        if position >= len(text) or text[position] != ":":
            msg = "F2 page key must be followed by a value"
            raise ValueError(msg)
        value_start = skip_whitespace(position + 1)
        member_value, value_end = decoder.raw_decode(text, value_start)
        members[key_value] = member_value
        ranges[key_value] = (byte_offsets[value_start], byte_offsets[value_end])
        position = skip_whitespace(value_end)
        if position < len(text) and text[position] == ",":
            position = skip_whitespace(position + 1)
            if position >= len(text) or text[position] == "}":
                msg = "F2 artifact must not contain a trailing comma"
                raise ValueError(msg)
            continue
        break
    if position >= len(text) or text[position] != "}":
        msg = "F2 artifact must contain a valid JSON object"
        raise ValueError(msg)
    if skip_whitespace(position + 1) != len(text):
        msg = "F2 artifact must not contain trailing data"
        raise ValueError(msg)
    return members, ranges


class ArtifactSource(StrEnum):
    """Artifact origins supported by the typography record contract."""

    PGDP_F2 = "pgdp_f2"
    GUTENBERG = "gutenberg"
    STANDARD_EBOOKS = "standard_ebooks"
    HUMAN = "human"
    SYNTHETIC = "synthetic"


class SourceCoordinateSpace(StrEnum):
    """Coordinate spaces used on the source side of an alignment."""

    RAW_BYTES = "raw_bytes"
    SOURCE_GRAPHEMES = "source_graphemes"
    SOURCE_PAGES = "source_pages"


class TargetCoordinateSpace(StrEnum):
    """Coordinate spaces used on the target side of an alignment."""

    OCR_GRAPHEMES = "ocr_graphemes"
    OCR_TOKENS = "ocr_tokens"
    TARGET_PAGES = "target_pages"


class ArtifactRef(CanonicalModel):
    """Immutable identity and retrieval metadata for one artifact."""

    source: ArtifactSource
    source_url: str | None
    local_path: str
    retrieved_at: dt.datetime
    sha256: str
    version: str
    license_ref: str | None

    @field_validator("sha256")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        return _validate_sha256(value, "sha256")

    @field_validator("version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if not value:
            msg = "version must not be empty"
            raise ValueError(msg)
        return value

    @field_validator("retrieved_at")
    @classmethod
    def _validate_retrieved_at(cls, value: dt.datetime) -> dt.datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            msg = "retrieved_at must include a timezone"
            raise ValueError(msg)
        return value


class TextIdentity(CanonicalModel):
    """Stable work, edition, book, project, and page identity."""

    work_id: str
    edition_id: str
    book_id: str
    project_id: str | None
    pg_ebook_id: _StrictIndex | None
    se_repository: str | None
    page_id: str
    image_artifact: ArtifactRef
    text_artifacts: tuple[ArtifactRef, ...]


class Grapheme(CanonicalModel):
    """One visible grapheme and its exact source byte slices."""

    index: _StrictIndex
    text: str
    source_slices: tuple[SourceSlice, ...]
    normalized_from: str | None

    @field_validator("text")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        if len(split_graphemes(value)) != 1:
            msg = "text must contain exactly one Unicode extended grapheme"
            raise ValueError(msg)
        return value


class ParserNoteStatus(StrEnum):
    """Whether a retained PGDP note asks an unresolved question."""

    COMMENT = "comment"
    QUESTION = "question"


class ParserNoteEvidence(CanonicalModel):
    """A quarantined PGDP note with exact source and review content."""

    raw_text: str
    page_review_content: str
    question_status: ParserNoteStatus
    source_slices: tuple[SourceSlice, ...]

    @model_validator(mode="after")
    def _validate_source(self) -> Self:
        if not self.raw_text.startswith("[**"):
            msg = "raw_text must begin with a PGDP note marker"
            raise ValueError(msg)
        if not self.source_slices:
            msg = "note evidence requires source slices"
            raise ValueError(msg)
        return self


class ParserNormalizationKind(StrEnum):
    """Source-preserving normalization evidence produced by the F2 parser."""

    LETTER_SPACE_REMOVED = "letter_space_removed"
    SMALL_CAPS_CASE_NORMALIZED = "small_caps_case_normalized"


class ParserNormalizationEvidence(CanonicalModel):
    """One comparison-only normalization with its raw source map."""

    kind: ParserNormalizationKind
    source_slices: tuple[SourceSlice, ...]
    replacement_text: str
    grapheme_indices: tuple[_StrictIndex, ...]

    @model_validator(mode="after")
    def _validate_source(self) -> Self:
        if not self.source_slices:
            msg = "normalization evidence requires source slices"
            raise ValueError(msg)
        if any(index < 0 for index in self.grapheme_indices):
            msg = "normalization grapheme indices must be nonnegative"
            raise ValueError(msg)
        return self


class ParserControlKind(StrEnum):
    """Quarantined F2 controls that did not resolve to a style span."""

    UNCLOSED_STYLE_TAG = "unclosed_style_tag"


class ParserControlEvidence(CanonicalModel):
    """Raw source evidence for one unresolved F2 control."""

    kind: ParserControlKind
    tag_name: str
    raw_text: str
    source_slices: tuple[SourceSlice, ...]

    @model_validator(mode="after")
    def _validate_source(self) -> Self:
        if not self.tag_name:
            msg = "control evidence requires a tag name"
            raise ValueError(msg)
        if not self.source_slices:
            msg = "control evidence requires source slices"
            raise ValueError(msg)
        return self


class OcrTokenRef(CanonicalModel):
    """An OCR token and its projection into canonical grapheme coordinates."""

    token_id: str
    text: str
    confidence: _Probability | None
    bbox: BoundingBox
    line_id: str
    grapheme_start: _StrictIndex
    grapheme_end: _StrictIndex
    alignment_id: str

    @field_validator("bbox", mode="before")
    @classmethod
    def _accept_bbox_instance(cls, value: object) -> object:
        if isinstance(value, BoundingBox):
            return value.to_dict()
        return value

    @model_validator(mode="after")
    def _validate_grapheme_range(self) -> Self:
        _validate_half_open_range(
            (self.grapheme_start, self.grapheme_end), "OCR token grapheme range"
        )
        return self


class AlignmentPathOperation(CanonicalModel):
    """One typed monotonic edit retained for an alignment alternative path."""

    kind: Literal[
        "match",
        "substitution",
        "source_only_deletion",
        "target_only_insertion",
    ]
    source_range: tuple[_StrictIndex, _StrictIndex]
    target_range: tuple[_StrictIndex, _StrictIndex]

    @model_validator(mode="after")
    def _validate_ranges(self) -> Self:
        source_start, source_end = self.source_range
        target_start, target_end = self.target_range
        if source_start > source_end or target_start > target_end:
            msg = "alignment path operation ranges must be ordered"
            raise ValueError(msg)
        source_consumed = source_start < source_end
        target_consumed = target_start < target_end
        if self.kind in {"match", "substitution"} and not (
            source_consumed and target_consumed
        ):
            msg = "match and substitution path operations must consume both source and target"
            raise ValueError(msg)
        if self.kind == "source_only_deletion" and not (
            source_consumed and not target_consumed
        ):
            msg = "source-only deletion path operation must consume only source"
            raise ValueError(msg)
        if self.kind == "target_only_insertion" and not (
            target_consumed and not source_consumed
        ):
            msg = "target-only insertion path operation must consume only target"
            raise ValueError(msg)
        return self


class AlignmentEvidence(CanonicalModel):
    """Versioned evidence for one source-to-target alignment."""

    alignment_id: str
    method: str
    source_artifact_sha256: str
    target_artifact_sha256: str
    source_coordinate_space: SourceCoordinateSpace
    target_coordinate_space: TargetCoordinateSpace
    source_range: tuple[_StrictIndex, _StrictIndex]
    target_range: tuple[_StrictIndex, _StrictIndex]
    operations: tuple[str, ...]
    score: float
    margin: float | None
    low_margin_threshold: Annotated[float, Field(ge=0.0)] = 0.0
    alternatives: tuple[Mapping[str, object], ...]
    accepted: bool
    source_normalization_operations: tuple[ComparisonOperation, ...] = ()
    target_normalization_operations: tuple[ComparisonOperation, ...] = ()
    runner_up_operations: tuple[AlignmentPathOperation, ...] | None = None
    runner_up_target_normalization_operations: (
        tuple[ComparisonOperation, ...] | None
    ) = None

    @field_validator("source_artifact_sha256", "target_artifact_sha256")
    @classmethod
    def _validate_hashes(cls, value: str, info: object) -> str:
        field_name = getattr(info, "field_name", "artifact_sha256")
        return _validate_sha256(value, str(field_name))

    @field_validator("alternatives", mode="after")
    @classmethod
    def _freeze_alternatives(
        cls, alternatives: tuple[Mapping[str, object], ...]
    ) -> tuple[Mapping[str, object], ...]:
        return tuple(_freeze_mapping(alternative) for alternative in alternatives)

    @field_serializer("alternatives")
    def _serialize_alternatives(
        self, alternatives: tuple[Mapping[str, object], ...]
    ) -> list[dict[str, object]]:
        return [_thaw_mapping(alternative) for alternative in alternatives]

    @model_validator(mode="after")
    def _validate_evidence(self) -> Self:
        _validate_half_open_range(self.source_range, "source_range")
        _validate_half_open_range(self.target_range, "target_range")
        if not math.isfinite(self.score):
            msg = "score must be finite"
            raise ValueError(msg)
        if self.margin is not None and (
            self.margin < 0 or not math.isfinite(self.margin)
        ):
            msg = "margin must be finite and nonnegative when present"
            raise ValueError(msg)
        if not math.isfinite(self.low_margin_threshold):
            msg = "low_margin_threshold must be finite"
            raise ValueError(msg)
        expected_accepted = (
            self.margin is None or self.margin >= self.low_margin_threshold
        )
        if self.accepted is not expected_accepted:
            msg = "accepted must match the recorded low_margin_threshold"
            raise ValueError(msg)
        self._validate_normalization_operation_inputs(
            self.source_normalization_operations,
            coordinate_range=self.source_range,
            field_name="source_normalization_operations",
        )
        self._validate_normalization_operation_inputs(
            self.target_normalization_operations,
            coordinate_range=self.target_range,
            field_name="target_normalization_operations",
        )
        if self.runner_up_operations is not None:
            self._validate_path_operations(self.runner_up_operations)
        elif self.runner_up_target_normalization_operations is not None:
            msg = (
                "runner-up target normalization operations require runner_up_operations"
            )
            raise ValueError(msg)
        if self.runner_up_target_normalization_operations is not None:
            self._validate_runner_up_target_normalization_operations(
                self.runner_up_target_normalization_operations
            )
        return self

    @staticmethod
    def _validate_normalization_operation_inputs(
        operations: tuple[ComparisonOperation, ...],
        *,
        coordinate_range: tuple[int, int],
        field_name: str,
    ) -> None:
        range_start, range_end = coordinate_range
        for operation in operations:
            operation_start, operation_end = operation.input_range
            if not (range_start <= operation_start < operation_end <= range_end):
                msg = f"{field_name} input ranges must lie within the evidence range"
                raise ValueError(msg)

    def _validate_runner_up_target_normalization_operations(
        self, operations: tuple[ComparisonOperation, ...]
    ) -> None:
        self._validate_normalization_operation_inputs(
            operations,
            coordinate_range=self.target_range,
            field_name="runner_up_target_normalization_operations",
        )
        runner_up_operations = self.runner_up_operations
        if runner_up_operations is None:
            msg = (
                "runner-up target normalization operations require runner_up_operations"
            )
            raise ValueError(msg)
        matched_target_ranges = {
            operation.target_range
            for operation in runner_up_operations
            if operation.kind in {"match", "substitution"}
        }
        if any(
            operation.input_range not in matched_target_ranges
            for operation in operations
        ):
            msg = (
                "runner_up_target_normalization_operations must match a runner-up "
                "comparison transition target range"
            )
            raise ValueError(msg)

    def _validate_path_operations(
        self, operations: tuple[AlignmentPathOperation, ...]
    ) -> None:
        previous_source: tuple[int, int] | None = None
        previous_target: tuple[int, int] | None = None
        for operation in operations:
            source_start, source_end = operation.source_range
            target_start, target_end = operation.target_range
            if not (
                self.source_range[0]
                <= source_start
                <= source_end
                <= self.source_range[1]
            ):
                msg = "runner_up_operations source ranges must lie within source_range"
                raise ValueError(msg)
            if not (
                self.target_range[0]
                <= target_start
                <= target_end
                <= self.target_range[1]
            ):
                msg = "runner_up_operations target ranges must lie within target_range"
                raise ValueError(msg)
            if previous_source is not None and (
                source_start < previous_source[0] or source_end < previous_source[1]
            ):
                msg = "runner_up_operations source ranges must be monotonic"
                raise ValueError(msg)
            if previous_target is not None and (
                target_start < previous_target[0] or target_end < previous_target[1]
            ):
                msg = "runner_up_operations target ranges must be monotonic"
                raise ValueError(msg)
            if previous_source is not None and (
                source_start < previous_source[1]
                and operation.source_range != previous_source
            ):
                msg = "runner_up_operations source ranges cannot partially overlap"
                raise ValueError(msg)
            if previous_target is not None and (
                target_start < previous_target[1]
                and operation.target_range != previous_target
            ):
                msg = "runner_up_operations target ranges cannot partially overlap"
                raise ValueError(msg)
            previous_source = operation.source_range
            previous_target = operation.target_range


class TypographyPageRecord(CanonicalModel):
    """Canonical typography record for one source page."""

    schema_version: Literal["1.0", "1.1"]
    identity: TextIdentity
    original_f2_artifact_base64: str | None
    original_f2_artifact_sha256: str | None
    external_f2_artifact: ArtifactReference | None = None
    f2_page_key: str | None
    f2_page_value_lexical_byte_range: tuple[_StrictIndex, _StrictIndex] | None
    f2_decoded_page_utf8_sha256: str | None
    parsed_text: str
    graphemes: tuple[Grapheme, ...]
    ocr_tokens: tuple[OcrTokenRef, ...]
    style_spans: tuple[StyleSpan, ...]
    structural_context: tuple[str, ...]
    parser_warnings: tuple[str, ...]
    parser_notes: tuple[ParserNoteEvidence, ...] = ()
    normalization_operations: tuple[ParserNormalizationEvidence, ...] = ()
    parser_controls: tuple[ParserControlEvidence, ...] = ()
    training_eligible: bool = True
    alignments: tuple[AlignmentEvidence, ...]
    project_comments_artifact: ArtifactRef | None
    guideline_version: str

    @override
    def model_copy(
        self,
        *,
        update: Mapping[str, object] | None = None,
        deep: bool = False,
    ) -> Self:
        """Return a fully revalidated page record copy."""
        del deep
        payload = self.model_dump(mode="json", warnings="none")
        if update is not None:
            payload.update({key: _model_input(value) for key, value in update.items()})
        return type(self).model_validate(payload)

    @override
    def to_json_bytes(self) -> bytes:
        """Serialize a record without changing the 1.0 wire shape."""
        payload = self.model_dump(mode="json")
        if self.schema_version == TYPOGRAPHY_PAGE_RECORD_LEGACY_SCHEMA_VERSION:
            payload.pop("external_f2_artifact", None)
        return json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()

    @field_validator("original_f2_artifact_sha256", "f2_decoded_page_utf8_sha256")
    @classmethod
    def _validate_optional_hashes(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        field_name = getattr(info, "field_name", "sha256")
        return _validate_sha256(value, str(field_name))

    @model_validator(mode="after")
    def _validate_record(self) -> Self:
        if (
            self.schema_version == TYPOGRAPHY_PAGE_RECORD_LEGACY_SCHEMA_VERSION
            and self.external_f2_artifact is not None
        ):
            msg = "schema_version 1.0 cannot include external_f2_artifact"
            raise ValueError(msg)
        if (
            self.schema_version == TYPOGRAPHY_PAGE_RECORD_EXTERNAL_F2_SCHEMA_VERSION
            and self.external_f2_artifact is None
        ):
            msg = "schema_version 1.1 requires external_f2_artifact"
            raise ValueError(msg)
        if self.f2_page_value_lexical_byte_range is not None:
            _validate_half_open_range(
                self.f2_page_value_lexical_byte_range,
                "f2_page_value_lexical_byte_range",
            )
        artifact_bytes = self._validate_f2_artifact()
        self._validate_page_source_slices(artifact_bytes)
        expected_indices = tuple(range(len(self.graphemes)))
        actual_indices = tuple(grapheme.index for grapheme in self.graphemes)
        if actual_indices != expected_indices:
            msg = "grapheme indices must be contiguous and start at zero"
            raise ValueError(msg)
        if "".join(grapheme.text for grapheme in self.graphemes) != self.parsed_text:
            msg = "graphemes must reconstruct parsed_text exactly"
            raise ValueError(msg)
        if any(span.end > len(self.graphemes) for span in self.style_spans):
            msg = "style span end cannot exceed the page grapheme count"
            raise ValueError(msg)
        if any(
            index >= len(self.graphemes)
            for operation in self.normalization_operations
            for index in operation.grapheme_indices
        ):
            msg = "normalization grapheme indices cannot exceed the page grapheme count"
            raise ValueError(msg)
        self._validate_parser_evidence(artifact_bytes)
        alignment_ids = {alignment.alignment_id for alignment in self.alignments}
        if len(alignment_ids) != len(self.alignments):
            msg = "alignment_id values must be unique within a page record"
            raise ValueError(msg)
        for token in self.ocr_tokens:
            if token.grapheme_end > len(self.graphemes):
                msg = "OCR token grapheme range cannot exceed the page grapheme count"
                raise ValueError(msg)
            if token.alignment_id not in alignment_ids:
                msg = "OCR token alignment_id must reference a supplied alignment"
                raise ValueError(msg)
        self._validate_alignment_artifacts()
        return self

    def revalidate_external_f2_artifact(self, artifact_bytes: bytes) -> None:
        """Revalidate an external F2 reference against supplied exact bytes."""
        record = type(self).model_validate(
            self.model_dump(mode="json", warnings="none")
        )
        if record.external_f2_artifact is None:
            msg = "external F2 artifact bytes require external_f2_artifact"
            raise ValueError(msg)
        record._validate_supplied_f2_artifact_bytes(artifact_bytes)
        record._validate_page_source_slices(artifact_bytes)
        record._validate_parser_evidence(artifact_bytes)

    def _validate_page_source_slices(self, artifact_bytes: bytes | None) -> None:
        expected_hash = self.original_f2_artifact_sha256
        if expected_hash is None:
            return
        lexical_range = self.f2_page_value_lexical_byte_range
        for grapheme in self.graphemes:
            for source_slice in grapheme.source_slices:
                if source_slice.artifact_sha256 != expected_hash:
                    msg = "F2-backed grapheme source slices must use the original F2 SHA-256"
                    raise ValueError(msg)
                if lexical_range is not None and (
                    source_slice.byte_start < lexical_range[0]
                    or source_slice.byte_end > lexical_range[1]
                ):
                    msg = "F2-backed grapheme source slices must lie within the F2 lexical byte range"
                    raise ValueError(msg)
                if artifact_bytes is not None and source_slice.byte_end > len(
                    artifact_bytes
                ):
                    msg = "F2-backed grapheme source slices must lie within the F2 artifact"
                    raise ValueError(msg)
        for span in self.style_spans:
            for source_slice in span.source_slices:
                if source_slice.artifact_sha256 != expected_hash:
                    msg = "F2-backed style span source slices must use the original F2 SHA-256"
                    raise ValueError(msg)
                if lexical_range is not None and (
                    source_slice.byte_start < lexical_range[0]
                    or source_slice.byte_end > lexical_range[1]
                ):
                    msg = "F2-backed style span source slices must lie within the F2 lexical byte range"
                    raise ValueError(msg)
                if artifact_bytes is not None and source_slice.byte_end > len(
                    artifact_bytes
                ):
                    msg = "F2-backed style span source slices must lie within the F2 artifact"
                    raise ValueError(msg)

    def _validate_alignment_artifacts(self) -> None:
        text_hashes = {artifact.sha256 for artifact in self.identity.text_artifacts}
        comments_hash = (
            None
            if self.project_comments_artifact is None
            else self.project_comments_artifact.sha256
        )
        target_grapheme_count = sum(
            len(split_graphemes(token.text)) for token in self.ocr_tokens
        )
        for alignment in self.alignments:
            source_hashes = set(text_hashes)
            if (
                alignment.source_coordinate_space is SourceCoordinateSpace.RAW_BYTES
                and comments_hash is not None
            ):
                source_hashes.add(comments_hash)
            if alignment.source_artifact_sha256 not in source_hashes:
                msg = "alignment source_artifact_sha256 must identify a declared text artifact"
                raise ValueError(msg)
            if alignment.target_coordinate_space in {
                TargetCoordinateSpace.OCR_GRAPHEMES,
                TargetCoordinateSpace.OCR_TOKENS,
            }:
                if (
                    alignment.target_artifact_sha256
                    != self.identity.image_artifact.sha256
                ):
                    msg = "OCR alignment target_artifact_sha256 must identify the page image"
                    raise ValueError(msg)
                if (
                    alignment.target_coordinate_space
                    is TargetCoordinateSpace.OCR_TOKENS
                ):
                    if alignment.target_range[1] > len(self.ocr_tokens):
                        msg = "OCR alignment target_range cannot exceed OCR token count"
                        raise ValueError(msg)
                elif alignment.target_range[1] > target_grapheme_count:
                    msg = "OCR alignment target_range cannot exceed OCR grapheme count"
                    raise ValueError(msg)
            elif alignment.target_artifact_sha256 not in (
                text_hashes
                | {self.identity.image_artifact.sha256}
                | ({comments_hash} if comments_hash is not None else set())
            ):
                msg = "alignment target_artifact_sha256 must identify a declared page artifact"
                raise ValueError(msg)
            if (
                alignment.source_coordinate_space
                is SourceCoordinateSpace.SOURCE_GRAPHEMES
                and alignment.source_range[1] > len(self.graphemes)
            ):
                msg = (
                    "source grapheme alignment range cannot exceed page grapheme count"
                )
                raise ValueError(msg)

    def _validate_f2_artifact(self) -> bytes | None:
        page_evidence = (
            self.original_f2_artifact_sha256,
            self.f2_page_key,
            self.f2_page_value_lexical_byte_range,
            self.f2_decoded_page_utf8_sha256,
        )
        has_embedded_artifact = self.original_f2_artifact_base64 is not None
        has_external_artifact = self.external_f2_artifact is not None
        if has_embedded_artifact and has_external_artifact:
            msg = "embedded and external F2 artifact references are mutually exclusive"
            raise ValueError(msg)
        if all(value is None for value in page_evidence):
            if has_embedded_artifact or has_external_artifact:
                msg = "F2 artifact references require complete F2 page evidence"
                raise ValueError(msg)
            if (
                self.parser_notes
                or self.normalization_operations
                or self.parser_controls
            ):
                msg = "parser evidence requires complete F2 artifact fields"
                raise ValueError(msg)
            return None
        if any(value is None for value in page_evidence):
            msg = "F2 artifact fields must be either all present or all absent"
            raise ValueError(msg)
        expected_hash = self.original_f2_artifact_sha256
        if expected_hash is None:
            msg = "F2 artifact identity is incomplete"
            raise ValueError(msg)
        if not has_embedded_artifact and not has_external_artifact:
            msg = "F2 page evidence requires an embedded or external F2 artifact"
            raise ValueError(msg)
        external_artifact = self.external_f2_artifact
        if external_artifact is not None:
            if external_artifact.sha256 != expected_hash:
                msg = (
                    "external_f2_artifact.sha256 must match original_f2_artifact_sha256"
                )
                raise ValueError(msg)
            if not any(
                artifact.sha256 == expected_hash
                for artifact in self.identity.text_artifacts
            ):
                msg = "original F2 artifact must appear in identity.text_artifacts"
                raise ValueError(msg)
            return None
        encoded = self.original_f2_artifact_base64
        if encoded is None:
            msg = "embedded F2 artifact identity is incomplete"
            raise ValueError(msg)
        try:
            artifact_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            msg = "original_f2_artifact_base64 must be valid base64"
            raise ValueError(msg) from error
        self._validate_supplied_f2_artifact_bytes(artifact_bytes)
        if not any(
            artifact.sha256 == expected_hash
            for artifact in self.identity.text_artifacts
        ):
            msg = "original F2 artifact must appear in identity.text_artifacts"
            raise ValueError(msg)
        return artifact_bytes

    def _validate_supplied_f2_artifact_bytes(self, artifact_bytes: bytes) -> None:
        expected_hash = self.original_f2_artifact_sha256
        if expected_hash is None:
            msg = "F2 artifact identity is incomplete"
            raise ValueError(msg)
        if hashlib.sha256(artifact_bytes).hexdigest() != expected_hash:
            msg = "original_f2_artifact_sha256 does not match the supplied artifact"
            raise ValueError(msg)
        lexical_range = self.f2_page_value_lexical_byte_range
        page_key = self.f2_page_key
        decoded_page_hash = self.f2_decoded_page_utf8_sha256
        if lexical_range is None or page_key is None or decoded_page_hash is None:
            msg = "F2 page evidence is incomplete"
            raise ValueError(msg)
        start, end = lexical_range
        if end > len(artifact_bytes):
            msg = "f2_page_value_lexical_byte_range exceeds the F2 artifact"
            raise ValueError(msg)
        try:
            lexical_value: object = json.loads(artifact_bytes[start:end])
            document, member_ranges = _parse_json_object_member_ranges(artifact_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            msg = "F2 lexical value range must identify a valid JSON string"
            raise ValueError(msg) from error
        if not isinstance(lexical_value, str):
            raise PydanticCustomError(
                "f2_page_value_type",
                "F2 lexical value range must identify a JSON string",
            )
        if page_key not in document:
            msg = "f2_page_key must identify a page in the F2 artifact"
            raise ValueError(msg)
        if member_ranges[page_key] != lexical_range:
            msg = "F2 lexical byte range must identify the selected f2_page_key"
            raise ValueError(msg)
        if document[page_key] != lexical_value:
            msg = "F2 lexical value does not match f2_page_key"
            raise ValueError(msg)
        if hashlib.sha256(lexical_value.encode()).hexdigest() != decoded_page_hash:
            msg = "decoded page hash does not match the F2 lexical value"
            raise ValueError(msg)

    def _validate_parser_evidence(self, artifact_bytes: bytes | None) -> None:
        expected_hash = self.original_f2_artifact_sha256
        if expected_hash is None:
            return
        lexical_range = self.f2_page_value_lexical_byte_range
        evidence = (
            *self.parser_notes,
            *self.normalization_operations,
            *self.parser_controls,
        )
        for item in evidence:
            for source_slice in item.source_slices:
                if source_slice.artifact_sha256 != expected_hash:
                    msg = (
                        "parser evidence source slices must use the original F2 SHA-256"
                    )
                    raise ValueError(msg)
                if lexical_range is not None and (
                    source_slice.byte_start < lexical_range[0]
                    or source_slice.byte_end > lexical_range[1]
                ):
                    msg = (
                        "parser evidence source slices must lie within the F2 lexical "
                        "byte range"
                    )
                    raise ValueError(msg)
                if artifact_bytes is not None and source_slice.byte_end > len(
                    artifact_bytes
                ):
                    msg = (
                        "parser evidence source slices must lie within the F2 artifact"
                    )
                    raise ValueError(msg)
