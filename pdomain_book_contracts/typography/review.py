"""Portable, immutable typography-review contract.

The review contract is deliberately separate from source-evidence records.
It describes human and model labels after a page has been extracted, so it can
move between the source-data pipeline, the SPA, and training tools unchanged.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import string
import uuid
from collections.abc import Mapping, Sequence
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Self

from pydantic import Field, field_serializer, field_validator, model_validator

from pdomain_book_contracts.typography.labels import ConfidenceTier, LabelSource
from pdomain_book_contracts.typography.spans import (
    GRAPHEME_SEGMENTATION_VERSION,
    CanonicalModel,
    split_graphemes,
)

REVIEW_CONTRACT_VERSION = "0.25.0"
"""Version of this portable review/exchange contract."""

WORD_ID_NAMESPACE = uuid.UUID("6f2d7ad0-6e7f-5a2d-b29b-4d6e6bb7cd90")
"""Fixed UUIDv5 namespace for canonical typography word identifiers."""

_StrictIndex = Annotated[int, Field(strict=True, ge=0)]


class LabelState(StrEnum):
    """Review knowledge for one taxonomy label on a word."""

    UNKNOWN = "unknown"
    POSITIVE = "positive"
    NEGATIVE = "negative"


class ReviewState(StrEnum):
    """Lifecycle state for a word review."""

    UNREVIEWED = "unreviewed"
    REVIEWED = "reviewed"
    REVIEWED_REGULAR = "reviewed_regular"
    QUARANTINED = "quarantined"
    DEFERRED = "deferred"


class ReviewDecision(StrEnum):
    """Decision recorded when a reviewer resolves a proposed label."""

    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CHANGES = "needs_changes"


class CorrectionDecision(StrEnum):
    """Decision that determines whether a correction carries a replacement."""

    APPROVED_EDIT = "approved_edit"
    REVIEWED_REGULAR = "reviewed_regular"
    REJECT_SOURCE = "reject_source"
    REJECT_ALIGNMENT = "reject_alignment"
    UNUSABLE_IMAGE = "unusable_image"
    DEFER = "defer"
    ACCEPT = "accept"


def canonical_json_bytes(value: object) -> bytes:
    """Encode JSON-compatible contract content deterministically."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def validate_sha256(value: str, field_name: str) -> str:
    """Validate and normalize a lowercase SHA-256 digest."""
    if len(value) != 64 or any(char not in string.hexdigits for char in value):
        msg = f"{field_name} must be a 64-character hexadecimal SHA-256"
        raise ValueError(msg)
    return value.lower()


def validate_word_id(value: str) -> str:
    """Validate a UUIDv5-derived portable word identifier."""
    try:
        identifier = uuid.UUID(value)
    except ValueError as error:
        msg = "word_id must be a UUIDv5 value"
        raise ValueError(msg) from error
    if identifier.version != 5:
        msg = "word_id must be a UUIDv5 value"
        raise ValueError(msg)
    return str(identifier)


class TypographyTaxonomyLabel(CanonicalModel):
    """One ordered label in the review taxonomy."""

    value: str
    display_name: str
    required_for_completion: bool
    trainable: bool

    @field_validator("value", "display_name")
    @classmethod
    def _require_nonempty(cls, value: str) -> str:
        if not value.strip():
            msg = "taxonomy label values must not be empty"
            raise ValueError(msg)
        return value


class TypographyTaxonomy(CanonicalModel):
    """Versioned ordered taxonomy and its exact canonical-content hash."""

    version: str
    labels: tuple[TypographyTaxonomyLabel, ...]
    taxonomy_hash: str = ""

    @model_validator(mode="after")
    def _derive_taxonomy_hash(self) -> Self:
        if not self.version.strip():
            msg = "taxonomy version must not be empty"
            raise ValueError(msg)
        values = tuple(label.value for label in self.labels)
        if len(set(values)) != len(values):
            msg = "taxonomy labels must have unique values"
            raise ValueError(msg)
        expected = hashlib.sha256(
            canonical_json_bytes(
                {
                    "labels": [label.model_dump(mode="json") for label in self.labels],
                    "version": self.version,
                }
            )
        ).hexdigest()
        if self.taxonomy_hash and self.taxonomy_hash != expected:
            msg = "taxonomy_hash does not match the ordered taxonomy payload"
            raise ValueError(msg)
        object.__setattr__(self, "taxonomy_hash", expected)
        return self

    def label_values(self) -> tuple[str, ...]:
        """Return taxonomy labels in their contract-defined order."""
        return tuple(label.value for label in self.labels)


class TypographySpan(CanonicalModel):
    """A positive taxonomy label over a nonempty half-open grapheme range."""

    span_id: str
    label: str
    start: _StrictIndex
    end: _StrictIndex
    label_source: LabelSource
    confidence_tier: ConfidenceTier
    alignment_evidence_id: str
    prediction_id: str | None = None

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        if (
            not self.span_id.strip()
            or not self.label.strip()
            or not self.alignment_evidence_id.strip()
        ):
            msg = "span label must not be empty"
            raise ValueError(msg)
        if self.start >= self.end:
            msg = "typography span must be a nonempty half-open grapheme range"
            raise ValueError(msg)
        return self


class TypographyReviewMetadata(CanonicalModel):
    """Optional actor and time metadata for a review operation."""

    reviewer_id: str | None = None
    reviewed_at: dt.datetime | None = None
    note: str | None = None
    decision: ReviewDecision | None = None

    @field_validator("reviewed_at")
    @classmethod
    def _require_timezone(cls, value: dt.datetime | None) -> dt.datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            msg = "reviewed_at must include a timezone"
            raise ValueError(msg)
        return value


def _freeze_label_states(value: Mapping[str, LabelState]) -> Mapping[str, LabelState]:
    """Freeze label states after Pydantic has validated enum values."""
    return MappingProxyType(dict(value))


class WordTypography(CanonicalModel):
    """Typography labels for one stable OCR word.

    A positive span requires a matching positive entry in ``label_states``.
    A negative state is reviewed regular text; ``unknown`` is intentionally
    incomplete and is never equivalent to regular text.
    """

    word_id: str
    text: str
    text_sha256: str
    page_content_sha256: str
    image_artifact_sha256: str
    grapheme_map_version: str
    taxonomy_version: str
    taxonomy_hash: str
    label_states: Mapping[str, LabelState]
    spans: tuple[TypographySpan, ...] = ()
    source_evidence_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    whole_word_labels: tuple[str, ...] | None = None
    word_revision: Annotated[int, Field(strict=True, ge=0)] = 0
    review_state: ReviewState = ReviewState.UNREVIEWED
    metadata: TypographyReviewMetadata | None = None

    @field_validator("taxonomy_version")
    @classmethod
    def _require_identifier(cls, value: str) -> str:
        if not value.strip():
            msg = "identifier values must not be empty"
            raise ValueError(msg)
        return value

    @field_validator("word_id")
    @classmethod
    def _validate_word_id(cls, value: str) -> str:
        return validate_word_id(value)

    @field_validator(
        "text_sha256",
        "page_content_sha256",
        "image_artifact_sha256",
        "taxonomy_hash",
    )
    @classmethod
    def _validate_hash(cls, value: str, info: object) -> str:
        field_name = getattr(info, "field_name", "sha256")
        return validate_sha256(value, str(field_name))

    @field_validator("grapheme_map_version")
    @classmethod
    def _validate_grapheme_map_version(cls, value: str) -> str:
        if value != GRAPHEME_SEGMENTATION_VERSION:
            msg = "grapheme_map_version must equal the contract segmentation version"
            raise ValueError(msg)
        return value

    @field_validator("source_evidence_ids")
    @classmethod
    def _validate_evidence_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if (
            not value
            or any(not item.strip() for item in value)
            or len(set(value)) != len(value)
        ):
            msg = "source_evidence_ids must be nonempty and unique"
            raise ValueError(msg)
        return value

    @field_validator("label_states")
    @classmethod
    def _freeze_states(
        cls, value: Mapping[str, LabelState]
    ) -> Mapping[str, LabelState]:
        if any(not label.strip() for label in value):
            msg = "label state names must not be empty"
            raise ValueError(msg)
        return _freeze_label_states(value)

    @model_validator(mode="after")
    def _validate_word(self) -> Self:
        expected_text_hash = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        if self.text_sha256 != expected_text_hash:
            msg = "text_sha256 does not match text"
            raise ValueError(msg)
        grapheme_count = len(split_graphemes(self.text))
        if any(span.end > grapheme_count for span in self.spans):
            msg = "typography span end cannot exceed the word grapheme count"
            raise ValueError(msg)
        for span in self.spans:
            if self.label_states.get(span.label) is not LabelState.POSITIVE:
                msg = "a typography span requires a matching positive label state"
                raise ValueError(msg)
        positive_span_labels = {span.label for span in self.spans}
        if len({span.span_id for span in self.spans}) != len(self.spans):
            msg = "typography span IDs must be unique within a word"
            raise ValueError(msg)
        if any(
            state is LabelState.POSITIVE and label not in positive_span_labels
            for label, state in self.label_states.items()
        ):
            msg = "a positive label state requires a positive typography span"
            raise ValueError(msg)
        derived = tuple(
            label
            for label in sorted(positive_span_labels)
            if self._covers_whole_word(label, grapheme_count)
        )
        if self.whole_word_labels is not None and self.whole_word_labels != derived:
            msg = "whole_word_labels must equal derived full-word positive labels"
            raise ValueError(msg)
        object.__setattr__(self, "whole_word_labels", derived)
        return self

    def _covers_whole_word(self, label: str, grapheme_count: int) -> bool:
        """Return whether positive spans cover every grapheme for one label."""
        if grapheme_count == 0:
            return False
        cursor = 0
        for span in sorted(
            (item for item in self.spans if item.label == label),
            key=lambda item: item.start,
        ):
            if span.start > cursor:
                return False
            cursor = max(cursor, span.end)
        return cursor == grapheme_count

    @field_serializer("label_states")
    def _serialize_states(self, value: Mapping[str, LabelState]) -> dict[str, str]:
        return {label: state.value for label, state in value.items()}

    @property
    def grapheme_count(self) -> int:
        """Return the exact count used by all span boundaries."""
        return len(split_graphemes(self.text))

    def validate_taxonomy(self, taxonomy: TypographyTaxonomy) -> None:
        """Reject a word whose taxonomy identity or labels do not match."""
        if (
            self.taxonomy_version != taxonomy.version
            or self.taxonomy_hash != taxonomy.taxonomy_hash
        ):
            msg = "word taxonomy version or hash does not match the supplied taxonomy"
            raise ValueError(msg)
        allowed = set(taxonomy.label_values())
        unknown = set(self.label_states).difference(allowed)
        if unknown:
            msg = f"word contains labels absent from taxonomy: {sorted(unknown)!r}"
            raise ValueError(msg)
        if any(span.label not in allowed for span in self.spans):
            msg = "word contains span labels absent from taxonomy"
            raise ValueError(msg)
        missing = tuple(
            label.value
            for label in taxonomy.labels
            if label.required_for_completion
            and self.label_states.get(label.value, LabelState.UNKNOWN)
            is LabelState.UNKNOWN
        )
        if (
            self.review_state in {ReviewState.REVIEWED, ReviewState.REVIEWED_REGULAR}
            and missing
        ):
            msg = "reviewed word has unknown required taxonomy labels"
            raise ValueError(msg)
        if self.review_state is ReviewState.REVIEWED_REGULAR and any(
            self.label_states.get(label.value, LabelState.UNKNOWN)
            is not LabelState.NEGATIVE
            for label in taxonomy.labels
            if label.required_for_completion
        ):
            msg = "reviewed_regular word requires negative required taxonomy labels"
            raise ValueError(msg)

    def missing_required_labels(self, taxonomy: TypographyTaxonomy) -> tuple[str, ...]:
        """Return required labels which are still absent or unknown."""
        self.validate_taxonomy(taxonomy)
        return tuple(
            label.value
            for label in taxonomy.labels
            if label.required_for_completion
            and self.label_states.get(label.value, LabelState.UNKNOWN)
            is LabelState.UNKNOWN
        )

    def is_complete(self, taxonomy: TypographyTaxonomy) -> bool:
        """Return whether all required taxonomy labels have a review state."""
        return self.review_state in {
            ReviewState.REVIEWED,
            ReviewState.REVIEWED_REGULAR,
        } and not self.missing_required_labels(taxonomy)


def _canonical_word_key(
    *, project_id: str, page_id: str, reading_order: int, text: str
) -> str:
    """Encode the published UUIDv5 word-id tuple without ambiguity."""
    if not project_id or not page_id:
        msg = "project_id and page_id must not be empty"
        raise ValueError(msg)
    if reading_order < 0:
        msg = "reading_order must be nonnegative"
        raise ValueError(msg)
    return canonical_json_bytes(
        ("pdomain.typography.word.v1", project_id, page_id, reading_order, text)
    ).decode("utf-8")


def make_word_id(
    *, project_id: str, page_id: str, reading_order: int, text: str
) -> str:
    """Make a stable word ID from the published UUIDv5 canonical tuple.

    Corrections never reissue this ID: a corrected ``WordTypography`` retains
    the same ``word_id`` and revision history lives in ``TypographyCorrection``.
    """
    return str(
        uuid.uuid5(
            WORD_ID_NAMESPACE,
            _canonical_word_key(
                project_id=project_id,
                page_id=page_id,
                reading_order=reading_order,
                text=text,
            ),
        )
    )


def make_split_word_id(parent_word_id: str, *, split_index: int) -> str:
    """Make a deterministic descendant ID for a word split at ``split_index``."""
    if split_index < 0:
        msg = "split_index must be nonnegative"
        raise ValueError(msg)
    parent_word_id = validate_word_id(parent_word_id)
    return str(
        uuid.uuid5(
            WORD_ID_NAMESPACE,
            canonical_json_bytes(("split-v1", parent_word_id, split_index)).decode(
                "utf-8"
            ),
        )
    )


def make_merged_word_id(word_ids: Sequence[str]) -> str:
    """Make a deterministic ID for an ordered merge of two or more words."""
    if len(word_ids) < 2:
        msg = "word_ids must contain at least two IDs in reading order"
        raise ValueError(msg)
    canonical_word_ids = tuple(validate_word_id(word_id) for word_id in word_ids)
    return str(
        uuid.uuid5(
            WORD_ID_NAMESPACE,
            canonical_json_bytes(("merge-v1", *canonical_word_ids)).decode("utf-8"),
        )
    )


class TypographyCorrection(CanonicalModel):
    """One immutable revision of a stable word's typography review."""

    correction_id: str
    word_id: str
    revision: Annotated[int, Field(strict=True, ge=1)]
    supersedes_id: str | None
    base_page_sha256: str
    base_image_sha256: str
    base_text_sha256: str
    base_word_revision: Annotated[int, Field(strict=True, ge=0)]
    replacement_text_sha256: str | None
    replacement_page_sha256: str | None
    replacement_image_sha256: str | None
    replacement_page_head_sha256: str | None
    replacement_word_revision: Annotated[int, Field(strict=True, ge=1)] | None
    taxonomy_version: str
    taxonomy_hash: str
    grapheme_map_version: str
    page_head_sha256: str
    labeler_id: str
    decision: CorrectionDecision
    replacement: WordTypography | None
    metadata: TypographyReviewMetadata | None = None

    @field_validator("correction_id", "taxonomy_version", "labeler_id")
    @classmethod
    def _require_id(cls, value: str) -> str:
        if not value.strip():
            msg = "correction identifiers must not be empty"
            raise ValueError(msg)
        return value

    @field_validator("word_id")
    @classmethod
    def _validate_word_id(cls, value: str) -> str:
        return validate_word_id(value)

    @field_validator(
        "base_page_sha256",
        "base_image_sha256",
        "base_text_sha256",
        "replacement_text_sha256",
        "replacement_page_sha256",
        "replacement_image_sha256",
        "replacement_page_head_sha256",
        "taxonomy_hash",
        "page_head_sha256",
    )
    @classmethod
    def _validate_base_hash(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        return validate_sha256(value, str(getattr(info, "field_name", "sha256")))

    @field_validator("grapheme_map_version")
    @classmethod
    def _validate_grapheme_map_version(cls, value: str) -> str:
        if value != GRAPHEME_SEGMENTATION_VERSION:
            msg = "grapheme_map_version must equal the contract segmentation version"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_revision(self) -> Self:
        if self.revision == 1 and self.supersedes_id is not None:
            msg = "revision 1 must not declare supersedes_id"
            raise ValueError(msg)
        if self.revision > 1 and not self.supersedes_id:
            msg = "revision greater than 1 requires supersedes_id"
            raise ValueError(msg)
        if (
            self.decision
            in {
                CorrectionDecision.APPROVED_EDIT,
                CorrectionDecision.ACCEPT,
                CorrectionDecision.REVIEWED_REGULAR,
            }
            and self.replacement is None
        ):
            msg = "accepted correction requires replacement"
            raise ValueError(msg)
        if (
            self.decision
            in {
                CorrectionDecision.REJECT_SOURCE,
                CorrectionDecision.REJECT_ALIGNMENT,
                CorrectionDecision.UNUSABLE_IMAGE,
                CorrectionDecision.DEFER,
            }
            and self.replacement is not None
        ):
            msg = "rejected correction must not carry replacement"
            raise ValueError(msg)
        if self.replacement is not None and self.replacement.word_id != self.word_id:
            msg = "correction replacement word_id must remain stable"
            raise ValueError(msg)
        if self.decision in {
            CorrectionDecision.APPROVED_EDIT,
            CorrectionDecision.ACCEPT,
            CorrectionDecision.REVIEWED_REGULAR,
        } and (
            self.replacement_text_sha256 is None
            or self.replacement_page_sha256 is None
            or self.replacement_image_sha256 is None
            or self.replacement_page_head_sha256 is None
            or self.replacement_word_revision is None
        ):
            msg = "accepted correction requires replacement hash and revision"
            raise ValueError(msg)
        if self.decision not in {
            CorrectionDecision.APPROVED_EDIT,
            CorrectionDecision.ACCEPT,
            CorrectionDecision.REVIEWED_REGULAR,
        } and (
            self.replacement_text_sha256 is not None
            or self.replacement_page_sha256 is not None
            or self.replacement_image_sha256 is not None
            or self.replacement_page_head_sha256 is not None
            or self.replacement_word_revision is not None
        ):
            msg = "rejected correction must not carry replacement hash or revision"
            raise ValueError(msg)
        if (
            self.replacement_word_revision is not None
            and self.replacement_word_revision <= self.base_word_revision
        ):
            msg = "replacement word revision must exceed the base word revision"
            raise ValueError(msg)
        if self.replacement is not None and (
            self.replacement.text_sha256 != self.replacement_text_sha256
            or self.replacement.page_content_sha256 != self.replacement_page_sha256
            or self.replacement.image_artifact_sha256 != self.replacement_image_sha256
            or self.replacement.taxonomy_version != self.taxonomy_version
            or self.replacement.taxonomy_hash != self.taxonomy_hash
            or self.replacement.grapheme_map_version != self.grapheme_map_version
        ):
            msg = "replacement does not match correction hash or contract metadata"
            raise ValueError(msg)
        return self

    @property
    def effective_page_sha256(self) -> str:
        """Return resulting page hash, inheriting the base for no-edit decisions."""
        return self.replacement_page_sha256 or self.base_page_sha256

    @property
    def effective_image_sha256(self) -> str:
        """Return resulting image hash, inheriting the base for no-edit decisions."""
        return self.replacement_image_sha256 or self.base_image_sha256

    @property
    def effective_text_sha256(self) -> str:
        """Return resulting text hash, inheriting the base for no-edit decisions."""
        return self.replacement_text_sha256 or self.base_text_sha256

    @property
    def effective_word_revision(self) -> int:
        """Return resulting word revision, inheriting the base for no-edit decisions."""
        return self.replacement_word_revision or self.base_word_revision

    @property
    def effective_page_head_sha256(self) -> str:
        """Return resulting page-head hash, inheriting the base for no-edit decisions."""
        return self.replacement_page_head_sha256 or self.page_head_sha256
