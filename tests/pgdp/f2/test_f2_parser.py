from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime

import pytest

from pdomain_book_contracts.sources.pgdp.f2.parser import F2Parser
from pdomain_book_contracts.sources.pgdp.f2.project_rules import (
    ProjectRule,
    ProjectRuleRegistry,
)
from pdomain_book_contracts.typography.labels import (
    ConfidenceTier,
    KnowledgeState,
    LabelSource,
    StyleLabel,
)
from pdomain_book_contracts.typography.records import (
    ArtifactRef,
    ArtifactSource,
    ParserControlKind,
    ParserNormalizationKind,
    ParserNoteStatus,
    TextIdentity,
    TypographyPageRecord,
)


def _artifact(payload: bytes, source: ArtifactSource) -> ArtifactRef:
    return ArtifactRef(
        source=source,
        source_url=None,
        local_path="fixture/file",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        sha256=hashlib.sha256(payload).hexdigest(),
        version="1",
        license_ref=None,
    )


def _identity(payload: bytes, project_id: str | None = "proj1") -> TextIdentity:
    artifact = _artifact(payload, ArtifactSource.PGDP_F2)
    return TextIdentity(
        work_id="work",
        edition_id="edition",
        book_id="book",
        project_id=project_id,
        pg_ebook_id=None,
        se_repository=None,
        page_id="page",
        image_artifact=artifact,
        text_artifacts=(artifact,),
    )


def _payload(pages: dict[str, str]) -> bytes:
    return json.dumps(pages).encode()


def _parse(
    text: str,
    *,
    parser: F2Parser | None = None,
    project_id: str | None = "proj1",
    comments: bytes | None = None,
) -> TypographyPageRecord:
    payload = _payload({"1.png": text})
    comments_artifact = (
        None if comments is None else _artifact(comments, ArtifactSource.HUMAN)
    )
    return (parser or F2Parser()).parse_page(
        identity=_identity(payload, project_id),
        guideline_version="g1",
        f2_artifact_bytes=payload,
        page_key="1.png",
        project_comments_bytes=comments,
        project_comments_artifact=comments_artifact,
    )


def test_record_carries_the_original_artifact_and_page_locators() -> None:
    payload = _payload({"0.png": "skip", "1.png": "<i>ab</i> c"})
    record = F2Parser().parse_page(
        identity=_identity(payload),
        guideline_version="g1",
        f2_artifact_bytes=payload,
        page_key="1.png",
    )
    encoded = record.original_f2_artifact_base64
    value_range = record.f2_page_value_lexical_byte_range
    assert encoded is not None
    assert value_range is not None
    assert base64.b64decode(encoded) == payload
    assert record.original_f2_artifact_sha256 == hashlib.sha256(payload).hexdigest()
    assert record.f2_page_key == "1.png"
    start, end = value_range
    assert payload[start:end] == b'"<i>ab</i> c"'
    assert (
        record.f2_decoded_page_utf8_sha256 == hashlib.sha256(b"<i>ab</i> c").hexdigest()
    )
    assert record.guideline_version == "g1"
    assert record.parsed_text == "ab c"
    assert [g.text for g in record.graphemes] == ["a", "b", " ", "c"]
    assert [g.index for g in record.graphemes] == [0, 1, 2, 3]
    assert record.project_comments_artifact is None
    assert record.training_eligible


@pytest.mark.parametrize(
    ("tag", "label"),
    [
        ("i", StyleLabel.ITALIC),
        ("b", StyleLabel.BOLD),
        ("g", StyleLabel.LETTER_SPACED),
    ],
)
def test_standard_tags_become_positive_gold_spans_over_graphemes(
    tag: str, label: StyleLabel
) -> None:
    record = _parse(f"x<{tag}>yz</{tag}>w")
    (span,) = record.style_spans
    assert (span.label, span.start, span.end) == (label, 1, 3)
    assert span.state is KnowledgeState.POSITIVE
    assert span.confidence_tier is ConfidenceTier.GOLD
    assert span.label_source is LabelSource.F2
    assert span.rule_ref is None
    assert span.warnings == ()
    assert record.parsed_text == "xyzw"


def test_span_source_slices_cover_open_tag_content_and_close_tag() -> None:
    record = _parse("<i>ab</i>")
    (span,) = record.style_spans
    payload = _payload({"1.png": "<i>ab</i>"})
    raw = b"".join(payload[s.byte_start : s.byte_end] for s in span.source_slices)
    assert raw == b"<i>ab</i>"


def test_nested_styles_get_one_span_each() -> None:
    record = _parse("<i>a<b>b</b>c</i>")
    spans = {s.label: (s.start, s.end) for s in record.style_spans}
    assert spans == {StyleLabel.BOLD: (1, 2), StyleLabel.ITALIC: (0, 3)}
    assert record.training_eligible


def test_empty_style_span_is_dropped() -> None:
    record = _parse("<i></i>x")
    assert record.style_spans == ()
    assert record.parsed_text == "x"


def test_span_boundaries_count_graphemes_not_code_points() -> None:
    record = _parse("é<i>x</i>")
    (span,) = record.style_spans
    assert (span.start, span.end) == (1, 2)


def test_small_caps_records_case_normalization_evidence() -> None:
    record = _parse("<sc>AbC</sc>")
    (span,) = record.style_spans
    assert span.label is StyleLabel.SMALL_CAPS
    assert span.warnings == ("small_caps_case_normalized",)
    assert record.parsed_text == "AbC"
    assert [
        (op.kind, op.replacement_text, op.grapheme_indices)
        for op in record.normalization_operations
    ] == [
        (ParserNormalizationKind.SMALL_CAPS_CASE_NORMALIZED, "a", (0,)),
        (ParserNormalizationKind.SMALL_CAPS_CASE_NORMALIZED, "c", (2,)),
    ]
    assert "small_caps_case_normalized" in record.parser_warnings
    assert record.training_eligible


def test_small_caps_with_only_lowercase_has_no_normalization_evidence() -> None:
    assert _parse("<sc>abc</sc>").normalization_operations == ()


def test_letter_spacing_records_one_operation_per_removed_space() -> None:
    record = _parse("<g>a b c</g>")
    assert record.parsed_text == "abc"
    assert [op.kind for op in record.normalization_operations] == [
        ParserNormalizationKind.LETTER_SPACE_REMOVED
    ] * 2
    assert [op.replacement_text for op in record.normalization_operations] == ["", ""]
    assert record.parser_warnings == ("letter_space_removed",)
    (span,) = record.style_spans
    assert (span.label, span.start, span.end) == (StyleLabel.LETTER_SPACED, 0, 3)
    assert record.training_eligible


def test_scripts_become_spans_over_their_visible_content() -> None:
    record = _parse("x^{23}y_{n}")
    assert record.parsed_text == "x23yn"
    assert [(s.label, s.start, s.end) for s in record.style_spans] == [
        (StyleLabel.SUPERSCRIPT, 1, 3),
        (StyleLabel.SUBSCRIPT, 4, 5),
    ]
    assert all(s.confidence_tier is ConfidenceTier.GOLD for s in record.style_spans)


def test_script_inside_a_style_keeps_the_outer_span_covering_it() -> None:
    record = _parse("<i>a^2b</i>c")
    by_label = {s.label: (s.start, s.end) for s in record.style_spans}
    assert by_label == {StyleLabel.SUPERSCRIPT: (1, 2), StyleLabel.ITALIC: (0, 3)}


def test_unlabelled_font_and_underline_tags_are_quarantined() -> None:
    font = _parse("<f>x</f>")
    (font_span,) = font.style_spans
    assert font_span.label is StyleLabel.FONT_OTHER_REVIEWED
    assert font_span.state is KnowledgeState.UNKNOWN
    assert font_span.confidence_tier is ConfidenceTier.QUARANTINE
    assert font.parser_warnings == ("ambiguous_font_change",)
    assert not font.training_eligible

    underline = _parse("<u>x</u>")
    (underline_span,) = underline.style_spans
    assert underline_span.label is StyleLabel.UNDERLINE
    assert underline_span.state is KnowledgeState.UNKNOWN
    assert underline.parser_warnings == ("unapproved_underline",)
    assert not underline.training_eligible


def _blackletter_registry(comments: bytes) -> ProjectRuleRegistry:
    return ProjectRuleRegistry(
        [
            ProjectRule(
                project_id="proj1",
                project_comments_sha256=hashlib.sha256(comments).hexdigest(),
                tag_name="f",
                label=StyleLabel.FONT_BLACKLETTER,
                rule_ref="proj1-f-blackletter",
            )
        ]
    )


def test_reviewed_project_rule_resolves_font_tag_to_gold_label() -> None:
    comments = b"<f> means blackletter"
    record = _parse(
        "<f>x</f>",
        parser=F2Parser(_blackletter_registry(comments)),
        comments=comments,
    )
    (span,) = record.style_spans
    assert span.label is StyleLabel.FONT_BLACKLETTER
    assert span.state is KnowledgeState.POSITIVE
    assert span.confidence_tier is ConfidenceTier.GOLD
    assert span.rule_ref == "proj1-f-blackletter"
    assert record.parser_warnings == ()
    assert record.training_eligible
    assert record.project_comments_artifact is not None
    assert (
        record.project_comments_artifact.sha256 == hashlib.sha256(comments).hexdigest()
    )


def test_project_rule_does_not_apply_to_other_comments_or_projects() -> None:
    registry = _blackletter_registry(b"<f> means blackletter")
    changed = _parse("<f>x</f>", parser=F2Parser(registry), comments=b"edited")
    assert changed.style_spans[0].label is StyleLabel.FONT_OTHER_REVIEWED
    assert not changed.training_eligible

    other_project = _parse(
        "<f>x</f>",
        parser=F2Parser(registry),
        project_id="proj2",
        comments=b"<f> means blackletter",
    )
    assert other_project.style_spans[0].label is StyleLabel.FONT_OTHER_REVIEWED

    no_project = _parse(
        "<f>x</f>",
        parser=F2Parser(registry),
        project_id=None,
        comments=b"<f> means blackletter",
    )
    assert no_project.style_spans[0].confidence_tier is ConfidenceTier.QUARANTINE


def test_unclosed_style_tag_is_reported_as_a_control_without_a_span() -> None:
    record = _parse("a<i>b")
    assert record.style_spans == ()
    assert record.parsed_text == "ab"
    (control,) = record.parser_controls
    assert control.kind is ParserControlKind.UNCLOSED_STYLE_TAG
    assert (control.tag_name, control.raw_text) == ("i", "<i>")
    assert record.parser_warnings == ("unclosed_tag",)
    assert not record.training_eligible


def test_unclosed_quarantined_tag_adds_its_own_warning_first() -> None:
    record = _parse("<u>x")
    assert record.parser_warnings == ("unclosed_tag", "unapproved_underline")
    assert record.parser_controls[0].tag_name == "u"


def test_mismatched_close_tag_leaves_outer_style_unclosed() -> None:
    record = _parse("<i>x</b>")
    assert record.style_spans == ()
    assert record.parser_warnings == ("mismatched_close_tag", "unclosed_tag")
    assert [c.tag_name for c in record.parser_controls] == ["i"]


def test_notes_are_hidden_and_classified_as_question_or_comment() -> None:
    record = _parse("[**why?] a [**ok] b")
    assert record.parsed_text == " a  b"
    assert [
        (n.page_review_content, n.question_status) for n in record.parser_notes
    ] == [
        ("why?", ParserNoteStatus.QUESTION),
        ("ok", ParserNoteStatus.COMMENT),
    ]
    assert record.parser_notes[0].raw_text == "[**why?]"
    assert record.parser_warnings == ("note_quarantine",)
    assert not record.training_eligible


def test_note_between_styled_text_does_not_shift_span_offsets() -> None:
    record = _parse("a[**n]<i>b</i>")
    (span,) = record.style_spans
    assert (span.start, span.end) == (1, 2)
    assert record.parsed_text == "ab"


def test_unclosed_note_is_hidden_and_recorded_with_its_text() -> None:
    record = _parse("a [**unclosed?")
    assert record.parsed_text == "a "
    (note,) = record.parser_notes
    assert note.page_review_content == "unclosed?"
    assert note.question_status is ParserNoteStatus.QUESTION
    assert record.parser_warnings == ("unclosed_note", "note_quarantine")
    assert not record.training_eligible


def test_blocks_set_structural_context_in_order_of_first_use() -> None:
    record = _parse("/#a#/ /*b*/")
    assert record.structural_context == ("display_block", "formatted_block")
    assert record.parsed_text == "a b"
    assert record.training_eligible


def test_repeated_blocks_report_context_once() -> None:
    record = _parse("/*a*/ /*b*/")
    assert record.structural_context == ("formatted_block",)


def test_unclosed_block_warns() -> None:
    record = _parse("/*a")
    assert record.structural_context == ("formatted_block",)
    assert record.parser_warnings == ("unclosed_block",)
    assert not record.training_eligible


def test_close_without_open_is_unmatched() -> None:
    record = _parse("a*/")
    assert record.structural_context == ()
    assert record.parser_warnings == ("unmatched_block",)


def test_close_of_the_wrong_kind_is_crossed_and_leaves_block_open() -> None:
    record = _parse("/*a#/")
    assert record.parser_warnings == ("crossed_block", "unclosed_block")


def test_unknown_markup_stays_visible_and_blocks_training() -> None:
    record = _parse("<foo>x")
    assert record.parsed_text == "<foo>x"
    assert record.parser_warnings == ("unknown_construct", "unclosed_unknown_tag")
    assert not record.training_eligible


def test_tb_and_structural_tags_leave_text_and_spans_unaffected() -> None:
    record = _parse("a<tb><table><tr><td><i>b</i></td></tr></table>")
    assert record.parsed_text == "ab"
    assert [(s.label, s.start, s.end) for s in record.style_spans] == [
        (StyleLabel.ITALIC, 1, 2)
    ]
    assert record.parser_warnings == ()


def _parse_key(parser: F2Parser, payload: bytes, key: str) -> TypographyPageRecord:
    return parser.parse_page(
        identity=_identity(payload),
        guideline_version="g1",
        f2_artifact_bytes=payload,
        page_key=key,
    )


def test_parsing_twice_gives_identical_records() -> None:
    parser = F2Parser()
    payload = _payload({"1.png": "<i>a</i>", "2.png": "b"})
    first = _parse_key(parser, payload, "1.png")
    again = _parse_key(parser, payload, "1.png")
    other = _parse_key(parser, payload, "2.png")
    assert first == again
    assert other.parsed_text == "b"
    assert other.f2_page_key == "2.png"


def test_small_index_cache_still_parses_alternating_artifacts_correctly() -> None:
    parser = F2Parser(document_cache_size=1)
    first_payload = _payload({"p": "<i>a</i>"})
    second_payload = _payload({"p": "<b>b</b>"})
    for payload, label in [
        (first_payload, StyleLabel.ITALIC),
        (second_payload, StyleLabel.BOLD),
        (first_payload, StyleLabel.ITALIC),
        (second_payload, StyleLabel.BOLD),
    ]:
        record = parser.parse_page(
            identity=_identity(payload),
            guideline_version="g1",
            f2_artifact_bytes=payload,
            page_key="p",
        )
        assert record.style_spans[0].label is label


def test_recently_used_artifact_survives_cache_eviction_of_older_ones() -> None:
    parser = F2Parser(document_cache_size=2)
    payloads = [_payload({"p": f"<i>{n}</i>"}) for n in range(3)]
    for payload in [*payloads, payloads[0], payloads[2]]:
        record = parser.parse_page(
            identity=_identity(payload),
            guideline_version="g1",
            f2_artifact_bytes=payload,
            page_key="p",
        )
        assert record.original_f2_artifact_sha256 == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize("size", [0, -1])
def test_cache_size_must_be_positive(size: int) -> None:
    with pytest.raises(ValueError, match="document_cache_size must be at least one"):
        F2Parser(document_cache_size=size)


def test_empty_guideline_version_is_rejected() -> None:
    payload = _payload({"p": "x"})
    with pytest.raises(ValueError, match="guideline_version must not be empty"):
        F2Parser().parse_page(
            identity=_identity(payload),
            guideline_version="",
            f2_artifact_bytes=payload,
            page_key="p",
        )


def test_unknown_page_key_is_rejected() -> None:
    payload = _payload({"p": "x"})
    with pytest.raises(ValueError, match="does not contain page key 'q'"):
        F2Parser().parse_page(
            identity=_identity(payload),
            guideline_version="g1",
            f2_artifact_bytes=payload,
            page_key="q",
        )


def test_comments_artifact_without_comment_bytes_is_rejected() -> None:
    payload = _payload({"p": "x"})
    with pytest.raises(ValueError, match="requires project_comments_bytes"):
        F2Parser().parse_page(
            identity=_identity(payload),
            guideline_version="g1",
            f2_artifact_bytes=payload,
            page_key="p",
            project_comments_artifact=_artifact(b"c", ArtifactSource.HUMAN),
        )


def test_comment_bytes_without_artifact_are_rejected() -> None:
    payload = _payload({"p": "x"})
    with pytest.raises(ValueError, match="project_comments_artifact is required"):
        F2Parser().parse_page(
            identity=_identity(payload),
            guideline_version="g1",
            f2_artifact_bytes=payload,
            page_key="p",
            project_comments_bytes=b"c",
        )


def test_comments_artifact_with_wrong_hash_is_rejected() -> None:
    payload = _payload({"p": "x"})
    with pytest.raises(ValueError, match="hash does not match"):
        F2Parser().parse_page(
            identity=_identity(payload),
            guideline_version="g1",
            f2_artifact_bytes=payload,
            page_key="p",
            project_comments_bytes=b"c",
            project_comments_artifact=_artifact(b"different", ArtifactSource.HUMAN),
        )
