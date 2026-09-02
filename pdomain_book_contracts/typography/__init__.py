"""Public immutable contracts for OCR-independent typography labeling.

Owns ``labels.py``, ``spans.py``, ``records.py``, ``annotations.py``,
``exchange.py``, ``book_manifest.py``, and ``review.py``, moved from
``pdomain_book_tools.typography``. Depends only on ``geometry``, ``text``,
and ``_schemas``.

``alignment.py`` and ``normalization.py`` used to live here too. They now
live in ``matching`` and ``text`` respectively — see those packages for
``AlignmentConfig``, ``ComparisonView``, and the rest of what moved.

``records.py``'s exports are resolved lazily by this module's
``__getattr__``, unlike every other submodule here — see that function's
docstring for the real import cycle this breaks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

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

if TYPE_CHECKING:
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

_RECORDS_EXPORTS = frozenset(
    {
        "TYPOGRAPHY_PAGE_RECORD_EXTERNAL_F2_SCHEMA_VERSION",
        "TYPOGRAPHY_PAGE_RECORD_LEGACY_SCHEMA_VERSION",
        "AlignmentEvidence",
        "AlignmentPathOperation",
        "ArtifactRef",
        "ArtifactSource",
        "Grapheme",
        "OcrTokenRef",
        "ParserControlEvidence",
        "ParserControlKind",
        "ParserNormalizationEvidence",
        "ParserNormalizationKind",
        "ParserNoteEvidence",
        "ParserNoteStatus",
        "SourceCoordinateSpace",
        "TargetCoordinateSpace",
        "TextIdentity",
        "TypographyPageRecord",
    }
)


def __getattr__(name: str) -> object:
    """Lazily resolve ``records.py``'s exports to break a real import cycle.

    ``records.py`` imports ``ComparisonOperation`` from ``text.normalization``.
    ``text.normalization`` in turn imports ``KnowledgeState`` / ``StyleLabel``
    (``typography.labels``) and ``CanonicalModel`` / ``StyleSpan`` (
    ``typography.spans``) for its own vocabulary — the module layout spec's
    dependency-direction table says ``text`` has no internal dependencies, but
    the code, as specified, needs those types, so ``text`` and ``typography``
    depend on each other in practice. That mismatch between the spec and the
    code is not fixed here; see this repository's Task 4 Step 2 reorganisation
    commit message.

    Importing ``records.py`` eagerly here, alongside this module's other
    submodules, makes ``import pdomain_book_contracts.typography`` run partway
    through ``text.normalization``'s own import whenever something reaches
    ``typography`` by way of ``text`` first (``matching.alignment`` does,
    among others) — Python has ``text.normalization`` on ``sys.modules``
    already but not yet finished, so ``records.py``'s
    ``from pdomain_book_contracts.text.normalization import
    ComparisonOperation`` fails with ``ImportError: cannot import name
    'ComparisonOperation' from partially initialized module``. Deferring the
    one submodule that closes the cycle to first attribute access breaks it
    without changing what any of these names resolve to or when a caller
    that imports them directly (``from
    pdomain_book_contracts.typography.records import ...``, which every
    caller inside this package's own ``matching`` subpackage does) pays for
    them.
    """
    if name in _RECORDS_EXPORTS:
        from pdomain_book_contracts.typography import records as _records

        # getattr() with a dynamic name is typed Any upstream; the runtime
        # value really is one of records.py's own typed exports, since
        # `name` was just checked against `_RECORDS_EXPORTS`.
        return cast("object", getattr(_records, name))
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
