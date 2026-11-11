from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from pdomain_book_contracts.sources.pgdp.f2.project_rules import (
    ProjectRule,
    ProjectRuleRegistry,
)
from pdomain_book_contracts.typography.labels import StyleLabel

_COMMENTS = b"Use <f> for blackletter."
_COMMENTS_SHA = hashlib.sha256(_COMMENTS).hexdigest()


def _rule(
    *,
    project_id: str = "proj1",
    sha: str = _COMMENTS_SHA,
    tag: str = "f",
    label: StyleLabel = StyleLabel.FONT_BLACKLETTER,
    ref: str = "ref-1",
) -> ProjectRule:
    return ProjectRule.model_validate(
        {
            "project_id": project_id,
            "project_comments_sha256": sha,
            "tag_name": tag,
            "label": label,
            "rule_ref": ref,
        }
    )


def test_hash_is_lowercased() -> None:
    assert _rule(sha=_COMMENTS_SHA.upper()).project_comments_sha256 == _COMMENTS_SHA


@pytest.mark.parametrize("sha", ["", "abc", "a" * 63, "a" * 65, "g" * 64])
def test_hash_must_be_64_hex_characters(sha: str) -> None:
    with pytest.raises(ValidationError, match="64-character hexadecimal"):
        _rule(sha=sha)


@pytest.mark.parametrize(
    "label",
    [
        StyleLabel.FONT_BLACKLETTER,
        StyleLabel.FONT_ANTIQUA,
        StyleLabel.FONT_UPRIGHT_IN_ITALIC,
        StyleLabel.FONT_OTHER_REVIEWED,
    ],
)
def test_f_rule_accepts_each_font_change_label(label: StyleLabel) -> None:
    assert _rule(tag="f", label=label).label is label


@pytest.mark.parametrize(
    "label", [StyleLabel.ITALIC, StyleLabel.UNDERLINE, StyleLabel.SMALL_CAPS]
)
def test_f_rule_rejects_non_font_labels(label: StyleLabel) -> None:
    with pytest.raises(ValidationError, match="approved font-change label"):
        _rule(tag="f", label=label)


def test_u_rule_must_assign_underline() -> None:
    assert _rule(tag="u", label=StyleLabel.UNDERLINE).tag_name == "u"
    with pytest.raises(ValidationError, match="underline label"):
        _rule(tag="u", label=StyleLabel.FONT_BLACKLETTER)


def test_rule_rejects_other_tag_names() -> None:
    with pytest.raises(ValidationError):
        _rule(tag="i", label=StyleLabel.ITALIC)


def test_empty_registry_resolves_nothing() -> None:
    assert ProjectRuleRegistry().rules == ()
    assert ProjectRuleRegistry().resolve("proj1", _COMMENTS, "f") is None


def test_registry_freezes_rules_into_a_tuple() -> None:
    rule = _rule()
    registry = ProjectRuleRegistry([rule])
    assert registry.rules == (rule,)


def test_registry_rejects_duplicate_project_hash_and_tag() -> None:
    with pytest.raises(ValueError, match="unique project, comments hash, and tag"):
        ProjectRuleRegistry([_rule(ref="a"), _rule(ref="b")])


def test_registry_allows_same_project_with_different_tag_hash_or_project() -> None:
    f_rule = _rule()
    u_rule = _rule(tag="u", label=StyleLabel.UNDERLINE)
    other_hash = _rule(sha=hashlib.sha256(b"other").hexdigest())
    other_project = _rule(project_id="proj2")
    registry = ProjectRuleRegistry([f_rule, u_rule, other_hash, other_project])
    assert len(registry.rules) == 4


def test_resolve_returns_rule_for_exact_project_hash_and_tag() -> None:
    f_rule = _rule()
    u_rule = _rule(tag="u", label=StyleLabel.UNDERLINE, ref="u-ref")
    registry = ProjectRuleRegistry([f_rule, u_rule])
    assert registry.resolve("proj1", _COMMENTS, "f") is f_rule
    assert registry.resolve("proj1", _COMMENTS, "u") is u_rule


def test_resolve_ignores_rules_when_any_key_part_differs() -> None:
    registry = ProjectRuleRegistry([_rule()])
    assert registry.resolve("proj2", _COMMENTS, "f") is None
    assert registry.resolve("proj1", _COMMENTS + b" ", "f") is None
    assert registry.resolve("proj1", _COMMENTS, "u") is None
    assert registry.resolve("proj1", _COMMENTS, "i") is None


def test_resolve_needs_both_project_id_and_comment_bytes() -> None:
    registry = ProjectRuleRegistry([_rule()])
    assert registry.resolve(None, _COMMENTS, "f") is None
    assert registry.resolve("proj1", None, "f") is None
