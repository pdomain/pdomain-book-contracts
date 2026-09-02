"""Genuinely F2-specific PGDP markup: tokens, the parser, rules, and warnings.

Owns ``tokens.py``, ``parser.py``, ``project_rules.py``, and ``warnings.py``,
moved unchanged in name from ``pdomain_book_tools.pgdp.f2``. The round-JSON
container reader that used to live alongside them, ``offsets.py``, moved up
to ``sources.pgdp`` instead, since it carries no F2-specific markup handling
— see that package's docstring. Depends on ``typography`` and ``text``.
"""

from __future__ import annotations

from pdomain_book_contracts.sources.pgdp.f2.parser import F2Parser
from pdomain_book_contracts.sources.pgdp.f2.project_rules import (
    ProjectRule,
    ProjectRuleRegistry,
)
from pdomain_book_contracts.sources.pgdp.f2.tokens import (
    F2JsonDocument,
    F2JsonPage,
    F2NormalizationKind,
    F2NormalizationOperation,
    F2PageTokens,
    F2Token,
    F2TokenKind,
    F2Warning,
    read_f2_json,
    read_f2_json_page,
    tokenize_f2,
)
from pdomain_book_contracts.sources.pgdp.f2.warnings import (
    F2ParseWarning,
    warning_blocks_training,
)

__all__ = [
    "F2JsonDocument",
    "F2JsonPage",
    "F2NormalizationKind",
    "F2NormalizationOperation",
    "F2PageTokens",
    "F2ParseWarning",
    "F2Parser",
    "F2Token",
    "F2TokenKind",
    "F2Warning",
    "ProjectRule",
    "ProjectRuleRegistry",
    "read_f2_json",
    "read_f2_json_page",
    "tokenize_f2",
    "warning_blocks_training",
]
