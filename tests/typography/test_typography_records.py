from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json

import pytest
from pydantic import ValidationError

from pdomain_book_contracts.geometry.bounding_box import BoundingBox
from pdomain_book_contracts.typography.exchange import ArtifactReference
from pdomain_book_contracts.typography.normalization import (
    ComparisonOperation,
    ComparisonOperationKind,
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
    TextIdentity,
    TypographyPageRecord,
)
from pdomain_book_contracts.typography.spans import SourceSlice, StyleSpan

IMAGE_SHA = "cd" * 32
COMMENTS_SHA = "ef" * 32
F2_DOC = b'{"p1":"<i>hi</i>","p2":"other"}'
F2_SHA = hashlib.sha256(F2_DOC).hexdigest()
VALUE = b'"<i>hi</i>"'
VALUE_START = F2_DOC.index(VALUE)
LEXICAL = (VALUE_START, VALUE_START + len(VALUE))
PAGE_TEXT = "<i>hi</i>"
PAGE_HASH = hashlib.sha256(PAGE_TEXT.encode()).hexdigest()
WHEN = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.UTC)


def ref(sha: str, name: str = "a") -> ArtifactRef:
    return ArtifactRef(
        source=ArtifactSource.PGDP_F2,
        source_url=None,
        local_path=f"{name}.json",
        retrieved_at=WHEN,
        sha256=sha,
        version="1",
        license_ref=None,
    )


def slice_at(start: int, end: int, sha: str = F2_SHA) -> SourceSlice:
    return SourceSlice(artifact_sha256=sha, byte_start=start, byte_end=end)


def graphemes(
    text: str = "hi", *, first: int = LEXICAL[0] + 4, sha: str = F2_SHA
) -> list[dict[str, object]]:
    return [
        Grapheme(
            index=i,
            text=char,
            source_slices=(slice_at(first + i, first + i + 1, sha),),
            normalized_from=None,
        ).model_dump(mode="json")
        for i, char in enumerate(text)
    ]


def style_span(**fields: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "label": "italic",
        "start": 0,
        "end": 2,
        "state": "positive",
        "label_source": "f2",
        "confidence_tier": "gold",
        "source_slices": [slice_at(LEXICAL[0] + 1, LEXICAL[1] - 1).model_dump()],
        "rule_ref": None,
        "semantic_reason": None,
        "warnings": [],
    }
    return StyleSpan.model_validate(payload | fields).model_dump(mode="json")


def alignment(**fields: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "alignment_id": "a1",
        "method": "test",
        "source_artifact_sha256": F2_SHA,
        "target_artifact_sha256": IMAGE_SHA,
        "source_coordinate_space": "source_graphemes",
        "target_coordinate_space": "ocr_graphemes",
        "source_range": (0, 2),
        "target_range": (0, 2),
        "operations": ("match",),
        "score": 1.0,
        "margin": None,
        "alternatives": (),
        "accepted": True,
    }
    return AlignmentEvidence.model_validate(payload | fields).model_dump(mode="json")


def token(**fields: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "token_id": "t1",
        "text": "hi",
        "confidence": 0.9,
        "bbox": BoundingBox.from_ltrb(1.0, 2.0, 30.0, 40.0),
        "line_id": "l1",
        "grapheme_start": 0,
        "grapheme_end": 2,
        "alignment_id": "a1",
    }
    return OcrTokenRef.model_validate(payload | fields).model_dump(mode="json")


def identity(*, text_shas: tuple[str, ...] = (F2_SHA,)) -> dict[str, object]:
    return TextIdentity(
        work_id="w",
        edition_id="e",
        book_id="b",
        project_id=None,
        pg_ebook_id=None,
        se_repository=None,
        page_id="p1",
        image_artifact=ref(IMAGE_SHA, "img"),
        text_artifacts=tuple(ref(sha, f"t{i}") for i, sha in enumerate(text_shas)),
    ).model_dump(mode="json")


def record_payload(**fields: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "identity": identity(),
        "original_f2_artifact_base64": base64.b64encode(F2_DOC).decode(),
        "original_f2_artifact_sha256": F2_SHA,
        "f2_page_key": "p1",
        "f2_page_value_lexical_byte_range": LEXICAL,
        "f2_decoded_page_utf8_sha256": PAGE_HASH,
        "parsed_text": "hi",
        "graphemes": graphemes(),
        "ocr_tokens": [token()],
        "style_spans": [style_span()],
        "structural_context": ["body"],
        "parser_warnings": [],
        "alignments": [alignment()],
        "project_comments_artifact": None,
        "guideline_version": "g1",
    }
    return payload | fields


def record(**fields: object) -> TypographyPageRecord:
    return TypographyPageRecord.model_validate(record_payload(**fields))


def external_payload(**fields: object) -> dict[str, object]:
    payload = record_payload(
        schema_version="1.1",
        original_f2_artifact_base64=None,
        external_f2_artifact=ArtifactReference(
            artifact_id="f2", relative_path="f2/F2.json", sha256=F2_SHA
        ).model_dump(mode="json"),
    )
    return payload | fields


def note(**fields: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "raw_text": "[**why?]",
        "page_review_content": "why?",
        "question_status": "question",
        "source_slices": [slice_at(LEXICAL[0] + 1, LEXICAL[0] + 3).model_dump()],
    }
    return ParserNoteEvidence.model_validate(payload | fields).model_dump(mode="json")


def test_artifact_ref_requires_a_timezone_version_and_valid_hash() -> None:
    good = ref(F2_SHA)
    assert ArtifactRef.from_json_bytes(good.to_json_bytes()) == good
    naive = dt.datetime.fromisoformat("2026-01-01T00:00:00")
    with pytest.raises(ValidationError, match="must include a timezone"):
        ArtifactRef.model_validate({**good.model_dump(), "retrieved_at": naive})
    with pytest.raises(ValidationError, match="version must not be empty"):
        ArtifactRef.model_validate({**good.model_dump(), "version": ""})
    assert (
        ArtifactRef.model_validate({**good.model_dump(), "sha256": "AB" * 32}).sha256
        == "ab" * 32
    )
    with pytest.raises(ValidationError, match="sha256 must be a 64-character"):
        ArtifactRef.model_validate({**good.model_dump(), "sha256": "ab"})


def test_grapheme_text_must_be_exactly_one_extended_grapheme() -> None:
    base = graphemes("h")[0]
    assert Grapheme.model_validate({**base, "text": "é"}).text == "é"
    for bad in ("", "ab"):
        with pytest.raises(ValidationError, match="exactly one Unicode extended"):
            Grapheme.model_validate({**base, "text": bad})


def test_note_evidence_needs_a_marker_and_source_slices() -> None:
    assert ParserNoteEvidence.model_validate(note()).question_status is (
        ParserNoteStatus.QUESTION
    )
    with pytest.raises(ValidationError, match="PGDP note marker"):
        note(raw_text="why?")
    with pytest.raises(ValidationError, match="requires source slices"):
        note(source_slices=[])


def test_normalization_evidence_needs_source_slices_and_nonnegative_indices() -> None:
    payload: dict[str, object] = {
        "kind": "letter_space_removed",
        "source_slices": [slice_at(1, 4).model_dump()],
        "replacement_text": "hi",
        "grapheme_indices": [0, 1],
    }
    ok = ParserNormalizationEvidence.model_validate(payload)
    assert ok.kind is ParserNormalizationKind.LETTER_SPACE_REMOVED
    with pytest.raises(ValidationError, match="requires source slices"):
        ParserNormalizationEvidence.model_validate({**payload, "source_slices": []})
    with pytest.raises(ValidationError, match="nonnegative"):
        ParserNormalizationEvidence.model_validate(
            {**payload, "grapheme_indices": [-1]}
        )


def test_control_evidence_needs_a_tag_name_and_source_slices() -> None:
    payload: dict[str, object] = {
        "kind": "unclosed_style_tag",
        "tag_name": "i",
        "raw_text": "<i>",
        "source_slices": [slice_at(1, 4).model_dump()],
    }
    assert (
        ParserControlEvidence.model_validate(payload).kind
        is ParserControlKind.UNCLOSED_STYLE_TAG
    )
    with pytest.raises(ValidationError, match="requires a tag name"):
        ParserControlEvidence.model_validate({**payload, "tag_name": ""})
    with pytest.raises(ValidationError, match="requires source slices"):
        ParserControlEvidence.model_validate({**payload, "source_slices": []})


def test_ocr_token_accepts_a_bounding_box_and_round_trips_it() -> None:
    parsed = OcrTokenRef.model_validate(token())
    restored = OcrTokenRef.from_json_bytes(parsed.to_json_bytes())
    assert restored == parsed
    assert (restored.bbox.minX, restored.bbox.minY) == (1.0, 2.0)
    assert (restored.bbox.maxX, restored.bbox.maxY) == (30.0, 40.0)


def test_ocr_token_rejects_empty_ranges_and_bad_confidence() -> None:
    with pytest.raises(ValidationError, match="OCR token grapheme range"):
        token(grapheme_start=2, grapheme_end=2)
    with pytest.raises(ValidationError, match="nonempty half-open range"):
        token(grapheme_start=-1, grapheme_end=2)
    with pytest.raises(ValidationError):
        token(confidence=1.5)
    assert OcrTokenRef.model_validate(token(confidence=None)).confidence is None


@pytest.mark.parametrize(
    ("kind", "source", "target"),
    [
        ("match", (0, 2), (0, 2)),
        ("substitution", (1, 3), (4, 5)),
        ("source_only_deletion", (0, 1), (2, 2)),
        ("target_only_insertion", (3, 3), (0, 2)),
    ],
)
def test_path_operations_accept_consumption_that_fits_their_kind(
    kind: str, source: tuple[int, int], target: tuple[int, int]
) -> None:
    op = AlignmentPathOperation.model_validate(
        {"kind": kind, "source_range": source, "target_range": target}
    )
    assert AlignmentPathOperation.from_json_bytes(op.to_json_bytes()) == op


@pytest.mark.parametrize(
    ("kind", "source", "target", "message"),
    [
        ("match", (0, 0), (0, 2), "consume both"),
        ("substitution", (0, 2), (1, 1), "consume both"),
        ("source_only_deletion", (0, 1), (0, 1), "consume only source"),
        ("source_only_deletion", (1, 1), (0, 0), "consume only source"),
        ("target_only_insertion", (0, 1), (0, 1), "consume only target"),
        ("target_only_insertion", (0, 0), (2, 2), "consume only target"),
        ("match", (3, 1), (0, 2), "must be ordered"),
        ("match", (0, 2), (5, 4), "must be ordered"),
    ],
)
def test_path_operations_reject_wrong_consumption(
    kind: str, source: tuple[int, int], target: tuple[int, int], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        AlignmentPathOperation.model_validate(
            {"kind": kind, "source_range": source, "target_range": target}
        )


def test_alignment_evidence_round_trips_with_frozen_alternatives() -> None:
    evidence = AlignmentEvidence.model_validate(
        alignment(
            alternatives=[{"score": 0.5, "ops": ["match", {"n": [1, None, True]}]}],
            margin=0.5,
            low_margin_threshold=0.25,
        )
    )
    restored = AlignmentEvidence.from_json_bytes(evidence.to_json_bytes())
    assert restored == evidence
    assert json.loads(evidence.to_json_bytes())["alternatives"] == [
        {"ops": ["match", {"n": [1, None, True]}], "score": 0.5}
    ]
    assert not hasattr(evidence.alternatives[0], "__setitem__")


def op(start: int, end: int) -> dict[str, object]:
    return ComparisonOperation(
        kind=ComparisonOperationKind.QUOTE_EQUIVALENCE,
        input_range=(start, end),
        output_range=(start, end),
        original_text="x",
        transformed_text="y",
    ).model_dump(mode="json")


def path_op(
    kind: str, source: tuple[int, int], target: tuple[int, int]
) -> dict[str, object]:
    return {"kind": kind, "source_range": source, "target_range": target}


def test_alignment_with_normalization_operations_round_trips() -> None:
    evidence = AlignmentEvidence.model_validate(
        alignment(
            source_normalization_operations=[op(0, 1)],
            target_normalization_operations=[op(1, 2)],
            runner_up_operations=[
                path_op("match", (0, 1), (0, 1)),
                path_op("substitution", (1, 2), (1, 2)),
            ],
            runner_up_target_normalization_operations=[op(1, 2)],
        )
    )
    restored = AlignmentEvidence.from_json_bytes(evidence.to_json_bytes())
    assert restored == evidence
    assert restored.runner_up_operations is not None
    assert len(restored.runner_up_operations) == 2


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"source_range": (2, 2)}, "source_range must be a nonempty"),
        ({"target_range": (-1, 2)}, "target_range must be a nonempty"),
        ({"source_artifact_sha256": "xx"}, "source_artifact_sha256 must be"),
        ({"target_artifact_sha256": ""}, "target_artifact_sha256 must be"),
        ({"score": float("nan")}, "score must be finite"),
        ({"score": float("inf")}, "score must be finite"),
        ({"margin": -0.1, "accepted": False}, "margin must be finite and nonneg"),
        ({"margin": float("inf")}, "margin must be finite and nonneg"),
        ({"low_margin_threshold": float("inf")}, "low_margin_threshold must be finite"),
        ({"low_margin_threshold": -1.0}, "low_margin_threshold"),
    ],
)
def test_alignment_scalar_rejections(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        alignment(**overrides)


@pytest.mark.parametrize(
    ("margin", "threshold", "accepted"),
    [(0.1, 0.2, True), (0.3, 0.2, False), (None, 0.5, False), (0.2, 0.2, False)],
)
def test_accepted_must_follow_the_recorded_margin_threshold(
    margin: float | None, threshold: float, accepted: bool
) -> None:
    with pytest.raises(ValidationError, match="accepted must match"):
        alignment(margin=margin, low_margin_threshold=threshold, accepted=accepted)


@pytest.mark.parametrize(
    ("margin", "threshold", "accepted"),
    [(0.2, 0.2, True), (0.1, 0.2, False), (None, 0.5, True), (0.0, 0.0, True)],
)
def test_accepted_flag_accepts_each_consistent_combination(
    margin: float | None, threshold: float, accepted: bool
) -> None:
    built = AlignmentEvidence.model_validate(
        alignment(margin=margin, low_margin_threshold=threshold, accepted=accepted)
    )
    assert built.accepted is accepted


def test_normalization_operations_must_lie_inside_their_evidence_range() -> None:
    with pytest.raises(ValidationError, match="source_normalization_operations"):
        alignment(source_normalization_operations=[op(1, 3)])
    with pytest.raises(ValidationError, match="target_normalization_operations"):
        alignment(
            target_range=(2, 4),
            target_normalization_operations=[op(1, 3)],
        )
    alignment(target_range=(2, 4), target_normalization_operations=[op(2, 4)])


def test_runner_up_operations_must_stay_inside_the_alignment_ranges() -> None:
    with pytest.raises(ValidationError, match="source ranges must lie within"):
        alignment(runner_up_operations=[path_op("match", (0, 3), (0, 1))])
    with pytest.raises(ValidationError, match="target ranges must lie within"):
        alignment(runner_up_operations=[path_op("match", (0, 1), (0, 3))])


def test_runner_up_operations_must_be_monotonic_on_both_sides() -> None:
    with pytest.raises(ValidationError, match="source ranges must be monotonic"):
        alignment(
            runner_up_operations=[
                path_op("match", (1, 2), (0, 1)),
                path_op("match", (0, 1), (1, 2)),
            ]
        )
    with pytest.raises(ValidationError, match="target ranges must be monotonic"):
        alignment(
            runner_up_operations=[
                path_op("match", (0, 1), (1, 2)),
                path_op("match", (1, 2), (0, 1)),
            ]
        )


def test_runner_up_operations_cannot_partially_overlap() -> None:
    with pytest.raises(ValidationError, match="source ranges cannot partially overlap"):
        alignment(
            runner_up_operations=[
                path_op("match", (0, 1), (0, 1)),
                path_op("match", (0, 2), (1, 2)),
            ]
        )
    with pytest.raises(ValidationError, match="target ranges cannot partially overlap"):
        alignment(
            runner_up_operations=[
                path_op("match", (0, 1), (0, 1)),
                path_op("match", (1, 2), (0, 2)),
            ]
        )


def test_runner_up_operations_may_repeat_an_identical_range() -> None:
    built = AlignmentEvidence.model_validate(
        alignment(
            runner_up_operations=[
                path_op("source_only_deletion", (0, 1), (0, 0)),
                path_op("substitution", (0, 1), (0, 1)),
            ]
        )
    )
    assert built.runner_up_operations is not None


def test_runner_up_target_normalization_needs_runner_up_operations() -> None:
    with pytest.raises(ValidationError, match="require runner_up_operations"):
        alignment(runner_up_target_normalization_operations=[op(0, 1)])


def test_runner_up_target_normalization_must_sit_on_a_compared_target_range() -> None:
    ops = [
        path_op("match", (0, 1), (0, 1)),
        path_op("target_only_insertion", (1, 1), (1, 2)),
    ]
    with pytest.raises(ValidationError, match="comparison transition target range"):
        alignment(
            runner_up_operations=ops,
            runner_up_target_normalization_operations=[op(1, 2)],
        )
    with pytest.raises(
        ValidationError, match="runner_up_target_normalization_operations"
    ):
        alignment(
            runner_up_operations=ops,
            runner_up_target_normalization_operations=[op(1, 3)],
        )
    alignment(
        runner_up_operations=ops,
        runner_up_target_normalization_operations=[op(0, 1)],
    )


def test_alternatives_reject_values_outside_json_types() -> None:
    with pytest.raises(ValidationError, match="unsupported alignment alternative"):
        alignment(alternatives=[{"x": {1, 2}}])


def test_embedded_record_round_trips_and_keeps_the_legacy_wire_shape() -> None:
    built = record()
    wire = built.to_json_bytes()
    assert b"external_f2_artifact" not in wire
    assert b'"schema_version":"1.0"' in wire
    restored = TypographyPageRecord.from_json_bytes(wire)
    assert restored == built
    assert restored.schema_version == TYPOGRAPHY_PAGE_RECORD_LEGACY_SCHEMA_VERSION
    assert restored.to_json_bytes() == wire


def test_external_record_round_trips_and_serializes_the_external_reference() -> None:
    built = TypographyPageRecord.model_validate(external_payload())
    wire = built.to_json_bytes()
    assert b'"schema_version":"1.1"' in wire
    assert b'"external_f2_artifact":{' in wire
    assert f'"sha256":"{F2_SHA}"'.encode() in wire
    restored = TypographyPageRecord.from_json_bytes(wire)
    assert restored == built
    assert restored.schema_version == TYPOGRAPHY_PAGE_RECORD_EXTERNAL_F2_SCHEMA_VERSION


def test_record_without_f2_evidence_is_valid_for_human_or_synthetic_text() -> None:
    plain_graphemes = graphemes(sha="aa" * 32)
    built = record(
        original_f2_artifact_base64=None,
        original_f2_artifact_sha256=None,
        f2_page_key=None,
        f2_page_value_lexical_byte_range=None,
        f2_decoded_page_utf8_sha256=None,
        graphemes=plain_graphemes,
        style_spans=[],
        identity=identity(text_shas=("aa" * 32,)),
        alignments=[alignment(source_artifact_sha256="aa" * 32)],
    )
    assert TypographyPageRecord.from_json_bytes(built.to_json_bytes()) == built


def test_model_copy_revalidates_and_converts_model_updates() -> None:
    built = record()
    comments = ref(COMMENTS_SHA, "comments")
    copied = built.model_copy(update={"project_comments_artifact": comments})
    assert copied.project_comments_artifact == comments
    assert built.project_comments_artifact is None
    with pytest.raises(ValidationError, match="reconstruct parsed_text"):
        built.model_copy(update={"parsed_text": "xx"})
    nested = built.model_copy(update={"structural_context": ("a", "b")})
    assert nested.structural_context == ("a", "b")


def test_model_copy_accepts_mappings_lists_and_models_in_updates() -> None:
    built = record()
    copied = built.model_copy(
        update={
            "identity": TextIdentity.model_validate(identity()),
            "parser_warnings": ["w"],
        }
    )
    assert copied.parser_warnings == ("w",)
    assert copied.identity == built.identity


def f2_fields(doc: bytes, key: str, value: bytes) -> dict[str, object]:
    start = doc.index(value)
    return {
        "original_f2_artifact_base64": base64.b64encode(doc).decode(),
        "original_f2_artifact_sha256": hashlib.sha256(doc).hexdigest(),
        "f2_page_key": key,
        "f2_page_value_lexical_byte_range": (start, start + len(value)),
        "f2_decoded_page_utf8_sha256": PAGE_HASH,
        "identity": identity(text_shas=(hashlib.sha256(doc).hexdigest(),)),
    }


def test_schema_version_and_external_reference_must_agree() -> None:
    with pytest.raises(ValidationError, match=r"1\.0 cannot include external"):
        TypographyPageRecord.model_validate(external_payload(schema_version="1.0"))
    with pytest.raises(ValidationError, match=r"1\.1 requires external_f2_artifact"):
        record(schema_version="1.1")
    with pytest.raises(ValidationError):
        record(schema_version="2.0")


def test_f2_lexical_range_must_be_a_nonempty_half_open_range() -> None:
    with pytest.raises(ValidationError, match="f2_page_value_lexical_byte_range"):
        record(f2_page_value_lexical_byte_range=(LEXICAL[0], LEXICAL[0]))


def test_f2_artifact_fields_are_all_present_or_all_absent() -> None:
    with pytest.raises(ValidationError, match="all present or all absent"):
        record(f2_page_key=None)
    with pytest.raises(ValidationError, match="all present or all absent"):
        record(f2_decoded_page_utf8_sha256=None)


def test_artifact_reference_without_page_evidence_is_rejected() -> None:
    cleared = {
        "original_f2_artifact_sha256": None,
        "f2_page_key": None,
        "f2_page_value_lexical_byte_range": None,
        "f2_decoded_page_utf8_sha256": None,
    }
    with pytest.raises(ValidationError, match="require complete F2 page evidence"):
        record(**cleared)
    with pytest.raises(ValidationError, match="require complete F2 page evidence"):
        TypographyPageRecord.model_validate(
            external_payload(**cleared, schema_version="1.1")
        )


def test_parser_evidence_requires_complete_f2_artifact_fields() -> None:
    cleared = {
        "original_f2_artifact_base64": None,
        "original_f2_artifact_sha256": None,
        "f2_page_key": None,
        "f2_page_value_lexical_byte_range": None,
        "f2_decoded_page_utf8_sha256": None,
    }
    with pytest.raises(ValidationError, match="parser evidence requires complete"):
        record(**cleared, parser_notes=[note()])


def test_embedded_and_external_artifacts_are_mutually_exclusive() -> None:
    with pytest.raises(ValidationError, match="mutually exclusive"):
        TypographyPageRecord.model_validate(
            external_payload(
                original_f2_artifact_base64=base64.b64encode(F2_DOC).decode()
            )
        )


def test_page_evidence_requires_an_embedded_or_external_artifact() -> None:
    with pytest.raises(ValidationError, match="requires an embedded or external"):
        record(original_f2_artifact_base64=None)


def test_external_reference_must_match_the_declared_hash_and_text_artifacts() -> None:
    wrong = ArtifactReference(
        artifact_id="f2", relative_path="f2.json", sha256="aa" * 32
    ).model_dump(mode="json")
    with pytest.raises(
        ValidationError, match=r"external_f2_artifact\.sha256 must match"
    ):
        TypographyPageRecord.model_validate(
            external_payload(external_f2_artifact=wrong)
        )
    with pytest.raises(
        ValidationError, match=r"must appear in identity\.text_artifacts"
    ):
        TypographyPageRecord.model_validate(
            external_payload(identity=identity(text_shas=("aa" * 32,)))
        )


def test_embedded_artifact_must_be_valid_base64_and_match_its_hash() -> None:
    with pytest.raises(ValidationError, match="must be valid base64"):
        record(original_f2_artifact_base64="!!!not base64!!!")
    other = base64.b64encode(F2_DOC + b" ").decode()
    with pytest.raises(ValidationError, match="does not match the supplied artifact"):
        record(original_f2_artifact_base64=other)


def test_embedded_artifact_must_appear_in_the_identity_text_artifacts() -> None:
    with pytest.raises(
        ValidationError, match=r"must appear in identity\.text_artifacts"
    ):
        record(identity=identity(text_shas=("aa" * 32,)))


def test_lexical_range_must_stay_inside_the_artifact() -> None:
    with pytest.raises(ValidationError, match="exceeds the F2 artifact"):
        record(f2_page_value_lexical_byte_range=(LEXICAL[0], len(F2_DOC) + 5))


def test_lexical_range_must_cover_a_valid_json_string() -> None:
    with pytest.raises(ValidationError, match="valid JSON string"):
        record(f2_page_value_lexical_byte_range=(LEXICAL[0], LEXICAL[1] - 3))
    doc = b'{"p1":5}'
    with pytest.raises(ValidationError, match="identify a JSON string"):
        record(**f2_fields(doc, "p1", b"5"))


def test_page_key_must_exist_and_own_the_lexical_range() -> None:
    with pytest.raises(ValidationError, match="must identify a page"):
        record(f2_page_key="missing")
    with pytest.raises(ValidationError, match="identify the selected f2_page_key"):
        record(f2_page_key="p2")


def test_decoded_page_hash_must_match_the_lexical_value() -> None:
    with pytest.raises(ValidationError, match="decoded page hash does not match"):
        record(f2_decoded_page_utf8_sha256="aa" * 32)


@pytest.mark.parametrize(
    ("doc", "value", "message"),
    [
        (b'["x"]', b'"x"', "must be a JSON object"),
        (b'{"p1":"x","p1":"y"}', b'"y"', "duplicate page key"),
        (b'{"p1" "x"}', b'"x"', "must be followed by a value"),
        (b'{"p1":"x",}', b'"x"', "trailing comma"),
        (b'{"p1":"x"} []', b'"x"', "trailing data"),
        (b'{"p1":"x"', b'"x"', "valid JSON object"),
    ],
)
def test_malformed_f2_documents_are_rejected(
    doc: bytes, value: bytes, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        record(**f2_fields(doc, "p1", value))


def test_multibyte_text_before_the_page_value_is_measured_in_bytes() -> None:
    doc = '{"café":"a","p1":"<i>hi</i>"}'.encode()
    built = record(
        **f2_fields(doc, "p1", VALUE),
        graphemes=graphemes(
            first=doc.index(VALUE) + 4, sha=hashlib.sha256(doc).hexdigest()
        ),
        style_spans=[],
        alignments=[alignment(source_artifact_sha256=hashlib.sha256(doc).hexdigest())],
    )
    assert built.f2_page_value_lexical_byte_range == (
        doc.index(VALUE),
        doc.index(VALUE) + len(VALUE),
    )


def test_graphemes_must_be_contiguous_and_rebuild_the_parsed_text() -> None:
    skipped = graphemes()
    skipped[1] = {**skipped[1], "index": 2}
    with pytest.raises(ValidationError, match="contiguous and start at zero"):
        record(graphemes=skipped)
    with pytest.raises(ValidationError, match="reconstruct parsed_text exactly"):
        record(parsed_text="ho")


def test_spans_and_normalization_cannot_exceed_the_grapheme_count() -> None:
    with pytest.raises(ValidationError, match="style span end cannot exceed"):
        record(style_spans=[style_span(end=3)])
    evidence = {
        "kind": "letter_space_removed",
        "source_slices": [slice_at(LEXICAL[0] + 1, LEXICAL[0] + 2).model_dump()],
        "replacement_text": "x",
        "grapheme_indices": [2],
    }
    with pytest.raises(ValidationError, match="normalization grapheme indices cannot"):
        record(normalization_operations=[evidence])
    record(normalization_operations=[{**evidence, "grapheme_indices": [1]}])


def test_alignment_ids_must_be_unique_and_referenced_by_tokens() -> None:
    with pytest.raises(ValidationError, match="alignment_id values must be unique"):
        record(alignments=[alignment(), alignment()])
    with pytest.raises(ValidationError, match="must reference a supplied alignment"):
        record(ocr_tokens=[token(alignment_id="ghost")])
    with pytest.raises(ValidationError, match="token grapheme range cannot exceed"):
        record(ocr_tokens=[token(grapheme_end=3)])


def test_f2_backed_slices_must_use_the_f2_hash_and_lexical_range() -> None:
    other_sha = graphemes(sha="aa" * 32)
    with pytest.raises(ValidationError, match="grapheme source slices must use"):
        record(graphemes=other_sha)
    before = graphemes(first=LEXICAL[0] - 2)
    with pytest.raises(ValidationError, match="grapheme source slices must lie within"):
        record(graphemes=before)
    after = graphemes(first=LEXICAL[1] - 1)
    with pytest.raises(ValidationError, match="grapheme source slices must lie within"):
        record(graphemes=after)


def test_f2_backed_style_span_slices_must_use_the_f2_hash_and_lexical_range() -> None:
    wrong_hash = style_span(
        source_slices=[slice_at(LEXICAL[0] + 1, LEXICAL[0] + 3, "aa" * 32).model_dump()]
    )
    with pytest.raises(ValidationError, match="style span source slices must use"):
        record(style_spans=[wrong_hash])
    outside = style_span(source_slices=[slice_at(0, 3).model_dump()])
    with pytest.raises(
        ValidationError, match="style span source slices must lie within"
    ):
        record(style_spans=[outside])


def test_parser_evidence_slices_must_use_the_f2_hash_and_lexical_range() -> None:
    record(parser_notes=[note()])
    wrong = note(
        source_slices=[slice_at(LEXICAL[0] + 1, LEXICAL[0] + 3, "aa" * 32).model_dump()]
    )
    with pytest.raises(ValidationError, match="parser evidence source slices must use"):
        record(parser_notes=[wrong])
    outside = note(source_slices=[slice_at(0, 2).model_dump()])
    with pytest.raises(ValidationError, match="parser evidence source slices must lie"):
        record(parser_notes=[outside])


def test_parser_controls_and_normalizations_are_checked_like_notes() -> None:
    control = {
        "kind": "unclosed_style_tag",
        "tag_name": "i",
        "raw_text": "<i>",
        "source_slices": [slice_at(0, 3).model_dump()],
    }
    with pytest.raises(ValidationError, match="parser evidence source slices must lie"):
        record(parser_controls=[control])
    inside = {
        **control,
        "source_slices": [slice_at(LEXICAL[0] + 1, LEXICAL[0] + 4).model_dump()],
    }
    assert record(parser_controls=[inside]).parser_controls[0].tag_name == "i"


def test_alignment_source_must_be_a_declared_text_artifact() -> None:
    with pytest.raises(ValidationError, match="identify a declared text artifact"):
        record(alignments=[alignment(source_artifact_sha256="aa" * 32)])


def test_raw_byte_alignments_may_name_the_project_comments_artifact() -> None:
    raw = alignment(
        source_artifact_sha256=COMMENTS_SHA, source_coordinate_space="raw_bytes"
    )
    with pytest.raises(ValidationError, match="identify a declared text artifact"):
        record(alignments=[raw])
    comments = ref(COMMENTS_SHA, "comments").model_dump(mode="json")
    built = record(alignments=[raw], project_comments_artifact=comments)
    assert built.alignments[0].source_artifact_sha256 == COMMENTS_SHA
    grapheme_space = alignment(source_artifact_sha256=COMMENTS_SHA)
    with pytest.raises(ValidationError, match="identify a declared text artifact"):
        record(alignments=[grapheme_space], project_comments_artifact=comments)


def test_ocr_alignments_must_target_the_page_image_within_their_counts() -> None:
    with pytest.raises(ValidationError, match="must identify the page image"):
        record(alignments=[alignment(target_artifact_sha256=F2_SHA)])
    with pytest.raises(ValidationError, match="cannot exceed OCR grapheme count"):
        record(alignments=[alignment(target_range=(0, 3))])
    tokens_space = alignment(target_coordinate_space="ocr_tokens", target_range=(0, 1))
    assert record(alignments=[tokens_space]).alignments[0].target_range == (0, 1)
    over = alignment(target_coordinate_space="ocr_tokens", target_range=(0, 2))
    with pytest.raises(ValidationError, match="cannot exceed OCR token count"):
        record(alignments=[over])


def test_page_level_alignments_may_target_any_declared_page_artifact() -> None:
    page_level = alignment(
        target_coordinate_space="target_pages", target_artifact_sha256=F2_SHA
    )
    assert (
        record(alignments=[page_level]).alignments[0].target_artifact_sha256 == F2_SHA
    )
    with pytest.raises(ValidationError, match="identify a declared page artifact"):
        record(
            alignments=[
                alignment(
                    target_coordinate_space="target_pages",
                    target_artifact_sha256="aa" * 32,
                )
            ]
        )


def test_source_grapheme_alignment_range_cannot_exceed_the_page() -> None:
    with pytest.raises(ValidationError, match="cannot exceed page grapheme count"):
        record(alignments=[alignment(source_range=(0, 3))])
    page_space = alignment(source_coordinate_space="source_pages", source_range=(0, 9))
    assert record(alignments=[page_space]).alignments[0].source_range == (0, 9)


def test_external_artifact_bytes_can_be_revalidated_against_the_record() -> None:
    built = TypographyPageRecord.model_validate(external_payload())
    built.revalidate_external_f2_artifact(F2_DOC)


def test_revalidation_rejects_bytes_that_do_not_match() -> None:
    built = TypographyPageRecord.model_validate(external_payload())
    with pytest.raises(ValueError, match="does not match the supplied artifact"):
        built.revalidate_external_f2_artifact(F2_DOC + b" ")
    with pytest.raises(ValueError, match="does not match the supplied artifact"):
        built.revalidate_external_f2_artifact(b"")


def test_revalidation_requires_an_external_reference() -> None:
    with pytest.raises(ValueError, match="require external_f2_artifact"):
        record().revalidate_external_f2_artifact(F2_DOC)


def test_model_copy_without_updates_returns_an_equal_revalidated_record() -> None:
    built = record()
    copied = built.model_copy()
    assert copied == built
    assert copied is not built


def test_model_copy_accepts_plain_mapping_updates() -> None:
    built = record()
    copied = built.model_copy(update={"identity": identity(text_shas=(F2_SHA,))})
    assert copied.identity == built.identity
    with pytest.raises(
        ValidationError, match=r"must appear in identity\.text_artifacts"
    ):
        built.model_copy(update={"identity": identity(text_shas=("aa" * 32,))})


def test_non_string_f2_page_key_is_a_validation_error() -> None:
    doc = b'{1:"x"}'
    fields = f2_fields(doc, "1", b'"x"')
    with pytest.raises(ValidationError, match="F2 page keys must be JSON strings"):
        record(**fields)
