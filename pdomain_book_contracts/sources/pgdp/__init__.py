"""PGDP round readers: the shared container and the F2 markup format.

Owns ``rounds.py`` (renamed from ``pgdp_results.py``, since it reads any
round rather than one thing called a result) and ``offsets.py`` (moved up
from ``f2/``, since it reads the round-JSON container that every PGDP round
shares and carries no F2-specific markup), plus ``f2/`` for the markup
genuinely specific to F2. Moved from ``pdomain_book_tools.pgdp``. Depends
on ``typography`` and ``text``.
"""

from __future__ import annotations

from pdomain_book_contracts.sources.pgdp import f2
from pdomain_book_contracts.sources.pgdp.offsets import (
    DecodedF2Character,
    LexicalF2Document,
    LexicalF2Index,
    LexicalF2Page,
    LexicalF2PageIndex,
    read_lexical_index,
    read_lexical_json,
    read_lexical_page,
)
from pdomain_book_contracts.sources.pgdp.rounds import PGDPExport, PGDPResults

__all__ = [
    "DecodedF2Character",
    "LexicalF2Document",
    "LexicalF2Index",
    "LexicalF2Page",
    "LexicalF2PageIndex",
    "PGDPExport",
    "PGDPResults",
    "f2",
    "read_lexical_index",
    "read_lexical_json",
    "read_lexical_page",
]
