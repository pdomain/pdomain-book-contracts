"""Lossless decoding of PGDP ``*`` physical-continuation controls."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Self, override

from pydantic import Field, field_validator, model_validator

from pdomain_book_tools.matching.models import (
    ArtifactRange,
    MatchDocument,
    MatchLine,
    MatchPage,
    MatchToken,
)
from pdomain_book_tools.typography.spans import CanonicalModel, split_graphemes

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


def _continuation_id(payload: Mapping[str, object]) -> str:
    """Return the canonical content ID for one continuation payload."""
    content = {key: value for key, value in payload.items() if key != "continuation_id"}
    canonical = json.dumps(
        content,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class PgdpRound(StrEnum):
    """A PGDP text round that may record physical continuation controls."""

    F2 = "f2"
    P3 = "p3"


class PgdpContinuationBoundary(StrEnum):
    """The physical boundary removed by a PGDP continuation control."""

    SAME_LINE = "same_line"
    LINE = "line"
    PAGE = "page"


class PgdpContinuationDecision(StrEnum):
    """A later lexical decision about one already-proven physical join."""

    JOIN_WITHOUT_HYPHEN = "join_without_hyphen"
    KEEP_HYPHEN = "keep_hyphen"
    LEAVE_SEPARATE = "leave_separate"
    PRESERVE_PUNCTUATION = "preserve_punctuation"
    AMBIGUOUS = "ambiguous"


class PgdpContinuationQuarantineReason(StrEnum):
    """Reasons PGDP marker evidence cannot safely become a continuation edge."""

    EMPTY_FRAGMENT = "empty_fragment"
    NONADJACENT_MARKERS = "nonadjacent_markers"
    ORPHAN_LEADING_MARKER = "orphan_leading_marker"
    ORPHAN_TRAILING_MARKER = "orphan_trailing_marker"
    ROUND_CONFLICT = "round_conflict"
    SOURCE_RANGE_MISMATCH = "source_range_mismatch"


class PgdpPhysicalFragment(CanonicalModel):
    """One unchanged physical text fragment with a source range per grapheme."""

    text: str
    token_id: str
    page_id: str
    line_id: str
    grapheme_ranges: tuple[ArtifactRange, ...]

    @field_validator("text", "token_id", "page_id", "line_id")
    @classmethod
    def _validate_nonempty_text(cls, value: str) -> str:
        if not value:
            msg = "physical fragment fields must not be empty"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_grapheme_ranges(self) -> PgdpPhysicalFragment:
        graphemes = split_graphemes(self.text)
        if len(graphemes) != len(self.grapheme_ranges):
            msg = "physical fragments require one source range per grapheme"
            raise ValueError(msg)
        if any(
            source_range.grapheme_end - source_range.grapheme_start != 1
            for source_range in self.grapheme_ranges
        ):
            msg = "physical fragment grapheme ranges must each cover one grapheme"
            raise ValueError(msg)
        return self


class PgdpMarkerEvidence(CanonicalModel):
    """Exact source ranges for one round's continuation markers."""

    round: PgdpRound
    marker_ranges: tuple[ArtifactRange, ...]

    @model_validator(mode="after")
    def _validate_markers(self) -> PgdpMarkerEvidence:
        if not self.marker_ranges:
            msg = "marker evidence requires at least one marker range"
            raise ValueError(msg)
        if any(
            source_range.grapheme_end - source_range.grapheme_start != 1
            for source_range in self.marker_ranges
        ):
            msg = "marker ranges must each cover one grapheme"
            raise ValueError(msg)
        return self

    @property
    def marker_count(self) -> int:
        """Return the number of raw ``*`` controls retained as evidence."""
        return len(self.marker_ranges)


class PgdpLogicalCandidate(CanonicalModel):
    """One logical text form that preserves the physical fragments separately."""

    text: str
    decision: PgdpContinuationDecision

    @field_validator("text")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        if not value:
            msg = "logical candidate text must not be empty"
            raise ValueError(msg)
        return value


class PgdpRoundContinuationEvidence(CanonicalModel):
    """One round's complete physical fragment and marker evidence."""

    round: PgdpRound
    left_fragment: PgdpPhysicalFragment
    right_fragment: PgdpPhysicalFragment
    marker_evidence: PgdpMarkerEvidence

    @model_validator(mode="after")
    def _validate_round(self) -> PgdpRoundContinuationEvidence:
        if self.marker_evidence.round is not self.round:
            msg = "round continuation marker evidence must use the declared round"
            raise ValueError(msg)
        return self


class PgdpContinuation(CanonicalModel):
    """One reversible PGDP physical-continuation edge."""

    continuation_id: str | None = None
    left_fragment: PgdpPhysicalFragment
    right_fragment: PgdpPhysicalFragment
    boundary: PgdpContinuationBoundary
    marker_evidence: tuple[PgdpMarkerEvidence, ...]
    round_evidence: tuple[PgdpRoundContinuationEvidence, ...]
    logical_candidates: tuple[PgdpLogicalCandidate, ...]
    decision: PgdpContinuationDecision
    quarantine_reasons: tuple[PgdpContinuationQuarantineReason, ...] = ()

    @override
    def model_copy(
        self,
        *,
        update: Mapping[str, object] | None = None,
        deep: bool = False,
    ) -> Self:
        """Return a revalidated copy that recomputes its continuation identity."""
        del deep
        payload = {**self.model_dump(), **(update or {}), "continuation_id": None}
        if update is not None and "round_evidence" not in update:
            updated_left = update.get("left_fragment")
            updated_right = update.get("right_fragment")
            if isinstance(updated_left, PgdpPhysicalFragment) or isinstance(
                updated_right, PgdpPhysicalFragment
            ):
                authoritative_payload = self.round_evidence[0].model_dump()
                if isinstance(updated_left, PgdpPhysicalFragment):
                    authoritative_payload["left_fragment"] = updated_left
                if isinstance(updated_right, PgdpPhysicalFragment):
                    authoritative_payload["right_fragment"] = updated_right
                authoritative = PgdpRoundContinuationEvidence.model_validate(
                    authoritative_payload
                )
                payload["round_evidence"] = (
                    authoritative,
                    *self.round_evidence[1:],
                )
        return type(self).model_validate(payload)

    @model_validator(mode="after")
    def _validate_continuation(self) -> PgdpContinuation:
        rounds = tuple(evidence.round for evidence in self.marker_evidence)
        if not rounds:
            msg = "continuations require marker evidence"
            raise ValueError(msg)
        if len(set(rounds)) != len(rounds):
            msg = "continuations allow one marker evidence record per round"
            raise ValueError(msg)
        evidence_rounds = tuple(evidence.round for evidence in self.round_evidence)
        if not evidence_rounds:
            msg = "continuations require complete per-round evidence"
            raise ValueError(msg)
        if len(set(evidence_rounds)) != len(evidence_rounds):
            msg = "continuations allow one complete evidence record per round"
            raise ValueError(msg)
        if evidence_rounds != rounds:
            msg = "round evidence order must exactly match marker evidence order"
            raise ValueError(msg)
        authoritative_evidence = self.round_evidence[0]
        if (
            authoritative_evidence.left_fragment != self.left_fragment
            or authoritative_evidence.right_fragment != self.right_fragment
        ):
            msg = "authoritative fragments must exactly match primary fragments"
            raise ValueError(msg)
        for marker, round_record in zip(
            self.marker_evidence, self.round_evidence, strict=True
        ):
            if marker != round_record.marker_evidence:
                msg = "marker evidence must exactly match its same-round record"
                raise ValueError(msg)
        if not self.logical_candidates:
            msg = "continuations require at least one logical candidate"
            raise ValueError(msg)
        candidate_texts = tuple(candidate.text for candidate in self.logical_candidates)
        if len(set(candidate_texts)) != len(candidate_texts):
            msg = "logical candidates must be distinct"
            raise ValueError(msg)
        if self.decision is PgdpContinuationDecision.AMBIGUOUS:
            if len(self.logical_candidates) < 2:
                msg = "ambiguous continuations require multiple logical candidates"
                raise ValueError(msg)
        elif len(self.logical_candidates) != 1:
            msg = "resolved continuations require exactly one logical candidate"
            raise ValueError(msg)
        elif self.logical_candidates[0].decision is not self.decision:
            msg = "resolved candidate decision must equal the continuation decision"
            raise ValueError(msg)
        expected = _continuation_id(self.model_dump(mode="json"))
        if self.continuation_id is not None and self.continuation_id != expected:
            msg = "continuation_id does not match the canonical payload"
            raise ValueError(msg)
        object.__setattr__(self, "continuation_id", expected)
        return self


class PgdpQuarantinedMarker(CanonicalModel):
    """Marker source evidence retained when no safe continuation edge exists."""

    marker_evidence: PgdpMarkerEvidence | None
    unmapped_marker_evidence: PgdpUnmappedMarkerEvidence | None
    reason: PgdpContinuationQuarantineReason

    @model_validator(mode="after")
    def _validate_marker_evidence(self) -> PgdpQuarantinedMarker:
        if (self.marker_evidence is None) == (self.unmapped_marker_evidence is None):
            msg = "quarantined markers require exactly one evidence representation"
            raise ValueError(msg)
        return self


class PgdpUnmappedMarkerEvidence(CanonicalModel):
    """A marker location retained when input ranges cannot map its grapheme."""

    round: PgdpRound
    token_id: str
    page_id: str
    line_id: str
    marker_grapheme_index: int = Field(ge=0, strict=True)
    token_artifact_ranges: tuple[ArtifactRange, ...]

    @field_validator("token_id", "page_id", "line_id")
    @classmethod
    def _validate_nonempty_identifier(cls, value: str) -> str:
        if not value:
            msg = "unmapped marker identifiers must not be empty"
            raise ValueError(msg)
        return value


class PgdpContinuationDecode(CanonicalModel):
    """All decoded PGDP continuation edges and explicit unresolved evidence."""

    continuations: tuple[PgdpContinuation, ...]
    quarantined_markers: tuple[PgdpQuarantinedMarker, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _LocatedToken:
    """One physical token with its round and reading-order location."""

    round: PgdpRound
    token: MatchToken
    page_id: str
    page_index: int
    line_id: str
    line_index: int
    token_index: int
    document_index: int
    grapheme_ranges: tuple[ArtifactRange, ...] | None


@dataclass(frozen=True)
class _RoundEdge:
    """A round-local edge with a tokenization-independent identity."""

    continuation: PgdpContinuation
    anchor: _EdgeAnchor


@dataclass(frozen=True)
class _UnanchoredRoundEdge:
    """A decoded edge before its boundary-local ordinal is assigned."""

    continuation: PgdpContinuation
    locus: _BoundaryLocus


@dataclass(frozen=True)
class _BoundaryLocus:
    """A tokenization-independent physical continuation boundary."""

    left_page_id: str
    left_line_id: str
    right_page_id: str
    right_line_id: str
    boundary: PgdpContinuationBoundary


@dataclass(frozen=True)
class _EdgeAnchor:
    """A boundary locus plus its physical reading-order continuation ordinal."""

    locus: _BoundaryLocus
    continuation_ordinal: int


def decode_pgdp_continuations(
    f2_document: MatchDocument, p3_document: MatchDocument
) -> PgdpContinuationDecode:
    """Decode F2 and P3 ``*`` controls without altering either input document.

    Inputs must give every token grapheme an exact ``ArtifactRange``. This keeps
    the decoder independent of PGDP JSON parsing while making every emitted
    fragment and marker traceable to the original artifact bytes.
    """
    f2_edges, f2_quarantine = _decode_round(PgdpRound.F2, f2_document)
    p3_edges, p3_quarantine = _decode_round(PgdpRound.P3, p3_document)
    continuations = _reconcile_rounds(f2_edges, p3_edges)
    return PgdpContinuationDecode(
        continuations=continuations,
        quarantined_markers=f2_quarantine + p3_quarantine,
    )


def build_pgdp_surface_document(
    document: MatchDocument,
    continuations: tuple[PgdpContinuation, ...],
) -> MatchDocument:
    """Return a source-preserving matching surface with PGDP markers removed.

    The adapter selects one round record for each continuation from stable token
    IDs. It changes neither physical token topology nor source ranges other
    than removing exact ranges whose source grapheme is a PGDP ``*`` marker.
    """
    token_locations = _token_locations(document)
    marker_ranges_by_token: dict[str, set[bytes]] = {}
    for continuation in continuations:
        if continuation.decision is PgdpContinuationDecision.AMBIGUOUS:
            msg = "cannot build a matching surface from an ambiguous continuation"
            raise ValueError(msg)
        evidence = _select_round_evidence(continuation, token_locations)
        if evidence is None:
            continue
        _validate_round_evidence_against_document(evidence, token_locations)
        _record_marker_ranges(
            evidence,
            token_locations,
            marker_ranges_by_token,
        )
    pages = tuple(
        MatchPage(
            page_id=page.page_id,
            lines=tuple(
                MatchLine(
                    line_id=line.line_id,
                    tokens=tuple(
                        _surface_token(
                            token,
                            marker_ranges_by_token.get(token.token_id, set()),
                        )
                        for token in line.tokens
                    ),
                )
                for line in page.lines
            ),
        )
        for page in document.pages
    )
    return MatchDocument(
        document_id=document.document_id,
        pages=pages,
        warnings=document.warnings,
    )


def _token_locations(document: MatchDocument) -> dict[str, MatchToken]:
    """Return stable document tokens and reject duplicate source ranges."""
    locations: dict[str, MatchToken] = {}
    source_ranges: set[bytes] = set()
    for page in document.pages:
        for line in page.lines:
            for token in line.tokens:
                _validated_token_graphemes(token)
                for source_range in token.artifact_ranges:
                    range_key = _range_key(source_range)
                    if range_key in source_ranges:
                        msg = "surface document source ranges must be globally unique"
                        raise ValueError(msg)
                    source_ranges.add(range_key)
                locations[token.token_id] = token
    return locations


def _select_round_evidence(
    continuation: PgdpContinuation,
    token_locations: Mapping[str, MatchToken],
) -> PgdpRoundContinuationEvidence | None:
    """Select exactly one evidence record whose physical token IDs are present."""
    selected: list[PgdpRoundContinuationEvidence] = []
    for evidence in continuation.round_evidence:
        evidence_token_ids = {
            evidence.left_fragment.token_id,
            evidence.right_fragment.token_id,
        }
        present_ids = evidence_token_ids & set(token_locations)
        if present_ids and present_ids != evidence_token_ids:
            msg = "continuation evidence only partially matches the surface document"
            raise ValueError(msg)
        if present_ids == evidence_token_ids:
            selected.append(evidence)
    if len(selected) > 1:
        msg = "continuation evidence matches multiple rounds in one surface document"
        raise ValueError(msg)
    return selected[0] if selected else None


def _validate_round_evidence_against_document(
    evidence: PgdpRoundContinuationEvidence,
    token_locations: Mapping[str, MatchToken],
) -> None:
    """Require retained fragments to be exact contiguous document graphemes."""
    for fragment in (evidence.left_fragment, evidence.right_fragment):
        token = token_locations[fragment.token_id]
        token_graphemes = _validated_token_graphemes(token)
        fragment_graphemes = split_graphemes(fragment.text)
        if not _contains_fragment(
            token_graphemes,
            token.artifact_ranges,
            fragment_graphemes,
            fragment.grapheme_ranges,
        ):
            msg = "continuation fragment does not match the surface document"
            raise ValueError(msg)


def _record_marker_ranges(
    evidence: PgdpRoundContinuationEvidence,
    token_locations: Mapping[str, MatchToken],
    marker_ranges_by_token: dict[str, set[bytes]],
) -> None:
    """Record exact marker ranges after proving that each source grapheme is ``*``."""
    range_locations: dict[bytes, tuple[str, str]] = {}
    for token_id, token in token_locations.items():
        for grapheme, source_range in zip(
            _validated_token_graphemes(token), token.artifact_ranges, strict=True
        ):
            range_locations[_range_key(source_range)] = (token_id, grapheme)
    for marker_range in evidence.marker_evidence.marker_ranges:
        marker_key = _range_key(marker_range)
        location = range_locations.get(marker_key)
        if location is None or location[1] != "*":
            msg = "continuation marker does not match the surface document"
            raise ValueError(msg)
        token_id = location[0]
        token_markers = marker_ranges_by_token.setdefault(token_id, set())
        if marker_key in token_markers:
            msg = "surface document has conflicting continuation marker evidence"
            raise ValueError(msg)
        token_markers.add(marker_key)


def _surface_token(token: MatchToken, marker_ranges: set[bytes]) -> MatchToken:
    """Remove selected marker graphemes while preserving token ID and range order."""
    graphemes = _validated_token_graphemes(token)
    retained = tuple(
        (grapheme, source_range)
        for grapheme, source_range in zip(graphemes, token.artifact_ranges, strict=True)
        if _range_key(source_range) not in marker_ranges
    )
    if not retained:
        msg = "surface marker removal would leave an empty physical token"
        raise ValueError(msg)
    return MatchToken(
        token_id=token.token_id,
        text="".join(grapheme for grapheme, _source_range in retained),
        artifact_ranges=tuple(source_range for _grapheme, source_range in retained),
    )


def _validated_token_graphemes(token: MatchToken) -> tuple[str, ...]:
    """Return token graphemes only when every one has an exact source range."""
    graphemes = split_graphemes(token.text)
    if len(graphemes) != len(token.artifact_ranges):
        msg = "surface document tokens require one source range per grapheme"
        raise ValueError(msg)
    return graphemes


def _contains_fragment(
    token_graphemes: tuple[str, ...],
    token_ranges: tuple[ArtifactRange, ...],
    fragment_graphemes: tuple[str, ...],
    fragment_ranges: tuple[ArtifactRange, ...],
) -> bool:
    """Return whether one fragment is an exact contiguous token subsequence."""
    fragment_length = len(fragment_graphemes)
    if fragment_length == 0 or fragment_length != len(fragment_ranges):
        return False
    for start in range(len(token_graphemes) - fragment_length + 1):
        end = start + fragment_length
        if (
            token_graphemes[start:end] == fragment_graphemes
            and token_ranges[start:end] == fragment_ranges
        ):
            return True
    return False


def _range_key(source_range: ArtifactRange) -> bytes:
    """Return a collision-free immutable key for one exact source range."""
    return source_range.to_json_bytes()


def _decode_round(
    round_: PgdpRound, document: MatchDocument
) -> tuple[tuple[_RoundEdge, ...], tuple[PgdpQuarantinedMarker, ...]]:
    tokens = _located_tokens(round_, document)
    edges: list[_UnanchoredRoundEdge] = []
    quarantined: list[PgdpQuarantinedMarker] = []
    consumed_leading_locations: set[tuple[int, int]] = set()
    for token_position, located in enumerate(tokens):
        graphemes = split_graphemes(located.token.text)
        for marker_index, grapheme in enumerate(graphemes):
            if grapheme != "*":
                continue
            marker = _marker_evidence(located, marker_index)
            if marker is None:
                quarantined.append(
                    _quarantined_marker(
                        round_,
                        located,
                        marker_index,
                        PgdpContinuationQuarantineReason.SOURCE_RANGE_MISMATCH,
                    )
                )
                continue
            if 0 < marker_index < len(graphemes) - 1:
                edge = _inline_edge(located, marker_index, marker)
                if edge is None:
                    quarantined.append(
                        _quarantined_marker(
                            round_,
                            located,
                            marker_index,
                            PgdpContinuationQuarantineReason.EMPTY_FRAGMENT,
                        )
                    )
                else:
                    edges.append(edge)
                continue
            if marker_index == len(graphemes) - 1:
                edge, marker_quarantine, consumed_leading = _trailing_edge(
                    tokens, token_position, located, marker_index, marker
                )
                if edge is not None:
                    edges.append(edge)
                if marker_quarantine is not None:
                    quarantined.append(marker_quarantine)
                if consumed_leading is not None:
                    consumed_leading_locations.add(consumed_leading)
                continue
            marker_location = (token_position, marker_index)
            if marker_location in consumed_leading_locations:
                continue
            edge, marker_quarantine = _leading_edge(
                tokens, token_position, located, marker_index, marker
            )
            if edge is not None:
                edges.append(edge)
            if marker_quarantine is not None:
                quarantined.append(marker_quarantine)
    return _assign_boundary_ordinals(edges), tuple(quarantined)


def _located_tokens(
    round_: PgdpRound, document: MatchDocument
) -> tuple[_LocatedToken, ...]:
    tokens: list[_LocatedToken] = []
    document_index = 0
    for page_index, page in enumerate(document.pages):
        for line_index, line in enumerate(page.lines):
            for token_index, token in enumerate(line.tokens):
                tokens.append(
                    _LocatedToken(
                        round=round_,
                        token=token,
                        page_id=page.page_id,
                        page_index=page_index,
                        line_id=line.line_id,
                        line_index=line_index,
                        token_index=token_index,
                        document_index=document_index,
                        grapheme_ranges=_token_grapheme_ranges(token),
                    )
                )
                document_index += 1
    return tuple(tokens)


def _token_grapheme_ranges(token: MatchToken) -> tuple[ArtifactRange, ...] | None:
    graphemes = split_graphemes(token.text)
    if len(token.artifact_ranges) != len(graphemes):
        return None
    if any(
        source_range.grapheme_end - source_range.grapheme_start != 1
        for source_range in token.artifact_ranges
    ):
        return None
    return token.artifact_ranges


def _marker_evidence(
    located: _LocatedToken, marker_index: int
) -> PgdpMarkerEvidence | None:
    ranges = located.grapheme_ranges
    if ranges is None:
        return None
    return PgdpMarkerEvidence(
        round=located.round,
        marker_ranges=(ranges[marker_index],),
    )


def _inline_edge(
    located: _LocatedToken, marker_index: int, marker: PgdpMarkerEvidence
) -> _UnanchoredRoundEdge | None:
    left = _fragment(located, 0, marker_index)
    right = _fragment(located, marker_index + 1, None)
    if left is None or right is None:
        return None
    boundary = PgdpContinuationBoundary.SAME_LINE
    return _round_edge(
        left,
        right,
        boundary,
        marker,
    )


def _trailing_edge(
    tokens: tuple[_LocatedToken, ...],
    token_position: int,
    located: _LocatedToken,
    marker_index: int,
    marker: PgdpMarkerEvidence,
) -> tuple[
    _UnanchoredRoundEdge | None,
    PgdpQuarantinedMarker | None,
    tuple[int, int] | None,
]:
    left = _fragment(located, 0, marker_index)
    if left is None:
        return (
            None,
            _quarantined_marker(
                located.round,
                located,
                marker_index,
                PgdpContinuationQuarantineReason.EMPTY_FRAGMENT,
            ),
            None,
        )
    if token_position + 1 == len(tokens):
        return (
            None,
            _quarantined_marker(
                located.round,
                located,
                marker_index,
                PgdpContinuationQuarantineReason.ORPHAN_TRAILING_MARKER,
            ),
            None,
        )
    next_token = tokens[token_position + 1]
    boundary = _boundary_between(located, next_token)
    if boundary is None:
        return (
            None,
            _quarantined_marker(
                located.round,
                located,
                marker_index,
                PgdpContinuationQuarantineReason.NONADJACENT_MARKERS,
            ),
            None,
        )
    next_graphemes = split_graphemes(next_token.token.text)
    next_starts_marker = bool(next_graphemes) and next_graphemes[0] == "*"
    right_start = 1 if next_starts_marker else 0
    right = _fragment(next_token, right_start, None)
    if right is None:
        return (
            None,
            _quarantined_marker(
                located.round,
                located,
                marker_index,
                PgdpContinuationQuarantineReason.EMPTY_FRAGMENT,
            ),
            None,
        )
    marker_evidence = marker
    consumed_leading: tuple[int, int] | None = None
    if next_starts_marker:
        next_marker = _marker_evidence(next_token, 0)
        if next_marker is None:
            return (
                None,
                _quarantined_marker(
                    located.round,
                    next_token,
                    0,
                    PgdpContinuationQuarantineReason.SOURCE_RANGE_MISMATCH,
                ),
                None,
            )
        marker_evidence = PgdpMarkerEvidence(
            round=located.round,
            marker_ranges=marker.marker_ranges + next_marker.marker_ranges,
        )
        consumed_leading = (token_position + 1, 0)
    return (
        _round_edge(
            left,
            right,
            boundary,
            marker_evidence,
        ),
        None,
        consumed_leading,
    )


def _leading_edge(
    tokens: tuple[_LocatedToken, ...],
    token_position: int,
    located: _LocatedToken,
    marker_index: int,
    marker: PgdpMarkerEvidence,
) -> tuple[_UnanchoredRoundEdge | None, PgdpQuarantinedMarker | None]:
    if token_position == 0:
        return (
            None,
            _quarantined_marker(
                located.round,
                located,
                marker_index,
                PgdpContinuationQuarantineReason.ORPHAN_LEADING_MARKER,
            ),
        )
    previous = tokens[token_position - 1]
    boundary = _boundary_between(previous, located)
    if boundary is None:
        return (
            None,
            _quarantined_marker(
                located.round,
                located,
                marker_index,
                PgdpContinuationQuarantineReason.NONADJACENT_MARKERS,
            ),
        )
    left = _fragment(previous, 0, None)
    right = _fragment(located, marker_index + 1, None)
    if left is None or right is None:
        return (
            None,
            _quarantined_marker(
                located.round,
                located,
                marker_index,
                PgdpContinuationQuarantineReason.EMPTY_FRAGMENT,
            ),
        )
    return (
        _round_edge(
            left,
            right,
            boundary,
            marker,
        ),
        None,
    )


def _fragment(
    located: _LocatedToken, start: int, end: int | None
) -> PgdpPhysicalFragment | None:
    ranges = located.grapheme_ranges
    if ranges is None:
        return None
    graphemes = split_graphemes(located.token.text)
    selected_graphemes = graphemes[start:end]
    selected_ranges = ranges[start:end]
    if not selected_graphemes:
        return None
    return PgdpPhysicalFragment(
        text="".join(selected_graphemes),
        token_id=located.token.token_id,
        page_id=located.page_id,
        line_id=located.line_id,
        grapheme_ranges=selected_ranges,
    )


def _round_edge(
    left: PgdpPhysicalFragment,
    right: PgdpPhysicalFragment,
    boundary: PgdpContinuationBoundary,
    marker: PgdpMarkerEvidence,
) -> _UnanchoredRoundEdge:
    candidates, decision = _logical_candidates(left.text, right.text)
    continuation = PgdpContinuation(
        left_fragment=left,
        right_fragment=right,
        boundary=boundary,
        marker_evidence=(marker,),
        round_evidence=(
            PgdpRoundContinuationEvidence(
                round=marker.round,
                left_fragment=left,
                right_fragment=right,
                marker_evidence=marker,
            ),
        ),
        logical_candidates=candidates,
        decision=decision,
    )
    return _UnanchoredRoundEdge(
        continuation=continuation,
        locus=_boundary_locus(left, right, boundary),
    )


def _boundary_locus(
    left: PgdpPhysicalFragment,
    right: PgdpPhysicalFragment,
    boundary: PgdpContinuationBoundary,
) -> _BoundaryLocus:
    return _BoundaryLocus(
        left_page_id=left.page_id,
        left_line_id=left.line_id,
        right_page_id=right.page_id,
        right_line_id=right.line_id,
        boundary=boundary,
    )


def _assign_boundary_ordinals(
    edges: list[_UnanchoredRoundEdge],
) -> tuple[_RoundEdge, ...]:
    ordinals: dict[_BoundaryLocus, int] = {}
    anchored_edges: list[_RoundEdge] = []
    for edge in edges:
        ordinal = ordinals.get(edge.locus, 0)
        anchored_edges.append(
            _RoundEdge(
                continuation=edge.continuation,
                anchor=_EdgeAnchor(
                    locus=edge.locus,
                    continuation_ordinal=ordinal,
                ),
            )
        )
        ordinals[edge.locus] = ordinal + 1
    return tuple(anchored_edges)


def _logical_candidates(
    left: str, right: str
) -> tuple[tuple[PgdpLogicalCandidate, ...], PgdpContinuationDecision]:
    if left.endswith("-") and not left.endswith("--"):
        return (
            (
                PgdpLogicalCandidate(
                    text=left[:-1] + right,
                    decision=PgdpContinuationDecision.JOIN_WITHOUT_HYPHEN,
                ),
                PgdpLogicalCandidate(
                    text=left + right,
                    decision=PgdpContinuationDecision.KEEP_HYPHEN,
                ),
                PgdpLogicalCandidate(
                    text=f"{left} {right}",
                    decision=PgdpContinuationDecision.LEAVE_SEPARATE,
                ),
            ),
            PgdpContinuationDecision.AMBIGUOUS,
        )
    return (
        (
            PgdpLogicalCandidate(
                text=left + right,
                decision=PgdpContinuationDecision.PRESERVE_PUNCTUATION,
            ),
        ),
        PgdpContinuationDecision.PRESERVE_PUNCTUATION,
    )


def _boundary_between(
    left: _LocatedToken, right: _LocatedToken
) -> PgdpContinuationBoundary | None:
    if right.document_index != left.document_index + 1:
        return None
    if left.page_id == right.page_id:
        if left.line_id == right.line_id:
            return PgdpContinuationBoundary.SAME_LINE
        if right.line_index != left.line_index + 1:
            return None
        return PgdpContinuationBoundary.LINE
    if right.page_index != left.page_index + 1:
        return None
    if not _pages_are_consecutive(left.page_id, right.page_id):
        return None
    return PgdpContinuationBoundary.PAGE


def _pages_are_consecutive(left_page_id: str, right_page_id: str) -> bool:
    left_number = _trailing_page_number(left_page_id)
    right_number = _trailing_page_number(right_page_id)
    if left_number is None or right_number is None:
        return True
    return right_number == left_number + 1


def _trailing_page_number(page_id: str) -> int | None:
    digits: list[str] = []
    found_digit = False
    for character in reversed(page_id):
        if character.isdecimal():
            digits.append(character)
            found_digit = True
        elif found_digit:
            break
    if not digits:
        return None
    return int("".join(reversed(digits)))


def _quarantined_marker(
    round_: PgdpRound,
    located: _LocatedToken,
    marker_index: int,
    reason: PgdpContinuationQuarantineReason,
) -> PgdpQuarantinedMarker:
    marker = _marker_evidence(located, marker_index)
    if marker is None:
        return PgdpQuarantinedMarker(
            marker_evidence=None,
            unmapped_marker_evidence=PgdpUnmappedMarkerEvidence(
                round=round_,
                token_id=located.token.token_id,
                page_id=located.page_id,
                line_id=located.line_id,
                marker_grapheme_index=marker_index,
                token_artifact_ranges=located.token.artifact_ranges,
            ),
            reason=reason,
        )
    return PgdpQuarantinedMarker(
        marker_evidence=marker,
        unmapped_marker_evidence=None,
        reason=reason,
    )


def _reconcile_rounds(
    f2_edges: tuple[_RoundEdge, ...], p3_edges: tuple[_RoundEdge, ...]
) -> tuple[PgdpContinuation, ...]:
    unmatched_p3 = list(p3_edges)
    continuations: list[PgdpContinuation] = []
    for f2_edge in f2_edges:
        matching_index = _matching_round_edge_index(f2_edge, unmatched_p3)
        conflicting_index = _conflicting_round_edge_index(f2_edge, unmatched_p3)
        if matching_index is not None:
            p3_edge = unmatched_p3.pop(matching_index)
            continuations.append(
                _merge_round_edges(f2_edge.continuation, p3_edge.continuation)
            )
        elif conflicting_index is not None:
            p3_edge = unmatched_p3.pop(conflicting_index)
            continuations.append(
                _with_quarantine(f2_edge.continuation, p3_edge.continuation)
            )
        else:
            continuations.append(f2_edge.continuation)
    continuations.extend(edge.continuation for edge in unmatched_p3)
    return tuple(continuations)


def _matching_round_edge_index(
    expected: _RoundEdge, candidates: Iterable[_RoundEdge]
) -> int | None:
    for index, candidate in enumerate(candidates):
        if expected.anchor == candidate.anchor and _same_edge(
            expected.continuation, candidate.continuation
        ):
            return index
    return None


def _conflicting_round_edge_index(
    expected: _RoundEdge, candidates: Iterable[_RoundEdge]
) -> int | None:
    for index, candidate in enumerate(candidates):
        if expected.anchor == candidate.anchor:
            return index
    return None


def _same_edge(left: PgdpContinuation, right: PgdpContinuation) -> bool:
    return (
        left.left_fragment.text == right.left_fragment.text
        and left.right_fragment.text == right.right_fragment.text
        and left.boundary is right.boundary
    )


def _merge_round_edges(f2: PgdpContinuation, p3: PgdpContinuation) -> PgdpContinuation:
    return PgdpContinuation(
        left_fragment=f2.left_fragment,
        right_fragment=f2.right_fragment,
        boundary=f2.boundary,
        marker_evidence=f2.marker_evidence + p3.marker_evidence,
        round_evidence=f2.round_evidence + p3.round_evidence,
        logical_candidates=f2.logical_candidates,
        decision=f2.decision,
        quarantine_reasons=f2.quarantine_reasons + p3.quarantine_reasons,
    )


def _with_quarantine(f2: PgdpContinuation, p3: PgdpContinuation) -> PgdpContinuation:
    return PgdpContinuation(
        left_fragment=f2.left_fragment,
        right_fragment=f2.right_fragment,
        boundary=f2.boundary,
        marker_evidence=f2.marker_evidence + p3.marker_evidence,
        round_evidence=f2.round_evidence + p3.round_evidence,
        logical_candidates=f2.logical_candidates,
        decision=f2.decision,
        quarantine_reasons=(PgdpContinuationQuarantineReason.ROUND_CONFLICT,),
    )
