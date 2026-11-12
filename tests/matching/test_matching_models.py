from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from pdomain_book_contracts.matching import (
    MatchDocument,
    MatchGraph,
    MatchLine,
    MatchPage,
    MatchPolicy,
    MatchQuarantineReason,
    MatchToken,
    match_documents,
)
from pdomain_book_contracts.matching.models import (
    ArtifactRange,
    MatchAlternative,
    MatchContinuationReference,
    MatchOperation,
    MatchOperationKind,
    MatchRelation,
    MatchRelationKind,
    MatchSearchEvidence,
    MatchSearchPathEvidence,
    canonical_relation_path_bytes,
    continuation_fragment_matches_token,
    continuation_reference_matches_document_side,
)
from pdomain_book_contracts.typography.normalization import build_comparison_view

if TYPE_CHECKING:
    from collections.abc import Sequence

_HASH = "ab" * 32
_MATCH = MatchOperationKind.MATCH
_DELETE = MatchOperationKind.SOURCE_ONLY_DELETION
_INSERT = MatchOperationKind.TARGET_ONLY_INSERTION


def _ar(offset: int, *, sha: str = _HASH) -> ArtifactRange:
    return ArtifactRange(
        artifact_id="artifact.json",
        artifact_sha256=sha,
        byte_start=offset,
        byte_end=offset + 1,
        grapheme_start=offset,
        grapheme_end=offset + 1,
    )


def _tok(name: str, text: str, ranges: tuple[ArtifactRange, ...] = ()) -> MatchToken:
    return MatchToken(token_id=name, text=text, artifact_ranges=ranges)


def _doc(prefix: str, words: Sequence[str]) -> MatchDocument:
    return MatchDocument(
        document_id=prefix,
        pages=(
            MatchPage(
                page_id=f"{prefix}-page",
                lines=(
                    MatchLine(
                        line_id=f"{prefix}-line",
                        tokens=tuple(
                            _tok(f"{prefix}{index}", word)
                            for index, word in enumerate(words)
                        ),
                    ),
                ),
            ),
        ),
    )


def _op(
    kind: MatchOperationKind, source: tuple[int, int], target: tuple[int, int]
) -> MatchOperation:
    return MatchOperation(
        kind=kind, source_grapheme_range=source, target_grapheme_range=target
    )


def _same(length: int) -> tuple[MatchOperation, ...]:
    return (_op(_MATCH, (0, length), (0, length)),)


def _one_to_one(
    source: str, target: str, ops: tuple[MatchOperation, ...]
) -> MatchRelation:
    return MatchRelation(
        kind=MatchRelationKind.ONE_TO_ONE,
        source_token_ids=(source,),
        target_token_ids=(target,),
        operations=ops,
    )


def _policy(threshold: float = 1.0) -> MatchPolicy:
    return MatchPolicy(
        policy_id="models-test",
        version="1",
        low_margin_threshold=threshold,
        max_merge_size=3,
        max_state_count=10_000,
        max_transition_count=100_000,
    )


def _graph() -> MatchGraph:
    return match_documents(
        _doc("s", ["ab", "cd"]), _doc("t", ["ab", "cd"]), policy=_policy()
    )


def _tie_graph() -> MatchGraph:
    return match_documents(
        _doc("s", ["Hello", "extra", "world"]),
        _doc("t", ["Hello", "world"]),
        policy=_policy(0.0),
    )


def _replace_best(
    graph: MatchGraph, relations: tuple[MatchRelation, ...], *, cost: float = 0.0
) -> MatchGraph:
    return graph.model_copy(
        update={
            "best_alternative": MatchAlternative(total_cost=cost, relations=relations),
            "runner_up_alternative": None,
            "runner_up_margin": None,
            "search_evidence": None,
        }
    )


def _path(
    source: int = 2,
    target: int = 2,
    cost: float = 0.0,
    relations: tuple[MatchRelation, ...] = (),
) -> MatchSearchPathEvidence:
    return MatchSearchPathEvidence(
        source_tokens_consumed=source,
        target_tokens_consumed=target,
        total_cost=cost,
        relations=relations,
    )


def _evidence(**overrides: object) -> MatchSearchEvidence:
    values: dict[str, object] = {
        "source_token_count": 2,
        "target_token_count": 2,
        "state_count": 3,
        "state_iteration_count": 3,
        "transition_count": 4,
        "grapheme_state_count": 0,
        "grapheme_work_count": 0,
        "max_state_count": 10,
        "max_transition_count": 10,
        "max_grapheme_state_count": 10,
        "max_grapheme_work_count": 10,
        "best_complete_path": None,
        "runner_up_complete_path": None,
        "partial_paths": (),
    }
    return MatchSearchEvidence.model_validate({**values, **overrides})


def test_artifact_range_normalizes_hash_case_and_rejects_bad_input() -> None:
    assert _ar(0, sha="AB" * 32).artifact_sha256 == _HASH
    with pytest.raises(ValidationError, match="artifact_id must not be empty"):
        ArtifactRange(
            artifact_id="",
            artifact_sha256=_HASH,
            byte_start=0,
            byte_end=1,
            grapheme_start=0,
            grapheme_end=1,
        )
    for bad in ("ab" * 31, "zz" * 32, ""):
        with pytest.raises(ValidationError, match="64-character hexadecimal"):
            _ar(0, sha=bad)


@pytest.mark.parametrize(
    ("byte", "grapheme", "message"),
    [
        ((2, 2), (0, 1), "byte range"),
        ((3, 2), (0, 1), "byte range"),
        ((0, 1), (4, 4), "grapheme range"),
        ((0, 1), (5, 4), "grapheme range"),
    ],
)
def test_artifact_range_must_be_nonempty_and_ordered(
    byte: tuple[int, int], grapheme: tuple[int, int], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        ArtifactRange(
            artifact_id="a",
            artifact_sha256=_HASH,
            byte_start=byte[0],
            byte_end=byte[1],
            grapheme_start=grapheme[0],
            grapheme_end=grapheme[1],
        )


def test_tokens_lines_and_pages_reject_empty_identifiers_and_text() -> None:
    with pytest.raises(ValidationError, match="token_id must not be empty"):
        _tok("", "x")
    with pytest.raises(ValidationError, match="token text must not be empty"):
        _tok("a", "")
    with pytest.raises(ValidationError, match="line_id must not be empty"):
        MatchLine(line_id="", tokens=())
    with pytest.raises(ValidationError, match="page_id must not be empty"):
        MatchPage(page_id="", lines=())
    with pytest.raises(ValidationError, match="document_id must not be empty"):
        MatchDocument(document_id="", pages=())


def test_duplicate_ids_are_rejected_at_the_level_that_owns_them() -> None:
    with pytest.raises(ValidationError, match="token IDs must be unique within a line"):
        MatchLine(line_id="l", tokens=(_tok("a", "x"), _tok("a", "y")))
    line_one = MatchLine(line_id="l", tokens=(_tok("a", "x"),))
    line_two = MatchLine(line_id="l", tokens=(_tok("b", "y"),))
    with pytest.raises(ValidationError, match="line IDs must be unique within a page"):
        MatchPage(page_id="p", lines=(line_one, line_two))


def test_document_ids_must_be_unique_across_the_whole_document() -> None:
    def page(page_id: str, line_id: str, token_id: str) -> MatchPage:
        line = MatchLine(line_id=line_id, tokens=(_tok(token_id, "x"),))
        return MatchPage(page_id=page_id, lines=(line,))

    with pytest.raises(ValidationError, match="page IDs must be unique"):
        MatchDocument(
            document_id="d", pages=(page("p", "l1", "a"), page("p", "l2", "b"))
        )
    with pytest.raises(ValidationError, match="line IDs must be unique within a doc"):
        MatchDocument(
            document_id="d", pages=(page("p1", "l", "a"), page("p2", "l", "b"))
        )
    with pytest.raises(ValidationError, match="token IDs must be unique within a doc"):
        MatchDocument(
            document_id="d", pages=(page("p1", "l1", "a"), page("p2", "l2", "a"))
        )


def test_document_reports_its_token_ids() -> None:
    assert _doc("s", ["a", "b", "c"]).token_ids() == {"s0", "s1", "s2"}


@pytest.mark.parametrize(
    ("kind", "source", "target", "message"),
    [
        (_MATCH, (2, 1), (0, 1), "must be ordered"),
        (_MATCH, (0, 1), (3, 2), "must be ordered"),
        (_MATCH, (0, 1), (1, 1), "match and substitution"),
        (MatchOperationKind.SUBSTITUTION, (1, 1), (0, 1), "match and substitution"),
        (_DELETE, (0, 1), (0, 1), "only the source"),
        (_DELETE, (0, 0), (0, 0), "only the source"),
        (_INSERT, (0, 1), (0, 1), "only the target"),
        (_INSERT, (0, 0), (0, 0), "only the target"),
    ],
)
def test_operation_ranges_must_agree_with_the_operation_kind(
    kind: MatchOperationKind,
    source: tuple[int, int],
    target: tuple[int, int],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        _op(kind, source, target)


def test_valid_deletions_and_insertions_are_accepted() -> None:
    assert _op(_DELETE, (0, 2), (1, 1)).target_grapheme_range == (1, 1)
    assert _op(_INSERT, (1, 1), (0, 2)).source_grapheme_range == (1, 1)


def _reference(**overrides: object) -> MatchContinuationReference:
    values: dict[str, object] = {
        "continuation_id": "c1",
        "evidence_artifact_id": "f2",
        "evidence_artifact_path": "rounds/F2.json",
        "evidence_sha256": _HASH,
        "decision": "preserve_punctuation",
        "left_fragment_token_id": "s0",
        "right_fragment_token_id": "s1",
        "left_fragment_text": "a",
        "right_fragment_text": "b",
        "left_fragment_grapheme_ranges": (_ar(0),),
        "right_fragment_grapheme_ranges": (_ar(1),),
        "relation_source_token_ids": ("s0", "s1"),
        "relation_target_token_ids": ("t0",),
    }
    return MatchContinuationReference.model_validate({**values, **overrides})


def test_continuation_reference_accepts_a_confined_relative_path() -> None:
    assert _reference().evidence_artifact_path == "rounds/F2.json"


@pytest.mark.parametrize("path", ["", "/etc/passwd", "../x", "a/../b", "a/.."])
def test_continuation_reference_rejects_unconfined_paths(path: str) -> None:
    with pytest.raises(ValidationError, match="confined relative path"):
        _reference(evidence_artifact_path=path)


@pytest.mark.parametrize(
    "field",
    [
        "continuation_id",
        "evidence_artifact_id",
        "decision",
        "left_fragment_token_id",
        "right_fragment_token_id",
        "left_fragment_text",
        "right_fragment_text",
    ],
)
def test_continuation_reference_rejects_empty_identifiers(field: str) -> None:
    with pytest.raises(ValidationError, match=f"{field} must not be empty"):
        _reference(**{field: ""})


def test_continuation_reference_rejects_a_malformed_evidence_hash() -> None:
    with pytest.raises(ValidationError, match="evidence_sha256 must be a 64"):
        _reference(evidence_sha256="12")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"left_fragment_grapheme_ranges": ()}, "require left fragment"),
        ({"right_fragment_grapheme_ranges": ()}, "require right fragment"),
        ({"left_fragment_text": "ab"}, "left continuation fragment text"),
        ({"right_fragment_text": "bc"}, "right continuation fragment text"),
        (
            {"relation_source_token_ids": (), "relation_target_token_ids": ()},
            "require relation token IDs",
        ),
    ],
)
def test_continuation_reference_rejects_inconsistent_fragments(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _reference(**overrides)


def test_a_fragment_matches_only_a_contiguous_slice_with_equal_ranges() -> None:
    token = _tok("s0", "abcd", tuple(_ar(i) for i in range(4)))
    assert continuation_fragment_matches_token("bc", (_ar(1), _ar(2)), token)
    assert continuation_fragment_matches_token("abcd", token.artifact_ranges, token)
    assert not continuation_fragment_matches_token("bd", (_ar(1), _ar(3)), token)
    assert not continuation_fragment_matches_token("bc", (_ar(2), _ar(3)), token)
    assert not continuation_fragment_matches_token("bx", (_ar(1), _ar(2)), token)
    assert not continuation_fragment_matches_token("bc", (_ar(1),), token)
    assert not continuation_fragment_matches_token(
        "abcde", tuple(_ar(i) for i in range(5)), token
    )


def test_a_fragment_never_matches_a_token_without_exact_ranges() -> None:
    assert not continuation_fragment_matches_token("a", (_ar(0),), _tok("s0", "ab"))


def test_reference_matches_a_document_side_only_when_both_fragments_do() -> None:
    left = _tok("s0", "a", (_ar(0),))
    right = _tok("s1", "b", (_ar(1),))
    side = {"s0": left, "s1": right}
    assert continuation_reference_matches_document_side(_reference(), side)
    assert not continuation_reference_matches_document_side(_reference(), {"s0": left})
    assert not continuation_reference_matches_document_side(_reference(), {"s1": right})
    wrong = {"s0": left, "s1": _tok("s1", "b", (_ar(9),))}
    assert not continuation_reference_matches_document_side(_reference(), wrong)


@pytest.mark.parametrize(
    ("kind", "source", "target"),
    [
        (MatchRelationKind.ONE_TO_ONE, ("a", "b"), ("c",)),
        (MatchRelationKind.ONE_TO_ONE, (), ("c",)),
        (MatchRelationKind.SOURCE_TO_FRAGMENTS, ("a",), ("c",)),
        (MatchRelationKind.SOURCE_TO_FRAGMENTS, ("a", "b"), ("c", "d")),
        (MatchRelationKind.SOURCES_TO_ONE, ("a",), ("c",)),
        (MatchRelationKind.SOURCES_TO_ONE, ("a", "b"), ("c", "d")),
        (MatchRelationKind.SOURCE_ONLY, (), ()),
        (MatchRelationKind.SOURCE_ONLY, ("a",), ("c",)),
        (MatchRelationKind.TARGET_ONLY, ("a",), ("c",)),
        (MatchRelationKind.TARGET_ONLY, (), ()),
    ],
)
def test_relation_kind_fixes_the_allowed_token_cardinality(
    kind: MatchRelationKind, source: tuple[str, ...], target: tuple[str, ...]
) -> None:
    with pytest.raises(ValidationError, match=f"{kind.value} relation has invalid"):
        MatchRelation(
            kind=kind, source_token_ids=source, target_token_ids=target, operations=()
        )


@pytest.mark.parametrize(
    ("kind", "source", "target"),
    [
        (MatchRelationKind.ONE_TO_ONE, ("a",), ("c",)),
        (MatchRelationKind.SOURCE_TO_FRAGMENTS, ("a",), ("c", "d", "e")),
        (MatchRelationKind.SOURCES_TO_ONE, ("a", "b", "c"), ("d",)),
        (MatchRelationKind.SOURCE_ONLY, ("a", "b"), ()),
        (MatchRelationKind.TARGET_ONLY, (), ("c", "d")),
    ],
)
def test_relation_accepts_each_kind_with_its_cardinality(
    kind: MatchRelationKind, source: tuple[str, ...], target: tuple[str, ...]
) -> None:
    relation = MatchRelation(
        kind=kind, source_token_ids=source, target_token_ids=target, operations=()
    )
    assert relation.kind is kind


def test_relation_rejects_empty_and_duplicate_token_ids() -> None:
    with pytest.raises(ValidationError, match="relation token IDs must not be empty"):
        _one_to_one("", "t0", ())
    with pytest.raises(ValidationError, match="source token IDs must be unique"):
        MatchRelation(
            kind=MatchRelationKind.SOURCES_TO_ONE,
            source_token_ids=("a", "a"),
            target_token_ids=("b",),
            operations=(),
        )
    with pytest.raises(ValidationError, match="target token IDs must be unique"):
        MatchRelation(
            kind=MatchRelationKind.SOURCE_TO_FRAGMENTS,
            source_token_ids=("a",),
            target_token_ids=("b", "b"),
            operations=(),
        )


def test_relation_id_is_content_derived_and_tamper_evident() -> None:
    relation = _one_to_one("s0", "t0", _same(2))
    assert relation.relation_id is not None
    assert len(relation.relation_id) == 64
    assert relation == _one_to_one("s0", "t0", _same(2))
    assert relation.relation_id != _one_to_one("s0", "t1", _same(2)).relation_id
    with pytest.raises(ValidationError, match="relation_id does not match"):
        MatchRelation(
            relation_id="0" * 64,
            kind=MatchRelationKind.ONE_TO_ONE,
            source_token_ids=("s0",),
            target_token_ids=("t0",),
            operations=_same(2),
        )


def test_relation_copy_recomputes_its_id_even_if_the_update_names_one() -> None:
    relation = _one_to_one("s0", "t0", _same(2))
    copied = relation.model_copy(
        update={"target_token_ids": ("t9",), "relation_id": relation.relation_id}
    )
    assert copied.target_token_ids == ("t9",)
    assert copied.relation_id == _one_to_one("s0", "t9", _same(2)).relation_id
    assert relation.model_copy() == relation
    with pytest.raises(ValidationError):
        relation.model_copy(update={"kind": MatchRelationKind.SOURCE_ONLY})


def test_relation_needs_both_comparison_views_or_neither() -> None:
    view = build_comparison_view("ab")
    kwargs: dict[str, object] = {
        "kind": MatchRelationKind.ONE_TO_ONE,
        "source_token_ids": ("s0",),
        "target_token_ids": ("t0",),
        "operations": _same(2),
    }
    with pytest.raises(ValidationError, match="requires both source and target views"):
        MatchRelation.model_validate({**kwargs, "source_comparison": view})
    with pytest.raises(ValidationError, match="requires both source and target views"):
        MatchRelation.model_validate({**kwargs, "target_comparison": view})
    both = MatchRelation.model_validate(
        {**kwargs, "source_comparison": view, "target_comparison": view}
    )
    assert both.source_comparison == view


def _relation_with(reference: MatchContinuationReference) -> MatchRelation:
    return MatchRelation(
        kind=MatchRelationKind.SOURCES_TO_ONE,
        source_token_ids=("s0", "s1"),
        target_token_ids=("t0",),
        operations=(),
        continuation_references=(reference,),
    )


def test_relation_continuation_references_must_describe_the_same_relation() -> None:
    assert (
        _relation_with(_reference()).continuation_references[0].continuation_id == "c1"
    )
    with pytest.raises(
        ValidationError, match="source token IDs must match its relation"
    ):
        _relation_with(_reference(relation_source_token_ids=("s0", "s9")))
    with pytest.raises(
        ValidationError, match="target token IDs must match its relation"
    ):
        _relation_with(_reference(relation_target_token_ids=("t9",)))
    with pytest.raises(ValidationError, match="occur on one relation side"):
        _relation_with(_reference(**{"right_fragment_token_id": "t0"}))


def test_alternative_validates_cost_uniqueness_and_identity() -> None:
    first = _one_to_one("s0", "t0", _same(2))
    second = _one_to_one("s1", "t1", _same(2))
    alternative = MatchAlternative(total_cost=1.5, relations=(first, second))
    assert alternative.alternative_id is not None
    for cost in (-1.0, float("inf"), float("nan")):
        with pytest.raises(ValidationError, match="finite and nonnegative"):
            MatchAlternative(total_cost=cost, relations=())
    with pytest.raises(ValidationError, match="relation IDs must be unique"):
        MatchAlternative(total_cost=0.0, relations=(first, first))
    with pytest.raises(ValidationError, match="source tokens can appear only once"):
        MatchAlternative(
            total_cost=0.0, relations=(first, _one_to_one("s0", "t1", _same(2)))
        )
    with pytest.raises(ValidationError, match="target tokens can appear only once"):
        MatchAlternative(
            total_cost=0.0, relations=(first, _one_to_one("s1", "t0", _same(2)))
        )
    with pytest.raises(ValidationError, match="alternative_id does not match"):
        MatchAlternative(
            alternative_id="1" * 64, total_cost=1.5, relations=(first, second)
        )


def test_alternative_copy_recomputes_identity() -> None:
    first = _one_to_one("s0", "t0", _same(2))
    alternative = MatchAlternative(total_cost=1.0, relations=(first,))
    copied = alternative.model_copy(update={"total_cost": 2.0})
    assert copied.total_cost == 2.0
    assert copied.alternative_id != alternative.alternative_id
    assert alternative.model_copy() == alternative


def test_relation_path_bytes_depend_on_the_ordered_relations() -> None:
    first = _one_to_one("s0", "t0", _same(2))
    second = _one_to_one("s1", "t1", _same(2))
    forward = canonical_relation_path_bytes((first, second))
    assert forward == canonical_relation_path_bytes((first, second))
    assert forward != canonical_relation_path_bytes((second, first))
    assert canonical_relation_path_bytes(()) == b"[]"
    assert _path(relations=(first, second)).canonical_path_bytes == forward


@pytest.mark.parametrize("cost", [-0.5, float("inf"), float("nan")])
def test_search_path_cost_must_be_finite_and_nonnegative(cost: float) -> None:
    with pytest.raises(ValidationError, match="finite and nonnegative"):
        _path(cost=cost)


def test_search_evidence_accepts_a_consistent_complete_search() -> None:
    evidence = _evidence(
        best_complete_path=_path(cost=0.0),
        runner_up_complete_path=_path(cost=4.0),
        partial_paths=(_path(1, 2), _path(2, 1, 1.0)),
    )
    assert evidence.best_complete_path is not None
    assert len(evidence.partial_paths) == 2


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"state_count": 0}, "state_count must be at least one"),
        ({"state_iteration_count": 0}, "state_iteration_count must be at least one"),
        ({"max_state_count": 0}, "bounds must be positive"),
        ({"max_transition_count": 0}, "bounds must be positive"),
        ({"max_grapheme_state_count": 0}, "bounds must be positive"),
        ({"max_grapheme_work_count": 0}, "bounds must be positive"),
        (
            {"best_complete_path": _path(1, 2)},
            "must consume both complete documents",
        ),
        (
            {"best_complete_path": _path(), "runner_up_complete_path": _path(2, 1)},
            "must consume both complete documents",
        ),
        (
            {"runner_up_complete_path": _path()},
            "requires a best complete path",
        ),
        (
            {
                "best_complete_path": _path(cost=3.0),
                "runner_up_complete_path": _path(cost=1.0),
            },
            "complete search paths must use deterministic order",
        ),
        (
            {"partial_paths": (_path(0, 0), _path(0, 1), _path(1, 1))},
            "at most two partial paths",
        ),
        (
            {"partial_paths": (_path(0, 1, 2.0), _path(1, 0, 1.0))},
            "partial search paths must use deterministic order",
        ),
        (
            {"partial_paths": (_path(3, 0),)},
            "consumption exceeds document token count",
        ),
        (
            {"partial_paths": (_path(0, 3),)},
            "consumption exceeds document token count",
        ),
        ({"partial_paths": (_path(2, 2),)}, "partial search paths cannot be complete"),
    ],
)
def test_search_evidence_rejects_inconsistent_search_state(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _evidence(**overrides)


def test_equal_cost_search_paths_are_ordered_by_canonical_bytes() -> None:
    first = _one_to_one("s0", "t0", _same(2))
    second = _one_to_one("s1", "t1", _same(2))
    low, high = sorted(
        (_path(relations=(first,)), _path(relations=(second,))),
        key=lambda path: path.canonical_path_bytes,
    )
    ordered = _evidence(best_complete_path=low, runner_up_complete_path=high)
    assert ordered.runner_up_complete_path == high
    with pytest.raises(ValidationError, match="deterministic order"):
        _evidence(best_complete_path=high, runner_up_complete_path=low)


@pytest.mark.parametrize("field", ["policy_id", "version"])
def test_policy_rejects_empty_identifiers(field: str) -> None:
    values = {"policy_id": "p", "version": "1"}
    values[field] = ""
    with pytest.raises(ValidationError, match=f"{field} must not be empty"):
        MatchPolicy(
            policy_id=values["policy_id"],
            version=values["version"],
            low_margin_threshold=0.0,
            max_merge_size=1,
            max_state_count=1,
            max_transition_count=1,
        )


@pytest.mark.parametrize(
    "field",
    [
        "low_margin_threshold",
        "exact_match_cost",
        "substitution_cost",
        "source_only_cost",
        "target_only_cost",
    ],
)
def test_policy_rejects_infinite_costs(field: str) -> None:
    values: dict[str, object] = {
        "policy_id": "p",
        "version": "1",
        "low_margin_threshold": 0.0,
        "max_merge_size": 1,
        "max_state_count": 1,
        "max_transition_count": 1,
    }
    values[field] = float("inf")
    with pytest.raises(ValidationError, match=f"{field} must be finite"):
        MatchPolicy.model_validate(values)


@pytest.mark.parametrize(
    "field", ["max_merge_size", "max_state_count", "max_transition_count"]
)
def test_policy_bounds_must_be_positive_integers(field: str) -> None:
    values: dict[str, object] = {
        "policy_id": "p",
        "version": "1",
        "low_margin_threshold": 0.0,
        "max_merge_size": 1,
        "max_state_count": 1,
        "max_transition_count": 1,
    }
    for bad in (0, 1.0):
        with pytest.raises(ValidationError):
            MatchPolicy.model_validate({**values, field: bad})


def test_engine_graph_is_accepted_and_round_trips_through_canonical_json() -> None:
    graph = _graph()
    assert graph.accepted
    assert graph.graph_id is not None
    assert MatchGraph.from_json_bytes(graph.to_json_bytes()) == graph


def test_graph_copy_recomputes_the_graph_id() -> None:
    graph = _graph()
    copied = graph.model_copy(update={"warnings": ("note",)})
    assert copied.warnings == ("note",)
    assert copied.graph_id != graph.graph_id
    assert graph.model_copy() == graph


def test_graph_runner_up_and_margin_come_together() -> None:
    graph = _graph()
    with pytest.raises(ValidationError, match="present together"):
        graph.model_copy(update={"runner_up_alternative": None})
    with pytest.raises(ValidationError, match="present together"):
        _replace_best(graph, graph.best_alternative.relations).model_copy(
            update={"runner_up_margin": 1.0}
        )


@pytest.mark.parametrize("margin", [-1.0, float("inf"), float("nan")])
def test_graph_margin_must_be_finite_and_nonnegative(margin: float) -> None:
    with pytest.raises(ValidationError, match="finite and nonnegative"):
        _graph().model_copy(update={"runner_up_margin": margin})


def test_graph_margin_must_equal_the_cost_difference() -> None:
    with pytest.raises(ValidationError, match="margin must equal"):
        _graph().model_copy(update={"runner_up_margin": 3.0})


def test_graph_runner_up_must_differ_from_the_best_path() -> None:
    graph = _graph()
    clone = MatchAlternative(
        total_cost=graph.best_alternative.total_cost,
        relations=graph.best_alternative.relations,
    )
    with pytest.raises(ValidationError, match="must differ from the best path"):
        graph.model_copy(
            update={
                "runner_up_alternative": clone,
                "runner_up_margin": 0.0,
                "search_evidence": None,
                "accepted": False,
                "quarantine_reasons": (MatchQuarantineReason.TIE,),
            }
        )


def test_graph_runner_up_cannot_be_cheaper_than_the_best() -> None:
    graph = _graph()
    runner = graph.runner_up_alternative
    assert runner is not None
    with pytest.raises(ValidationError, match="cannot be lower than best cost"):
        graph.model_copy(
            update={
                "best_alternative": graph.best_alternative.model_copy(
                    update={"total_cost": 9.0}
                ),
                "runner_up_margin": 0.0,
                "search_evidence": None,
            }
        )


def test_graph_tie_breaks_follow_canonical_relation_bytes() -> None:
    tie = _tie_graph()
    runner = tie.runner_up_alternative
    assert runner is not None
    assert tie.runner_up_margin == 0.0
    with pytest.raises(
        ValidationError, match="follow the best path's canonical ordering"
    ):
        tie.model_copy(
            update={
                "best_alternative": runner,
                "runner_up_alternative": tie.best_alternative,
                "search_evidence": None,
            }
        )


def test_graph_acceptance_must_agree_with_quarantine_reasons() -> None:
    graph = _graph()
    with pytest.raises(ValidationError, match="accepted graphs cannot contain"):
        graph.model_copy(
            update={"quarantine_reasons": (MatchQuarantineReason.LOW_MARGIN,)}
        )
    with pytest.raises(ValidationError, match="require at least one quarantine reason"):
        graph.model_copy(update={"accepted": False})


def test_graph_ties_and_low_margins_must_be_quarantined() -> None:
    tie = _tie_graph()
    assert not tie.accepted
    assert tie.quarantine_reasons == (MatchQuarantineReason.TIE,)
    with pytest.raises(ValidationError, match="accepted graph must quarantine tie"):
        tie.model_copy(update={"accepted": True, "quarantine_reasons": ()})
    with pytest.raises(ValidationError, match="reasons must include tie"):
        tie.model_copy(
            update={
                "quarantine_reasons": (MatchQuarantineReason.UNRESOLVED_CONTINUATION,)
            }
        )
    strict = match_documents(
        _doc("s", ["ab", "cd"]), _doc("t", ["ab", "cd"]), policy=_policy(5.0)
    )
    assert strict.quarantine_reasons == (MatchQuarantineReason.LOW_MARGIN,)
    with pytest.raises(
        ValidationError, match="accepted graph must quarantine low margin"
    ):
        strict.model_copy(update={"accepted": True, "quarantine_reasons": ()})
    with pytest.raises(ValidationError, match="reasons must include low margin"):
        strict.model_copy(
            update={
                "quarantine_reasons": (MatchQuarantineReason.STATE_LIMIT_EXHAUSTED,)
            }
        )


def _relations(*pairs: tuple[str, str]) -> tuple[MatchRelation, ...]:
    return tuple(_one_to_one(s, t, _same(2)) for s, t in pairs)


def test_graph_best_alternative_must_cover_every_token_in_physical_order() -> None:
    graph = _graph()
    with pytest.raises(ValidationError, match="cover every source token"):
        _replace_best(graph, _relations(("s0", "t0")))
    only_source = (
        _one_to_one("s0", "t0", _same(2)),
        MatchRelation(
            kind=MatchRelationKind.SOURCE_ONLY,
            source_token_ids=("s1",),
            target_token_ids=(),
            operations=(_op(_DELETE, (0, 2), (0, 0)),),
        ),
    )
    with pytest.raises(ValidationError, match="cover every target token"):
        _replace_best(graph, only_source)
    with pytest.raises(ValidationError, match="follow physical source document order"):
        _replace_best(graph, _relations(("s1", "t0"), ("s0", "t1")))
    with pytest.raises(ValidationError, match="follow physical target document order"):
        _replace_best(graph, _relations(("s0", "t1"), ("s1", "t0")))


def test_graph_relations_must_name_tokens_of_their_own_documents() -> None:
    graph = _graph()
    with pytest.raises(ValidationError, match="unknown source token"):
        _replace_best(graph, _relations(("s0", "t0"), ("zz", "t1")))
    with pytest.raises(ValidationError, match="unknown target token"):
        _replace_best(graph, _relations(("s0", "t0"), ("s1", "zz")))


def test_graph_validates_the_runner_up_alternative_too() -> None:
    graph = _graph()
    broken = MatchAlternative(total_cost=4.0, relations=_relations(("s0", "t0")))
    with pytest.raises(ValidationError, match="cover every source token"):
        graph.model_copy(
            update={"runner_up_alternative": broken, "search_evidence": None}
        )


@pytest.mark.parametrize(
    ("operations", "message"),
    [
        ((_op(_MATCH, (0, 1), (0, 1)),), "partition source graphemes exactly"),
        (
            (_op(_MATCH, (0, 1), (0, 1)), _op(_DELETE, (1, 2), (1, 1))),
            "partition target graphemes exactly",
        ),
        (
            (_op(_MATCH, (0, 2), (0, 2)), _op(_MATCH, (1, 2), (1, 2))),
            "monotonic and non-overlapping",
        ),
        (
            (_op(_MATCH, (0, 1), (0, 1)), _op(_MATCH, (0, 2), (1, 2))),
            "monotonic and non-overlapping",
        ),
        ((_op(_MATCH, (1, 2), (0, 1)),), "partition source graphemes without gaps"),
        ((_op(_MATCH, (0, 1), (1, 2)),), "partition target graphemes without gaps"),
        ((_op(_MATCH, (0, 3), (0, 2)),), "source grapheme range exceeds"),
        ((_op(_MATCH, (0, 2), (0, 3)),), "target grapheme range exceeds"),
    ],
)
def test_graph_relation_operations_must_partition_both_token_texts(
    operations: tuple[MatchOperation, ...], message: str
) -> None:
    relations = (_one_to_one("s0", "t0", operations), _one_to_one("s1", "t1", _same(2)))
    with pytest.raises(ValidationError, match=message):
        _replace_best(_graph(), relations)


def test_graph_accepts_insert_and_delete_operations_that_partition_the_texts() -> None:
    ops = (
        _op(_DELETE, (0, 1), (0, 0)),
        _op(_INSERT, (1, 1), (0, 1)),
        _op(_MATCH, (1, 2), (1, 2)),
    )
    relations = (_one_to_one("s0", "t0", ops), _one_to_one("s1", "t1", _same(2)))
    assert _replace_best(_graph(), relations).accepted


def _reference_relation(reference: MatchContinuationReference) -> MatchRelation:
    return MatchRelation(
        kind=MatchRelationKind.SOURCES_TO_ONE,
        source_token_ids=("s0", "s1"),
        target_token_ids=("t0",),
        operations=(_op(_MATCH, (0, 2), (0, 2)),),
        continuation_references=(reference,),
    )


def test_graph_continuation_references_must_match_a_document_side() -> None:
    source = MatchDocument(
        document_id="s",
        pages=(
            MatchPage(
                page_id="sp",
                lines=(
                    MatchLine(
                        line_id="sl",
                        tokens=(
                            _tok("s0", "a", (_ar(0),)),
                            _tok("s1", "b", (_ar(1),)),
                        ),
                    ),
                ),
            ),
        ),
    )
    target = _doc("t", ["ab"])
    policy = _policy(0.0)

    def graph_with(reference: MatchContinuationReference) -> MatchGraph:
        best = MatchAlternative(
            total_cost=0.0, relations=(_reference_relation(reference),)
        )
        return MatchGraph(
            source_document=source,
            target_document=target,
            policy=policy,
            best_alternative=best,
            runner_up_alternative=None,
            runner_up_margin=None,
            accepted=True,
            quarantine_reasons=(),
        )

    assert graph_with(_reference()).accepted
    with pytest.raises(ValidationError, match="provenance does not match"):
        graph_with(_reference(left_fragment_grapheme_ranges=(_ar(7),)))


def _exhausted(graph: MatchGraph, evidence: MatchSearchEvidence) -> MatchGraph:
    return graph.model_copy(
        update={
            "runner_up_alternative": None,
            "runner_up_margin": None,
            "accepted": False,
            "quarantine_reasons": (MatchQuarantineReason.STATE_LIMIT_EXHAUSTED,),
            "search_evidence": evidence,
        }
    )


def test_graph_search_evidence_must_agree_with_the_alternatives() -> None:
    graph = _graph()
    evidence = graph.search_evidence
    assert evidence is not None
    best_path = evidence.best_complete_path
    assert best_path is not None
    runner_path = evidence.runner_up_complete_path
    assert runner_path is not None

    def with_evidence(**overrides: object) -> MatchGraph:
        updated = MatchSearchEvidence.model_validate(
            {**evidence.model_dump(), **overrides}
        )
        return graph.model_copy(update={"search_evidence": updated})

    assert with_evidence().graph_id == graph.graph_id
    wrong_cost = _path(cost=best_path.total_cost + 0.5, relations=best_path.relations)
    with pytest.raises(ValidationError, match="best complete search path must match"):
        with_evidence(best_complete_path=wrong_cost, runner_up_complete_path=None)
    with pytest.raises(ValidationError, match="runner complete search path presence"):
        with_evidence(runner_up_complete_path=None)
    wrong_runner = _path(
        cost=runner_path.total_cost + 1.0, relations=runner_path.relations
    )
    with pytest.raises(ValidationError, match="runner complete search path must match"):
        with_evidence(runner_up_complete_path=wrong_runner)


def test_graph_without_a_complete_search_path_requires_a_resource_limit_reason() -> (
    None
):
    graph = _graph()
    no_path = _evidence()
    exhausted = _exhausted(graph, no_path)
    assert not exhausted.accepted
    with pytest.raises(ValidationError, match="without a best complete path requires"):
        exhausted.model_copy(
            update={
                "quarantine_reasons": (MatchQuarantineReason.UNRESOLVED_CONTINUATION,)
            }
        )
