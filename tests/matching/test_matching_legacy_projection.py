from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from pdomain_book_contracts.matching import (
    LegacyDocumentSide,
    LegacyProjectionMutation,
    LegacyProjectionResult,
    MatchDocument,
    MatchGraph,
    MatchLine,
    MatchPage,
    MatchPolicy,
    MatchRelationKind,
    MatchToken,
    match_documents,
)
from pdomain_book_contracts.matching.legacy_projection import (
    legacy_page_to_match_document,
    project_match_graph_onto_page,
)
from pdomain_book_contracts.matching.match_type import MatchType
from pdomain_book_contracts.typography.annotations import TypographyAnnotations

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(eq=False)
class _Word:
    text: str
    ground_truth_text: str = ""
    ground_truth_match_keys: dict[str, object] = field(default_factory=dict)
    review: object | None = None
    typography_annotations: TypographyAnnotations | None = None
    glyph_annotations: object | None = None

    def __post_init__(self) -> None:
        if not self.ground_truth_text:
            self.ground_truth_text = self.text

    def merge(self, word_to_merge: object) -> None:
        if not isinstance(word_to_merge, _Word):
            raise TypeError
        self.text += word_to_merge.text
        self.ground_truth_text += word_to_merge.ground_truth_text


@dataclass(eq=False)
class _Line:
    line_words: list[_Word]
    base_ground_truth_text: str | None = None
    review: object | None = None

    @property
    def words(self) -> list[_Word]:
        return self.line_words

    def remove_item(self, item: _Word) -> None:
        self.line_words[:] = [word for word in self.line_words if word is not item]


@dataclass(eq=False)
class _Page:
    page_index: int
    lines: list[_Line]
    review: object | None = None


_DOC = "pg"


def _page(*lines: tuple[str, ...]) -> _Page:
    return _Page(
        page_index=3,
        lines=[_Line([_Word(text) for text in words]) for words in lines],
    )


def _reference(*lines: tuple[str, ...]) -> MatchDocument:
    return MatchDocument(
        document_id="ref",
        pages=(
            MatchPage(
                page_id="ref:page:0",
                lines=tuple(
                    MatchLine(
                        line_id=f"ref:page:0:line:{line_index}",
                        tokens=tuple(
                            MatchToken(
                                token_id=f"ref:page:0:line:{line_index}:word:{index}",
                                text=text,
                            )
                            for index, text in enumerate(words)
                        ),
                    )
                    for line_index, words in enumerate(lines)
                ),
            ),
        ),
    )


def _policy(*, max_merge_size: int = 3) -> MatchPolicy:
    return MatchPolicy(
        policy_id="legacy-test",
        version="1",
        low_margin_threshold=0.0,
        max_merge_size=max_merge_size,
        max_state_count=10_000,
        max_transition_count=100_000,
    )


def _graph(
    page: _Page,
    reference: MatchDocument,
    *,
    side: LegacyDocumentSide = LegacyDocumentSide.TARGET,
    max_merge_size: int = 3,
) -> MatchGraph:
    page_document = legacy_page_to_match_document(page, document_id=_DOC)
    if side is LegacyDocumentSide.TARGET:
        source, target = reference, page_document
    else:
        source, target = page_document, reference
    return match_documents(
        source, target, policy=_policy(max_merge_size=max_merge_size)
    )


def _project(
    page: _Page,
    reference: MatchDocument,
    *,
    side: LegacyDocumentSide = LegacyDocumentSide.TARGET,
    max_merge_size: int = 3,
) -> tuple[MatchGraph, LegacyProjectionResult]:
    graph = _graph(page, reference, side=side, max_merge_size=max_merge_size)
    result = project_match_graph_onto_page(
        page, graph, document_id=_DOC, page_side=side
    )
    return graph, result


def _texts(page: _Page) -> list[list[str]]:
    return [[word.text for word in line.words] for line in page.lines]


def test_page_snapshot_encodes_page_line_and_word_positions() -> None:
    page = _page(("alpha", "beta"), ("gamma",))
    document = legacy_page_to_match_document(page, document_id="doc")
    assert document.document_id == "doc"
    assert [p.page_id for p in document.pages] == ["doc:page:3"]
    lines = document.pages[0].lines
    assert [line.line_id for line in lines] == [
        "doc:page:3:line:0",
        "doc:page:3:line:1",
    ]
    assert [(t.token_id, t.text) for t in lines[0].tokens] == [
        ("doc:page:3:line:0:word:0", "alpha"),
        ("doc:page:3:line:0:word:1", "beta"),
    ]
    assert [t.token_id for t in lines[1].tokens] == ["doc:page:3:line:1:word:0"]


def test_snapshot_reads_word_text_not_ground_truth_text() -> None:
    page = _page(("ocr",))
    page.lines[0].words[0].ground_truth_text = "truth"
    document = legacy_page_to_match_document(page, document_id="doc")
    assert document.pages[0].lines[0].tokens[0].text == "ocr"


def test_one_to_one_relations_write_ground_truth_and_graph_evidence() -> None:
    page = _page(("Helo", "world"))
    graph, result = _project(page, _reference(("Hello", "world")))
    words = page.lines[0].words
    assert [word.ground_truth_text for word in words] == ["Hello", "world"]
    assert [word.text for word in words] == ["Helo", "world"]
    relations = graph.best_alternative.relations
    assert result.projected_relation_ids == tuple(
        relation.relation_id for relation in relations
    )
    assert result.mutated_relation_ids == ()
    assert result.skipped_relation_ids == ()
    keys = words[0].ground_truth_match_keys
    assert keys == {
        "match_type": MatchType.LINE_REPLACE_WORD_REPLACE.value,
        "match_score": 89,
        "match_graph_id": graph.graph_id,
        "match_relation_id": relations[0].relation_id,
        "match_side": "target",
        "match_source_token_ids": ("ref:page:0:line:0:word:0",),
        "match_target_token_ids": ("pg:page:3:line:0:word:0",),
        "match_projection_mutation": LegacyProjectionMutation.NONE.value,
    }
    assert words[1].ground_truth_match_keys["match_score"] == 100


def test_projection_refreshes_each_line_base_ground_truth_text() -> None:
    page = _page(("Helo", "wrld"), ("tst",))
    _project(page, _reference(("Hello", "world"), ("test",)))
    assert [line.base_ground_truth_text for line in page.lines] == [
        "Hello world",
        "test",
    ]


def test_fragments_of_one_logical_word_are_merged_on_the_page() -> None:
    page = _page(("Hel", "lo", "world"))
    graph, result = _project(page, _reference(("Hello", "world")))
    assert _texts(page) == [["Hello", "world"]]
    first = graph.best_alternative.relations[0]
    assert first.kind is MatchRelationKind.SOURCE_TO_FRAGMENTS
    assert result.projected_relation_ids[0] == first.relation_id
    assert result.mutated_relation_ids == (first.relation_id,)
    merged = page.lines[0].words[0]
    assert merged.ground_truth_text == "Hello"
    assert merged.ground_truth_match_keys["match_type"] == (
        MatchType.LINE_REPLACE_WORD_REPLACE_COMBINED.value
    )
    assert merged.ground_truth_match_keys["match_projection_mutation"] == (
        LegacyProjectionMutation.COMBINED_PAGE_FRAGMENTS.value
    )
    assert merged.ground_truth_match_keys["match_target_token_ids"] == (
        "pg:page:3:line:0:word:0",
        "pg:page:3:line:0:word:1",
    )
    assert merged.ground_truth_match_keys["match_score"] == 100
    assert page.lines[0].base_ground_truth_text == "Hello world"


def test_two_merges_on_one_line_each_find_their_words_after_earlier_merges() -> None:
    page = _page(("Hel", "lo", "wor", "ld", "end"))
    _, result = _project(page, _reference(("Hello", "world", "end")))
    assert _texts(page) == [["Hello", "world", "end"]]
    assert len(result.mutated_relation_ids) == 2
    assert [w.ground_truth_text for w in page.lines[0].words] == [
        "Hello",
        "world",
        "end",
    ]


def test_source_side_page_receives_the_target_text() -> None:
    page = _page(("Helo", "world"))
    graph, _ = _project(
        page, _reference(("Hello", "world")), side=LegacyDocumentSide.SOURCE
    )
    words = page.lines[0].words
    assert [word.ground_truth_text for word in words] == ["Hello", "world"]
    keys = words[0].ground_truth_match_keys
    assert keys["match_side"] == "source"
    assert keys["match_source_token_ids"] == ("pg:page:3:line:0:word:0",)
    assert keys["match_target_token_ids"] == ("ref:page:0:line:0:word:0",)
    assert keys["match_graph_id"] == graph.graph_id


def test_source_side_fragments_are_merged_too() -> None:
    page = _page(("Hel", "lo"))
    _, result = _project(page, _reference(("Hello",)), side=LegacyDocumentSide.SOURCE)
    assert _texts(page) == [["Hello"]]
    assert len(result.mutated_relation_ids) == 1


def test_relations_with_no_counterpart_on_the_page_are_left_alone() -> None:
    page = _page(("Hello", "world"))
    graph, result = _project(
        page, _reference(("Hello", "extra", "world")), max_merge_size=1
    )
    kinds = [relation.kind for relation in graph.best_alternative.relations]
    assert MatchRelationKind.SOURCE_ONLY in kinds
    source_only = next(
        r.relation_id
        for r in graph.best_alternative.relations
        if r.kind is MatchRelationKind.SOURCE_ONLY
    )
    assert source_only not in result.projected_relation_ids
    assert source_only not in result.skipped_relation_ids
    assert [w.ground_truth_text for w in page.lines[0].words] == ["Hello", "world"]


def _mark_split(page: _Page) -> None:
    page.lines[0].words[1].ground_truth_match_keys["split"] = True


def _mark_review(page: _Page) -> None:
    page.lines[0].words[0].review = object()


def _mark_typography(page: _Page) -> None:
    page.lines[0].words[1].typography_annotations = TypographyAnnotations(spans=())


def _mark_glyphs(page: _Page) -> None:
    page.lines[0].words[0].glyph_annotations = object()


def _mark_line_review(page: _Page) -> None:
    page.lines[0].review = object()


def _mark_page_review(page: _Page) -> None:
    page.review = object()


@pytest.mark.parametrize(
    ("mark", "mutation"),
    [
        (_mark_split, LegacyProjectionMutation.MANUAL_SPLIT_PRESERVED),
        (_mark_review, LegacyProjectionMutation.PROTECTED_WORD_STATE_PRESERVED),
        (_mark_typography, LegacyProjectionMutation.PROTECTED_WORD_STATE_PRESERVED),
        (_mark_glyphs, LegacyProjectionMutation.PROTECTED_WORD_STATE_PRESERVED),
        (_mark_line_review, LegacyProjectionMutation.CONTAINER_REVIEW_PRESERVED),
        (_mark_page_review, LegacyProjectionMutation.CONTAINER_REVIEW_PRESERVED),
    ],
)
def test_protected_fragments_stay_physical_with_typed_skip_evidence(
    mark: Callable[[_Page], None], mutation: LegacyProjectionMutation
) -> None:
    page = _page(("Hel", "lo", "world"))
    mark(page)
    graph, result = _project(page, _reference(("Hello", "world")))
    assert _texts(page) == [["Hel", "lo", "world"]]
    first = graph.best_alternative.relations[0]
    assert result.skipped_relation_ids == (first.relation_id,)
    assert result.mutated_relation_ids == ()
    assert result.projected_relation_ids == (
        graph.best_alternative.relations[1].relation_id,
    )
    for word in page.lines[0].words[:2]:
        keys = word.ground_truth_match_keys
        assert keys["match_projection_mutation"] == mutation.value
        assert keys["match_type"] == MatchType.LINE_REPLACE_WORD_REPLACE.value
        assert keys["match_relation_id"] == first.relation_id
        assert word.ground_truth_text == word.text
    assert page.lines[0].words[2].ground_truth_text == "world"


def test_manual_split_takes_precedence_over_protected_word_state() -> None:
    page = _page(("Hel", "lo", "world"))
    _mark_split(page)
    _mark_review(page)
    _project(page, _reference(("Hello", "world")))
    assert page.lines[0].words[0].ground_truth_match_keys[
        "match_projection_mutation"
    ] == (LegacyProjectionMutation.MANUAL_SPLIT_PRESERVED.value)


def test_falsy_split_key_does_not_protect_a_word() -> None:
    page = _page(("Hel", "lo", "world"))
    page.lines[0].words[1].ground_truth_match_keys["split"] = False
    _project(page, _reference(("Hello", "world")))
    assert _texts(page) == [["Hello", "world"]]


def test_one_to_one_relation_is_written_even_on_a_reviewed_word() -> None:
    page = _page(("Helo",))
    review = object()
    page.lines[0].words[0].review = review
    _project(page, _reference(("Hello",)))
    word = page.lines[0].words[0]
    assert word.ground_truth_text == "Hello"
    assert word.review is review


def test_fragments_split_across_lines_are_not_merged() -> None:
    page = _page(("Hel",), ("lo", "world"))
    graph, result = _project(page, _reference(("Hello", "world")))
    assert _texts(page) == [["Hel"], ["lo", "world"]]
    first = graph.best_alternative.relations[0]
    assert result.skipped_relation_ids == (first.relation_id,)
    for line in page.lines:
        assert line.words[0].ground_truth_match_keys["match_projection_mutation"] == (
            LegacyProjectionMutation.CROSS_LINE_FRAGMENTS_PRESERVED.value
        )


def test_quarantined_graph_is_refused_before_touching_the_page() -> None:
    page = _page(("Hello", "world", "zz"))
    graph = _graph(page, _reference(("Hello", "world")))
    assert not graph.accepted
    with pytest.raises(ValueError, match="quarantined match graph"):
        project_match_graph_onto_page(page, graph, document_id=_DOC)
    assert all(word.ground_truth_match_keys == {} for word in page.lines[0].words)
    assert page.lines[0].base_ground_truth_text is None


def test_page_edited_after_matching_is_refused() -> None:
    page = _page(("Helo", "world"))
    graph = _graph(page, _reference(("Hello", "world")))
    page.lines[0].words[0].text = "Heloo"
    with pytest.raises(ValueError, match="does not match the graph"):
        project_match_graph_onto_page(page, graph, document_id=_DOC)
    assert page.lines[0].words[0].ground_truth_text == "Helo"


def test_page_projected_from_the_wrong_side_is_refused() -> None:
    page = _page(("Helo", "world"))
    graph = _graph(page, _reference(("Hello", "world")))
    with pytest.raises(ValueError, match="does not match the graph"):
        project_match_graph_onto_page(
            page, graph, document_id=_DOC, page_side=LegacyDocumentSide.SOURCE
        )


def test_page_with_a_different_document_id_is_refused() -> None:
    page = _page(("Helo", "world"))
    graph = _graph(page, _reference(("Hello", "world")))
    with pytest.raises(ValueError, match="does not match the graph"):
        project_match_graph_onto_page(page, graph, document_id="other")
