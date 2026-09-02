# Durable decisions

## Agent Index

- **Kind:** process
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-09-02
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
