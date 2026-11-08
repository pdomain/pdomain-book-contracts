from __future__ import annotations

import hashlib

import pytest

from pdomain_book_contracts.annotation.provenance import (
    ConfidenceTier,
    KnowledgeState,
    LabelSource,
)
from pdomain_book_contracts.layout.text_hints import LayoutTextHint, LayoutTextLine
from pdomain_book_contracts.matching import (
    ArtifactRange,
    MatchDocument,
    MatchLine,
    MatchPage,
    MatchPolicy,
    MatchToken,
    match_documents,
)
from pdomain_book_contracts.matching.pgdp_bounded import PgdpBoundedStrategy
from pdomain_book_contracts.matching.pgdp_layout_projection import (
    PgdpAlignmentDisposition,
    PgdpPageAlignment,
    align_pgdp_page,
    compose_pgdp_alignments,
    project_f2_formatting,
)
from pdomain_book_contracts.matching.pgdp_visible import (
    PgdpOcrWord,
    match_document_from_ocr_words,
    match_document_from_pgdp_tokens,
)
from pdomain_book_contracts.sources.pgdp.f2.tokens import read_f2_json
from pdomain_book_contracts.typography.labels import StyleLabel
from pdomain_book_contracts.typography.spans import SourceSlice, StyleSpan

_HASH = hashlib.sha256(b"projection-test").hexdigest()


def _policy(*, max_state_count: int = 10_000) -> MatchPolicy:
    return MatchPolicy(
        policy_id="test-policy",
        version="1",
        low_margin_threshold=0.0,
        max_merge_size=2,
        max_state_count=max_state_count,
        max_transition_count=100_000,
    )


def _document(
    document_id: str,
    tokens: tuple[tuple[str, str, int], ...],
) -> MatchDocument:
    return MatchDocument(
        document_id=document_id,
        pages=(
            MatchPage(
                page_id=f"{document_id}-page",
                lines=(
                    MatchLine(
                        line_id=f"{document_id}-line",
                        tokens=tuple(
                            MatchToken(
                                token_id=token_id,
                                text=text,
                                artifact_ranges=tuple(
                                    ArtifactRange(
                                        artifact_id=document_id,
                                        artifact_sha256=_HASH,
                                        byte_start=index,
                                        byte_end=index + 1,
                                        grapheme_start=start + index,
                                        grapheme_end=start + index + 1,
                                    )
                                    for index in range(len(text))
                                ),
                            )
                            for token_id, text, start in tokens
                        ),
                    ),
                ),
            ),
        ),
    )


def _style(start: int, end: int) -> StyleSpan:
    return StyleSpan(
        label=StyleLabel.ITALIC,
        start=start,
        end=end,
        state=KnowledgeState.POSITIVE,
        label_source=LabelSource.F2,
        confidence_tier=ConfidenceTier.GOLD,
        source_slices=(
            SourceSlice(artifact_sha256=_HASH, byte_start=start, byte_end=end),
        ),
        rule_ref="test",
        semantic_reason=None,
        warnings=(),
    )


def test_align_groups_a_real_number_split_join_and_round_trips() -> None:
    f2 = _document("f2", (("f2-11", "11", 0), ("f2-717", "717", 3)))
    p3 = _document("p3", (("p3-11717", "11717", 0),))
    ocr = _document("ocr", (("ocr-11717", "11717", 0),))

    alignment = align_pgdp_page(f2=f2, p3=p3, ocr=ocr, policy=_policy())

    assert alignment.disposition is PgdpAlignmentDisposition.ACCEPTED
    assert len(alignment.groups) == 1
    assert alignment.groups[0].f2_token_ids == ("f2-11", "f2-717")
    assert alignment.groups[0].p3_token_ids == ("p3-11717",)
    assert alignment.groups[0].ocr_token_ids == ("ocr-11717",)
    assert PgdpPageAlignment.from_json_bytes(alignment.to_json_bytes()) == alignment


def test_composition_rejects_different_shared_p3_text() -> None:
    f2 = _document("f2", (("f2-word", "word", 0),))
    p3 = _document("p3", (("p3-word", "word", 0),))
    changed_p3 = _document("p3", (("p3-word", "ward", 0),))
    ocr = _document("ocr", (("ocr-word", "word", 0),))

    f2_to_p3 = match_documents(f2, p3, policy=_policy())
    p3_to_ocr = match_documents(changed_p3, ocr, policy=_policy())

    with pytest.raises(ValueError, match="shared P3"):
        compose_pgdp_alignments(f2_to_p3=f2_to_p3, p3_to_ocr=p3_to_ocr)


def test_formatting_projects_only_exact_composed_graphemes() -> None:
    f2 = _document("f2", (("f2-word", "Case", 0),))
    p3 = _document("p3", (("p3-word", "case", 0),))
    ocr = _document("ocr", (("ocr-word", "case", 0),))
    alignment = align_pgdp_page(f2=f2, p3=p3, ocr=ocr, policy=_policy())
    hint = LayoutTextHint(
        kind="poetry",
        source="f2",
        text="Case",
        lines=(LayoutTextLine(text="Case"),),
        source_ref="f2#0",
        grapheme_range=(0, 4),
    )

    projection = project_f2_formatting(
        alignment=alignment,
        hints=(hint,),
        style_spans=(_style(0, 4),),
    )

    assert projection.layout_hints[0].ocr_token_ids == ("ocr-word",)
    assert projection.style_spans[0].source_grapheme_range == (1, 4)
    assert projection.unresolved[-1].disposition is PgdpAlignmentDisposition.CHANGED


def test_formatting_uses_artifact_grapheme_ranges_for_a_partial_join_style() -> None:
    f2 = _document("f2", (("f2-11", "11", 0), ("f2-717", "717", 3)))
    p3 = _document("p3", (("p3-11717", "11717", 0),))
    ocr = _document("ocr", (("ocr-11717", "11717", 0),))
    alignment = align_pgdp_page(f2=f2, p3=p3, ocr=ocr, policy=_policy())

    projection = project_f2_formatting(
        alignment=alignment,
        hints=(),
        style_spans=(_style(3, 6),),
    )

    assert (
        projection.style_spans[0].ocr_ranges[0].token_id
        == alignment.groups[0].ocr_token_ids[0]
    )
    assert projection.style_spans[0].ocr_ranges[0].grapheme_range == (2, 5)


def test_exhausted_match_stays_quarantined_in_composition() -> None:
    f2 = _document("f2", (("f2-word", "word", 0),))
    p3 = _document("p3", (("p3-word", "word", 0),))
    ocr = _document("ocr", (("ocr-word", "word", 0),))

    alignment = align_pgdp_page(
        f2=f2, p3=p3, ocr=ocr, policy=_policy(max_state_count=1)
    )

    assert alignment.disposition is PgdpAlignmentDisposition.EXHAUSTED
    assert all(
        group.disposition is PgdpAlignmentDisposition.EXHAUSTED
        for group in alignment.groups
    )


def test_accepted_anchor_groups_remain_accepted_when_a_residual_exhausts() -> None:
    tokens = tuple((f"token-{index}", str(index), index) for index in range(4))
    alignment = align_pgdp_page(
        f2=_document("f2", tokens),
        p3=_document("p3", tokens),
        ocr=_document("ocr", tokens),
        policy=_policy(max_state_count=1),
    )

    assert alignment.disposition is PgdpAlignmentDisposition.EXHAUSTED
    assert any(
        group.disposition is PgdpAlignmentDisposition.ACCEPTED
        for group in alignment.groups
    )


def test_composition_preserves_retained_anchor_strategy_and_work() -> None:
    tokens = tuple((f"token-{index}", str(index), index) for index in range(4))
    aligned = align_pgdp_page(
        f2=_document("f2", tokens),
        p3=_document("p3", tokens),
        ocr=_document("ocr", tokens),
        policy=_policy(max_state_count=1),
    )

    composed = compose_pgdp_alignments(
        f2_to_p3=aligned.f2_to_p3,
        p3_to_ocr=aligned.p3_to_ocr,
        f2_to_p3_windows=aligned.f2_to_p3_windows,
        p3_to_ocr_windows=aligned.p3_to_ocr_windows,
    )

    assert composed.f2_to_p3_strategy is PgdpBoundedStrategy.UNIQUE_EXACT_ANCHORS
    assert composed.p3_to_ocr_strategy is PgdpBoundedStrategy.UNIQUE_EXACT_ANCHORS
    assert composed.work == aligned.work


def test_style_projection_keeps_a_combining_grapheme_with_multiple_raw_slices() -> None:
    parsed = read_f2_json(b'{"p":"<i>a\\u0301</i>"}').pages[0].parsed
    f2 = match_document_from_pgdp_tokens(
        parsed, document_id="f2", page_id="p", artifact_id="F2.json"
    )
    p3 = _document("p3", (("p3-word", "a\u0301", 0),))
    ocr_word_id = "-".join(("ocr", "word"))
    ocr = match_document_from_ocr_words(
        (PgdpOcrWord(token_id=ocr_word_id, text="a\u0301", line_id="ocr-line"),),
        document_id="ocr",
        page_id="p",
    )
    alignment = align_pgdp_page(
        f2=f2.document, p3=p3, ocr=ocr.document, policy=_policy()
    )

    projection = project_f2_formatting(
        alignment=alignment, hints=(), style_spans=(_style(0, 1),)
    )

    projected_range = projection.style_spans[0].ocr_ranges[0]
    assert projected_range.token_id == ocr.document.pages[0].lines[0].tokens[0].token_id
    assert projected_range.grapheme_range == (0, 1)
