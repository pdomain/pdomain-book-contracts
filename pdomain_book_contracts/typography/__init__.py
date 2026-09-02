"""Public immutable contracts for OCR-independent typography labeling.

Owns ``labels.py``, ``spans.py``, ``normalization.py``, ``records.py``,
``annotations.py``, ``exchange.py``, ``book_manifest.py``, and ``review.py``,
moved from ``pdomain_book_tools.typography``. Depends only on ``geometry``
and ``_schemas``.

``alignment.py`` used to live here too. It now lives in ``matching`` — see
that package for ``AlignmentConfig`` and the rest of what moved.

``normalization.py`` moved to ``text`` and back here again: it needs
``typography.labels`` and ``typography.spans`` for its own vocabulary, so
``text`` never had the "no internal dependencies" property the module
layout spec's dependency-direction table assumed for it. Keeping
``normalization.py`` in ``typography`` — the package it actually depends
on — makes ``matching`` importing ``typography.normalization`` a one-way
dependency, which is the direction the spec already allows, so there is no
cycle to work around.
"""

from __future__ import annotations

from pdomain_book_contracts.typography.annotations import TypographyAnnotations
from pdomain_book_contracts.typography.book_manifest import (
    BookLabelingManifest,
    BookLabelingPage,
    BookMatchRelationReference,
)
from pdomain_book_contracts.typography.exchange import (
    ArtifactReference,
    CoordinateTransform,
    CoordinateTransformStage,
    CorrectionBundle,
    Evidence,
    LabelingBundle,
    ModelRun,
    ModelRunPurpose,
    PageGeometry,
    ReplacementArtifact,
    SourceOrientation,
    WordGeometry,
)
from pdomain_book_contracts.typography.labels import (
    ConfidenceTier,
    KnowledgeState,
    LabelSource,
    StyleLabel,
)
from pdomain_book_contracts.typography.records import (
    TYPOGRAPHY_PAGE_RECORD_EXTERNAL_F2_SCHEMA_VERSION,
    TYPOGRAPHY_PAGE_RECORD_LEGACY_SCHEMA_VERSION,
    AlignmentEvidence,
    AlignmentPathOperation,
    ArtifactRef,
    ArtifactSource,
    Grapheme,
    OcrTokenRef,
    ParserControlEvidence,
    ParserControlKind,
    ParserNormalizationEvidence,
    ParserNormalizationKind,
    ParserNoteEvidence,
    ParserNoteStatus,
    SourceCoordinateSpace,
    TargetCoordinateSpace,
    TextIdentity,
    TypographyPageRecord,
)
from pdomain_book_contracts.typography.review import (
    REVIEW_CONTRACT_VERSION,
    WORD_ID_NAMESPACE,
    CorrectionDecision,
    LabelState,
    ReviewDecision,
    ReviewState,
    TypographyCorrection,
    TypographyReviewMetadata,
    TypographySpan,
    TypographyTaxonomy,
    TypographyTaxonomyLabel,
    WordTypography,
    make_merged_word_id,
    make_split_word_id,
    make_word_id,
)
from pdomain_book_contracts.typography.spans import (
    GRAPHEME_SEGMENTATION_VERSION,
    SourceSlice,
    StyleSpan,
    TypographySpans,
    split_graphemes,
)

__all__ = [
    "GRAPHEME_SEGMENTATION_VERSION",
    "REVIEW_CONTRACT_VERSION",
    "TYPOGRAPHY_PAGE_RECORD_EXTERNAL_F2_SCHEMA_VERSION",
    "TYPOGRAPHY_PAGE_RECORD_LEGACY_SCHEMA_VERSION",
    "WORD_ID_NAMESPACE",
    "AlignmentEvidence",
    "AlignmentPathOperation",
    "ArtifactRef",
    "ArtifactReference",
    "ArtifactSource",
    "BookLabelingManifest",
    "BookLabelingPage",
    "BookMatchRelationReference",
    "ConfidenceTier",
    "CoordinateTransform",
    "CoordinateTransformStage",
    "CorrectionBundle",
    "CorrectionDecision",
    "Evidence",
    "Grapheme",
    "KnowledgeState",
    "LabelSource",
    "LabelState",
    "LabelingBundle",
    "ModelRun",
    "ModelRunPurpose",
    "OcrTokenRef",
    "PageGeometry",
    "ParserControlEvidence",
    "ParserControlKind",
    "ParserNormalizationEvidence",
    "ParserNormalizationKind",
    "ParserNoteEvidence",
    "ParserNoteStatus",
    "ReplacementArtifact",
    "ReviewDecision",
    "ReviewState",
    "SourceCoordinateSpace",
    "SourceOrientation",
    "SourceSlice",
    "StyleLabel",
    "StyleSpan",
    "TargetCoordinateSpace",
    "TextIdentity",
    "TypographyAnnotations",
    "TypographyCorrection",
    "TypographyPageRecord",
    "TypographyReviewMetadata",
    "TypographySpan",
    "TypographySpans",
    "TypographyTaxonomy",
    "TypographyTaxonomyLabel",
    "WordGeometry",
    "WordTypography",
    "make_merged_word_id",
    "make_split_word_id",
    "make_word_id",
    "split_graphemes",
]
