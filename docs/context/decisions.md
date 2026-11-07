# Durable decisions

## Agent Index

- **Kind:** process
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-11-06
- **Read when:** investigating why the package boundary or layout is what it
  is.
- **Search terms:** decisions, dependency boundary, package layout.

### 2026-09-02 — Dependency set fixed at pydantic, pydantic-core, shapely, regex

- **Context:** The package exists to let a consumer depend on one pure-Python
  contract without pulling in an imaging stack.
- **Decision:** Limit dependencies to pydantic, pydantic-core, shapely, and
  regex. No other runtime dependency, including test-only or optional ones,
  may be added.
- **Rationale:** Any heavier dependency defeats the reason the package was
  split out of `pdomain-book-tools`.
- **Evidence:** `pyproject.toml`; `tests/test_torch_free_import.py`.
- **Supersedes / Superseded-by:** None.

### 2026-09-02 — AGENTS.md is canonical; CLAUDE.md is a symlink

- **Context:** Sibling repositories are inconsistent: some make `CLAUDE.md`
  the canonical file, others symlink it to `AGENTS.md`.
- **Decision:** `AGENTS.md` holds the real content; `CLAUDE.md` is a symlink
  to it, matching `pdomain-source-data`.
- **Rationale:** `pdomain-source-data` is the most recently created sibling
  and the explicit model for this repository's setup.
- **Evidence:** `AGENTS.md`; `CLAUDE.md`.
- **Supersedes / Superseded-by:** None.

### 2026-11-06 — typing-extensions is an allowed runtime dependency

- **Context:** The 2026-09-02 dependency decision named pydantic,
  pydantic-core, shapely, and regex. It said no other runtime dependency
  may be added. The geometry, typography, and matching modules import
  `typing_extensions.override` when Python is older than 3.12. This package
  requires Python 3.11 or newer, and older than 3.14.
- **Decision:** Allow `typing-extensions` as a runtime dependency. Allow no
  other addition. The blocked imaging and machine-learning libraries stay
  blocked.
- **Rationale:** `override` is in the standard library only from Python 3.12.
  On 3.11 the backport has to be declared. Otherwise those modules fail to
  import.
- **Evidence:** `pyproject.toml` declares `typing-extensions>=4.16,<5`. The
  version check is in these files:
  - `pdomain_book_contracts/geometry/point.py`
  - `pdomain_book_contracts/geometry/bounding_box.py`
  - `pdomain_book_contracts/typography/records.py`
  - `pdomain_book_contracts/typography/book_manifest.py`
  - `pdomain_book_contracts/matching/models.py`
  - `pdomain_book_contracts/matching/pgdp_continuations.py`
- **Supersedes / Superseded-by:** Supersedes the "no other runtime
  dependency" clause of the 2026-09-02 dependency decision. The rest of
  that decision still stands.
