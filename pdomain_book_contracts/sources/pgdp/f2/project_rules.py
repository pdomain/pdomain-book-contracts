"""Evidence-bound project overrides for PGDP F2 formatting tags."""

from __future__ import annotations

import hashlib
import string
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import field_validator, model_validator

from pdomain_book_contracts.typography.labels import StyleLabel
from pdomain_book_contracts.typography.spans import CanonicalModel

if TYPE_CHECKING:
    from collections.abc import Sequence

_ProjectTag = Literal["f", "u"]
_FONT_CHANGE_LABELS = frozenset(
    {
        StyleLabel.FONT_BLACKLETTER,
        StyleLabel.FONT_ANTIQUA,
        StyleLabel.FONT_UPRIGHT_IN_ITALIC,
        StyleLabel.FONT_OTHER_REVIEWED,
    }
)


class ProjectRule(CanonicalModel):
    """One reviewed formatting rule bound to exact Project Comments bytes."""

    project_id: str
    project_comments_sha256: str
    tag_name: _ProjectTag
    label: StyleLabel
    rule_ref: str

    @field_validator("project_comments_sha256")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if len(value) != 64 or any(
            character not in string.hexdigits for character in value
        ):
            msg = "project_comments_sha256 must be a 64-character hexadecimal SHA-256"
            raise ValueError(msg)
        return value.lower()

    @model_validator(mode="after")
    def _validate_tag_label(self) -> ProjectRule:
        if self.tag_name == "u" and self.label is not StyleLabel.UNDERLINE:
            msg = "u rules must assign the underline label"
            raise ValueError(msg)
        if self.tag_name == "f" and self.label not in _FONT_CHANGE_LABELS:
            msg = "f rules must assign an approved font-change label"
            raise ValueError(msg)
        return self


@dataclass(frozen=True)
class ProjectRuleRegistry:
    """Immutable reviewed rules selected only by project and comment hash."""

    rules: tuple[ProjectRule, ...] = ()

    def __init__(self, rules: Sequence[ProjectRule] = ()) -> None:
        frozen_rules = tuple(rules)
        keys = {
            (rule.project_id, rule.project_comments_sha256, rule.tag_name)
            for rule in frozen_rules
        }
        if len(keys) != len(frozen_rules):
            msg = "project rules must have unique project, comments hash, and tag keys"
            raise ValueError(msg)
        object.__setattr__(self, "rules", frozen_rules)

    def resolve(
        self,
        project_id: str | None,
        project_comments_bytes: bytes | None,
        tag_name: str,
    ) -> ProjectRule | None:
        """Return the exact reviewed rule, without inspecting comments heuristically."""
        if project_id is None or project_comments_bytes is None:
            return None
        comments_hash = hashlib.sha256(project_comments_bytes).hexdigest()
        for rule in self.rules:
            if (
                rule.project_id == project_id
                and rule.project_comments_sha256 == comments_hash
                and rule.tag_name == tag_name
            ):
                return rule
        return None
