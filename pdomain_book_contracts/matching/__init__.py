"""Public immutable contracts for source-neutral OCR-to-text matching.

Owns ``alignment.py`` (moved from ``pdomain_book_tools.typography`` — it
aligns two texts, which is what this package is for), ``engine.py``,
``models.py``, ``legacy_projection.py``, and ``pgdp_continuations.py``
(moved from ``pdomain_book_tools.matching``), plus the matching vocabulary
``match_type.py`` and ``character_groups.py`` (moved from
``pdomain_book_tools.ocr.ground_truth_matching_helpers``). Depends on
``geometry``, ``text``, and ``typography``.
"""

from __future__ import annotations

from pdomain_book_contracts.matching.alignment import (
    AlignmentConfig,
    AlignmentEdit,
    AlignmentEditKind,
    ProjectedBoundingBox,
    ProjectedStyleSpan,
    TokenAlignmentResult,
    align_tokens,
    project_style_span,
    project_token_ranges,
)
from pdomain_book_contracts.matching.character_groups import CharacterGroups
from pdomain_book_contracts.matching.engine import match_documents
from pdomain_book_contracts.matching.legacy_projection import (
    LegacyDocumentSide,
    LegacyMatchEvidence,
    LegacyProjectionMutation,
    LegacyProjectionResult,
    legacy_page_to_match_document,
    project_match_graph_onto_page,
)
from pdomain_book_contracts.matching.match_type import MatchType
from pdomain_book_contracts.matching.models import (
    ArtifactRange,
    MatchAlternative,
    MatchComparisonNormalization,
    MatchContinuationReference,
    MatchDocument,
    MatchGraph,
    MatchLine,
    MatchOperation,
    MatchOperationKind,
    MatchPage,
    MatchPolicy,
    MatchQuarantineReason,
    MatchRelation,
    MatchRelationKind,
    MatchSearchEvidence,
    MatchSearchPathEvidence,
    MatchTieBreakRule,
    MatchToken,
    canonical_relation_path_bytes,
)
from pdomain_book_contracts.matching.pgdp_continuations import (
    PgdpContinuation,
    PgdpContinuationBoundary,
    PgdpContinuationDecision,
    PgdpContinuationDecode,
    PgdpContinuationQuarantineReason,
    PgdpLogicalCandidate,
    PgdpMarkerEvidence,
    PgdpPhysicalFragment,
    PgdpQuarantinedMarker,
    PgdpRound,
    PgdpRoundContinuationEvidence,
    PgdpUnmappedMarkerEvidence,
    build_pgdp_surface_document,
    decode_pgdp_continuations,
)

__all__ = [
    "AlignmentConfig",
    "AlignmentEdit",
    "AlignmentEditKind",
    "ArtifactRange",
    "CharacterGroups",
    "LegacyDocumentSide",
    "LegacyMatchEvidence",
    "LegacyProjectionMutation",
    "LegacyProjectionResult",
    "MatchAlternative",
    "MatchComparisonNormalization",
    "MatchContinuationReference",
    "MatchDocument",
    "MatchGraph",
    "MatchLine",
    "MatchOperation",
    "MatchOperationKind",
    "MatchPage",
    "MatchPolicy",
    "MatchQuarantineReason",
    "MatchRelation",
    "MatchRelationKind",
    "MatchSearchEvidence",
    "MatchSearchPathEvidence",
    "MatchTieBreakRule",
    "MatchToken",
    "MatchType",
    "PgdpContinuation",
    "PgdpContinuationBoundary",
    "PgdpContinuationDecision",
    "PgdpContinuationDecode",
    "PgdpContinuationQuarantineReason",
    "PgdpLogicalCandidate",
    "PgdpMarkerEvidence",
    "PgdpPhysicalFragment",
    "PgdpQuarantinedMarker",
    "PgdpRound",
    "PgdpRoundContinuationEvidence",
    "PgdpUnmappedMarkerEvidence",
    "ProjectedBoundingBox",
    "ProjectedStyleSpan",
    "TokenAlignmentResult",
    "align_tokens",
    "build_pgdp_surface_document",
    "canonical_relation_path_bytes",
    "decode_pgdp_continuations",
    "legacy_page_to_match_document",
    "match_documents",
    "project_match_graph_onto_page",
    "project_style_span",
    "project_token_ranges",
]
