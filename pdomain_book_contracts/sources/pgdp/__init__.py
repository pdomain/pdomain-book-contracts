"""
PGDP round readers: the shared container and the F2 markup format.

Will own ``rounds.py`` (renamed from ``pgdp_results.py``, since it reads any
round rather than one thing called a result) and ``offsets.py`` (moved up
from ``f2/``, since it reads the round-JSON container that every PGDP round
shares and carries no F2-specific markup), plus ``f2/tokens.py``,
``f2/parser.py``, ``f2/project_rules.py``, and ``f2/warnings.py`` for the
markup genuinely specific to F2. Moved from ``pdomain_book_tools.pgdp``.
Depends on ``typography`` and ``text``.

Empty pending the code move in a later task.
"""

from __future__ import annotations
