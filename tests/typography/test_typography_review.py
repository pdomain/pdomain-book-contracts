from __future__ import annotations

import datetime as dt
import hashlib
import uuid

import pytest
from pydantic import ValidationError

from pdomain_book_contracts.typography.labels import ConfidenceTier, LabelSource
from pdomain_book_contracts.typography.review import (
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
    canonical_json_bytes,
    make_merged_word_id,
    make_split_word_id,
    make_word_id,
    validate_sha256,
    validate_word_id,
)
from pdomain_book_contracts.typography.spans import GRAPHEME_SEGMENTATION_VERSION

PAGE = "11" * 32
IMAGE = "22" * 32
HEAD = "33" * 32


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _word_id(reading_order: int = 0) -> str:
    return make_word_id(
        project_id="p", page_id="pg", reading_order=reading_order, text="word"
    )


def _taxonomy(*, required: bool = True) -> TypographyTaxonomy:
    return TypographyTaxonomy(
        version="t1",
        labels=(
            TypographyTaxonomyLabel(
                value="italic",
                display_name="Italic",
                required_for_completion=required,
                trainable=True,
            ),
            TypographyTaxonomyLabel(
                value="bold",
                display_name="Bold",
                required_for_completion=False,
                trainable=True,
            ),
        ),
    )


def _span(label: str, start: int, end: int, span_id: str = "s") -> TypographySpan:
    return TypographySpan(
        span_id=span_id,
        label=label,
        start=start,
        end=end,
        label_source=LabelSource.HUMAN,
        confidence_tier=ConfidenceTier.GOLD,
        alignment_evidence_id="ev",
    )


def _word(
    *,
    text: str = "word",
    states: dict[str, LabelState] | None = None,
    spans: tuple[TypographySpan, ...] = (),
    review_state: ReviewState = ReviewState.UNREVIEWED,
    revision: int = 0,
    taxonomy: TypographyTaxonomy | None = None,
) -> WordTypography:
    taxonomy = taxonomy or _taxonomy()
    return WordTypography(
        word_id=_word_id(),
        text=text,
        text_sha256=_sha(text),
        page_content_sha256=PAGE,
        image_artifact_sha256=IMAGE,
        grapheme_map_version=GRAPHEME_SEGMENTATION_VERSION,
        taxonomy_version=taxonomy.version,
        taxonomy_hash=taxonomy.taxonomy_hash,
        label_states=states or {},
        spans=spans,
        source_evidence_ids=("ev",),
        review_state=review_state,
        word_revision=revision,
    )


def test_canonical_json_bytes_is_sorted_compact_and_rejects_nan() -> None:
    assert canonical_json_bytes({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode()
    with pytest.raises(ValueError, match="Out of range"):
        canonical_json_bytes({"x": float("nan")})


def test_validate_sha256_lowercases_and_rejects_bad_digests() -> None:
    assert validate_sha256("AB" * 32, "f") == "ab" * 32
    for bad in ("", "ab" * 31, "xy" * 32):
        with pytest.raises(ValueError, match="f must be a 64-character"):
            validate_sha256(bad, "f")


def test_word_ids_are_stable_uuid5_values_over_the_published_tuple() -> None:
    first = make_word_id(project_id="p", page_id="pg", reading_order=3, text="hi")
    again = make_word_id(project_id="p", page_id="pg", reading_order=3, text="hi")
    assert first == again
    assert uuid.UUID(first).version == 5
    key = '["pdomain.typography.word.v1","p","pg",3,"hi"]'
    assert first == str(uuid.uuid5(WORD_ID_NAMESPACE, key))
    others = {
        make_word_id(project_id="q", page_id="pg", reading_order=3, text="hi"),
        make_word_id(project_id="p", page_id="px", reading_order=3, text="hi"),
        make_word_id(project_id="p", page_id="pg", reading_order=4, text="hi"),
        make_word_id(project_id="p", page_id="pg", reading_order=3, text="ho"),
    }
    assert first not in others
    assert len(others) == 4


@pytest.mark.parametrize(
    ("project_id", "page_id", "reading_order", "message"),
    [
        ("", "pg", 0, "must not be empty"),
        ("p", "", 0, "must not be empty"),
        ("p", "pg", -1, "nonnegative"),
    ],
)
def test_make_word_id_rejects_invalid_inputs(
    project_id: str, page_id: str, reading_order: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        make_word_id(
            project_id=project_id,
            page_id=page_id,
            reading_order=reading_order,
            text="t",
        )


def test_validate_word_id_requires_a_uuid_version_5() -> None:
    word_id = _word_id()
    assert validate_word_id(word_id.upper()) == word_id
    with pytest.raises(ValueError, match="UUIDv5"):
        validate_word_id("not-a-uuid")
    with pytest.raises(ValueError, match="UUIDv5"):
        validate_word_id(str(uuid.uuid4()))


def test_split_word_ids_are_deterministic_and_distinct_per_index() -> None:
    parent = _word_id()
    assert make_split_word_id(parent, split_index=1) == make_split_word_id(
        parent, split_index=1
    )
    assert make_split_word_id(parent, split_index=1) != make_split_word_id(
        parent, split_index=2
    )
    assert make_split_word_id(parent, split_index=0) != parent
    assert make_split_word_id(parent.upper(), split_index=1) == make_split_word_id(
        parent, split_index=1
    )


def test_split_word_id_rejects_negative_index_and_bad_parent() -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        make_split_word_id(_word_id(), split_index=-1)
    with pytest.raises(ValueError, match="UUIDv5"):
        make_split_word_id("bogus", split_index=0)


def test_merged_word_id_depends_on_order_and_needs_two_parents() -> None:
    a, b = _word_id(0), _word_id(1)
    assert make_merged_word_id([a, b]) == make_merged_word_id((a, b))
    assert make_merged_word_id([a, b]) != make_merged_word_id([b, a])
    with pytest.raises(ValueError, match="at least two"):
        make_merged_word_id([a])
    with pytest.raises(ValueError, match="UUIDv5"):
        make_merged_word_id([a, "nope"])


def test_taxonomy_hash_is_derived_and_changes_with_order_and_version() -> None:
    taxonomy = _taxonomy()
    assert len(taxonomy.taxonomy_hash) == 64
    reversed_labels = TypographyTaxonomy(
        version="t1", labels=tuple(reversed(taxonomy.labels))
    )
    assert reversed_labels.taxonomy_hash != taxonomy.taxonomy_hash
    assert TypographyTaxonomy(version="t2", labels=taxonomy.labels).taxonomy_hash != (
        taxonomy.taxonomy_hash
    )
    assert taxonomy.label_values() == ("italic", "bold")


def test_taxonomy_round_trips_and_rejects_a_stale_hash() -> None:
    taxonomy = _taxonomy()
    assert TypographyTaxonomy.from_json_bytes(taxonomy.to_json_bytes()) == taxonomy
    with pytest.raises(ValidationError, match="taxonomy_hash does not match"):
        TypographyTaxonomy(
            version="t1", labels=taxonomy.labels, taxonomy_hash="00" * 32
        )


def test_taxonomy_rejects_duplicate_labels_and_blank_values() -> None:
    label = _taxonomy().labels[0]
    with pytest.raises(ValidationError, match="unique values"):
        TypographyTaxonomy(version="t", labels=(label, label))
    with pytest.raises(ValidationError, match="version must not be empty"):
        TypographyTaxonomy(version=" ", labels=(label,))
    with pytest.raises(ValidationError, match="must not be empty"):
        TypographyTaxonomyLabel(
            value=" ", display_name="x", required_for_completion=True, trainable=True
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"start": 2, "end": 2}, "nonempty half-open"),
        ({"start": 3, "end": 1}, "nonempty half-open"),
        ({"span_id": " "}, "must not be empty"),
        ({"label": ""}, "must not be empty"),
        ({"alignment_evidence_id": ""}, "must not be empty"),
    ],
)
def test_typography_span_rejections(
    overrides: dict[str, str | int], message: str
) -> None:
    payload: dict[str, object] = {
        "span_id": "s",
        "label": "italic",
        "start": 0,
        "end": 1,
        "label_source": "human",
        "confidence_tier": "gold",
        "alignment_evidence_id": "ev",
    }
    with pytest.raises(ValidationError, match=message):
        TypographySpan.model_validate({**payload, **overrides})


def test_review_metadata_requires_a_timezone_and_round_trips() -> None:
    with pytest.raises(ValidationError, match="must include a timezone"):
        TypographyReviewMetadata(
            reviewed_at=dt.datetime.fromisoformat("2026-01-01T00:00:00")
        )
    metadata = TypographyReviewMetadata(
        reviewer_id="r",
        reviewed_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        note="n",
        decision=ReviewDecision.NEEDS_CHANGES,
    )
    assert (
        TypographyReviewMetadata.from_json_bytes(metadata.to_json_bytes()) == metadata
    )


def test_word_without_spans_has_no_whole_word_labels_and_round_trips() -> None:
    word = _word(states={"italic": LabelState.NEGATIVE})
    assert word.whole_word_labels == ()
    assert word.grapheme_count == 4
    restored = WordTypography.from_json_bytes(word.to_json_bytes())
    assert restored == word
    assert restored.label_states["italic"] is LabelState.NEGATIVE


def test_label_states_are_serialized_as_plain_strings() -> None:
    word = _word(states={"italic": LabelState.UNKNOWN})
    assert b'"label_states":{"italic":"unknown"}' in word.to_json_bytes()


def test_whole_word_labels_derive_from_spans_that_cover_every_grapheme() -> None:
    word = _word(
        states={"italic": LabelState.POSITIVE, "bold": LabelState.POSITIVE},
        spans=(
            _span("italic", 2, 4, "b"),
            _span("italic", 0, 2, "a"),
            _span("bold", 0, 3, "c"),
        ),
    )
    assert word.whole_word_labels == ("italic",)


def test_a_gap_between_same_label_spans_is_not_whole_word_coverage() -> None:
    word = _word(
        states={"italic": LabelState.POSITIVE},
        spans=(_span("italic", 0, 1, "a"), _span("italic", 2, 4, "b")),
    )
    assert word.whole_word_labels == ()


def test_empty_text_never_counts_as_whole_word_covered() -> None:
    word = _word(text="", states={"italic": LabelState.NEGATIVE})
    assert word.grapheme_count == 0
    assert word.whole_word_labels == ()


def test_supplied_whole_word_labels_must_match_the_derived_ones() -> None:
    word = _word(states={"italic": LabelState.POSITIVE}, spans=(_span("italic", 0, 4),))
    payload = word.model_dump(mode="json")
    assert WordTypography.model_validate(payload).whole_word_labels == ("italic",)
    payload["whole_word_labels"] = ["bold"]
    with pytest.raises(ValidationError, match="derived full-word positive labels"):
        WordTypography.model_validate(payload)


def test_a_span_past_the_end_of_the_text_is_rejected() -> None:
    with pytest.raises(ValidationError, match="cannot exceed the word grapheme count"):
        _word(states={"italic": LabelState.POSITIVE}, spans=(_span("italic", 0, 5),))


def test_grapheme_clusters_not_code_points_bound_span_ends() -> None:
    text = "e\u0301x"
    assert _word(
        text=text, states={"bold": LabelState.POSITIVE}, spans=(_span("bold", 0, 2),)
    ).whole_word_labels == ("bold",)
    with pytest.raises(ValidationError, match="cannot exceed"):
        _word(
            text=text,
            states={"bold": LabelState.POSITIVE},
            spans=(_span("bold", 0, 3),),
        )


def test_a_span_needs_a_positive_state_and_a_positive_state_needs_a_span() -> None:
    with pytest.raises(ValidationError, match="matching positive label state"):
        _word(states={"italic": LabelState.NEGATIVE}, spans=(_span("italic", 0, 1),))
    with pytest.raises(ValidationError, match="matching positive label state"):
        _word(spans=(_span("italic", 0, 1),))
    with pytest.raises(ValidationError, match="requires a positive typography span"):
        _word(states={"italic": LabelState.POSITIVE})


def test_span_ids_must_be_unique_within_a_word() -> None:
    with pytest.raises(ValidationError, match="span IDs must be unique"):
        _word(
            states={"italic": LabelState.POSITIVE},
            spans=(_span("italic", 0, 1, "x"), _span("italic", 2, 3, "x")),
        )


def test_text_hash_must_match_the_text() -> None:
    payload = _word().model_dump(mode="json")
    payload["text"] = "other"
    with pytest.raises(ValidationError, match="text_sha256 does not match text"):
        WordTypography.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("word_id", "bogus", "UUIDv5"),
        ("page_content_sha256", "zz", "64-character"),
        ("grapheme_map_version", "other", "segmentation version"),
        ("source_evidence_ids", [], "nonempty and unique"),
        ("source_evidence_ids", ["a", "a"], "nonempty and unique"),
        ("source_evidence_ids", [" "], "nonempty and unique"),
        ("taxonomy_version", " ", "must not be empty"),
        ("label_states", {" ": "negative"}, "must not be empty"),
        ("label_states", {"italic": "maybe"}, "label_states"),
    ],
)
def test_word_field_rejections(field: str, value: object, message: str) -> None:
    payload = _word().model_dump(mode="json")
    payload[field] = value
    with pytest.raises(ValidationError, match=message):
        WordTypography.model_validate(payload)


def test_label_states_are_exposed_as_a_read_only_mapping() -> None:
    word = _word(states={"italic": LabelState.NEGATIVE})
    assert not hasattr(word.label_states, "__setitem__")


def test_validate_taxonomy_rejects_a_different_taxonomy_identity() -> None:
    word = _word()
    other = TypographyTaxonomy(version="t2", labels=_taxonomy().labels)
    with pytest.raises(ValueError, match="version or hash does not match"):
        word.validate_taxonomy(other)


def test_validate_taxonomy_rejects_labels_outside_the_taxonomy() -> None:
    taxonomy = _taxonomy()
    word = _word(states={"underline": LabelState.NEGATIVE})
    with pytest.raises(ValueError, match="absent from taxonomy"):
        word.validate_taxonomy(taxonomy)
    span_word = _word(
        states={"underline": LabelState.POSITIVE}, spans=(_span("underline", 0, 1),)
    )
    with pytest.raises(ValueError, match="absent from taxonomy"):
        span_word.validate_taxonomy(taxonomy)


def test_reviewed_word_cannot_leave_a_required_label_unknown() -> None:
    taxonomy = _taxonomy()
    with pytest.raises(ValueError, match="unknown required taxonomy labels"):
        _word(review_state=ReviewState.REVIEWED).validate_taxonomy(taxonomy)
    unreviewed = _word(review_state=ReviewState.UNREVIEWED)
    unreviewed.validate_taxonomy(taxonomy)
    _word(
        review_state=ReviewState.REVIEWED, states={"italic": LabelState.NEGATIVE}
    ).validate_taxonomy(taxonomy)


def test_reviewed_regular_requires_every_required_label_negative() -> None:
    taxonomy = _taxonomy()
    positive = _word(
        review_state=ReviewState.REVIEWED_REGULAR,
        states={"italic": LabelState.POSITIVE},
        spans=(_span("italic", 0, 1),),
    )
    with pytest.raises(ValueError, match="requires negative required"):
        positive.validate_taxonomy(taxonomy)
    _word(
        review_state=ReviewState.REVIEWED_REGULAR,
        states={"italic": LabelState.NEGATIVE},
    ).validate_taxonomy(taxonomy)


def test_missing_required_labels_ignores_optional_and_known_labels() -> None:
    taxonomy = _taxonomy()
    assert _word().missing_required_labels(taxonomy) == ("italic",)
    assert _word(states={"italic": LabelState.UNKNOWN}).missing_required_labels(
        taxonomy
    ) == ("italic",)
    assert (
        _word(states={"italic": LabelState.NEGATIVE}).missing_required_labels(taxonomy)
        == ()
    )
    optional = _taxonomy(required=False)
    word = _word(taxonomy=optional)
    assert word.missing_required_labels(optional) == ()


def test_is_complete_needs_a_reviewed_state_and_no_missing_labels() -> None:
    taxonomy = _taxonomy()
    done = {"italic": LabelState.NEGATIVE}
    assert _word(states=done, review_state=ReviewState.REVIEWED).is_complete(taxonomy)
    assert not _word(states=done, review_state=ReviewState.DEFERRED).is_complete(
        taxonomy
    )
    assert not _word(states=done).is_complete(taxonomy)


def _correction(
    decision: CorrectionDecision = CorrectionDecision.REJECT_SOURCE,
    /,
    **overrides: object,
) -> TypographyCorrection:
    payload: dict[str, object] = {
        "correction_id": "c1",
        "word_id": _word_id(),
        "revision": 1,
        "supersedes_id": None,
        "base_page_sha256": PAGE,
        "base_image_sha256": IMAGE,
        "base_text_sha256": _sha("word"),
        "base_word_revision": 0,
        "replacement_text_sha256": None,
        "replacement_page_sha256": None,
        "replacement_image_sha256": None,
        "replacement_page_head_sha256": None,
        "replacement_word_revision": None,
        "taxonomy_version": _taxonomy().version,
        "taxonomy_hash": _taxonomy().taxonomy_hash,
        "grapheme_map_version": GRAPHEME_SEGMENTATION_VERSION,
        "page_head_sha256": HEAD,
        "labeler_id": "lab",
        "decision": decision.value,
        "replacement": None,
    }
    return TypographyCorrection.model_validate({**payload, **overrides})


def _approved(**overrides: object) -> TypographyCorrection:
    replacement = _word(
        states={"italic": LabelState.POSITIVE},
        spans=(_span("italic", 0, 4),),
        revision=1,
    )
    payload: dict[str, object] = {
        "replacement_text_sha256": replacement.text_sha256,
        "replacement_page_sha256": PAGE,
        "replacement_image_sha256": IMAGE,
        "replacement_page_head_sha256": "44" * 32,
        "replacement_word_revision": 1,
        "replacement": replacement.model_dump(mode="json"),
    }
    return _correction(CorrectionDecision.APPROVED_EDIT, **{**payload, **overrides})


def test_rejection_inherits_every_effective_value_from_the_base() -> None:
    correction = _correction()
    assert correction.effective_page_sha256 == PAGE
    assert correction.effective_image_sha256 == IMAGE
    assert correction.effective_text_sha256 == _sha("word")
    assert correction.effective_word_revision == 0
    assert correction.effective_page_head_sha256 == HEAD


def test_approved_edit_exposes_its_replacement_as_the_effective_state() -> None:
    replacement = _word(
        states={"italic": LabelState.POSITIVE},
        spans=(_span("italic", 0, 4),),
        revision=1,
    ).model_dump(mode="json")
    replacement["page_content_sha256"] = "55" * 32
    correction = _approved(replacement_page_sha256="55" * 32, replacement=replacement)
    assert correction.effective_page_sha256 == "55" * 32
    assert correction.effective_page_head_sha256 == "44" * 32
    assert correction.effective_word_revision == 1
    assert correction.effective_image_sha256 == IMAGE


def test_approved_correction_round_trips_through_canonical_json() -> None:
    correction = _approved()
    restored = TypographyCorrection.from_json_bytes(correction.to_json_bytes())
    assert restored == correction
    assert restored.replacement is not None
    assert restored.replacement.whole_word_labels == ("italic",)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"revision": 1, "supersedes_id": "c0"}, "revision 1 must not declare"),
        ({"revision": 2, "supersedes_id": None}, "requires supersedes_id"),
        ({"revision": 2, "supersedes_id": ""}, "requires supersedes_id"),
        ({"revision": 0}, "revision"),
        ({"correction_id": " "}, "must not be empty"),
        ({"labeler_id": ""}, "must not be empty"),
        ({"word_id": "bogus"}, "UUIDv5"),
        ({"grapheme_map_version": "v0"}, "segmentation version"),
        ({"base_page_sha256": "xx"}, "64-character"),
        ({"replacement_text_sha256": "xx"}, "64-character"),
    ],
)
def test_correction_field_and_revision_rejections(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _correction(**overrides)


@pytest.mark.parametrize(
    "decision",
    [
        CorrectionDecision.APPROVED_EDIT,
        CorrectionDecision.ACCEPT,
        CorrectionDecision.REVIEWED_REGULAR,
    ],
)
def test_accepting_decisions_require_a_replacement(
    decision: CorrectionDecision,
) -> None:
    with pytest.raises(
        ValidationError, match="accepted correction requires replacement"
    ):
        _correction(decision)


@pytest.mark.parametrize(
    "decision",
    [
        CorrectionDecision.REJECT_SOURCE,
        CorrectionDecision.REJECT_ALIGNMENT,
        CorrectionDecision.UNUSABLE_IMAGE,
        CorrectionDecision.DEFER,
    ],
)
def test_rejecting_decisions_must_not_carry_a_replacement(
    decision: CorrectionDecision,
) -> None:
    replacement = _word().model_dump(mode="json")
    with pytest.raises(ValidationError, match="must not carry replacement"):
        _correction(decision, replacement=replacement)


def test_rejecting_decision_must_not_carry_replacement_hashes() -> None:
    with pytest.raises(ValidationError, match="replacement hash or revision"):
        _correction(replacement_page_sha256=PAGE)
    with pytest.raises(ValidationError, match="replacement hash or revision"):
        _correction(replacement_word_revision=1)


def test_accepting_decision_needs_every_replacement_hash_and_revision() -> None:
    for field in (
        "replacement_text_sha256",
        "replacement_page_sha256",
        "replacement_image_sha256",
        "replacement_page_head_sha256",
        "replacement_word_revision",
    ):
        with pytest.raises(ValidationError, match="replacement hash and revision"):
            _approved(**{field: None})


def test_replacement_must_keep_the_correction_word_id() -> None:
    other = _word().model_dump(mode="json")
    other["word_id"] = _word_id(1)
    with pytest.raises(ValidationError, match="word_id must remain stable"):
        _approved(replacement=other)


def test_replacement_revision_must_exceed_the_base_revision() -> None:
    with pytest.raises(ValidationError, match="must exceed the base word revision"):
        _approved(base_word_revision=1)


@pytest.mark.parametrize(
    "overrides",
    [
        {"replacement_text_sha256": "66" * 32},
        {"replacement_page_sha256": "66" * 32},
        {"replacement_image_sha256": "66" * 32},
        {"taxonomy_version": "t9"},
        {"taxonomy_hash": "66" * 32},
    ],
)
def test_replacement_must_agree_with_the_correction_hashes(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="does not match correction hash"):
        _approved(**overrides)
