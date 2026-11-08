from __future__ import annotations

from pdomain_book_contracts.matching import (
    MatchDocument,
    MatchLine,
    MatchPage,
    MatchPolicy,
    MatchToken,
    match_documents,
)


def test_real_ocr_ligature_insertion_keeps_valid_grapheme_operations() -> None:
    left_id, right_id = "p3-word", "ocr-word"
    source = MatchDocument(
        document_id="p3",
        pages=(
            MatchPage(
                page_id="081.png",
                lines=(
                    MatchLine(
                        line_id="p3-line",
                        tokens=(MatchToken(token_id=left_id, text="E."),),
                    ),
                ),
            ),
        ),
    )
    target = MatchDocument(
        document_id="ocr",
        pages=(
            MatchPage(
                page_id="081.png",
                lines=(
                    MatchLine(
                        line_id="ocr-line",
                        tokens=(
                            MatchToken(token_id=right_id, text="her,our\ufb01rst"),
                        ),
                    ),
                ),
            ),
        ),
    )
    policy = MatchPolicy(
        policy_id="regression",
        version="1",
        low_margin_threshold=0.1,
        max_merge_size=1,
        max_state_count=100,
        max_transition_count=1000,
    )
    graph = match_documents(source, target, policy=policy)
    reverse = match_documents(target, source, policy=policy)
    assert reverse.source_document == target
    assert reverse.target_document == source
    assert graph.source_document == source
    assert graph.target_document == target
    assert MatchDocument.from_json_bytes(source.to_json_bytes()) == source
