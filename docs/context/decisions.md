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

### 2026-11-13 — Retired: coverage-floor branch handoff

- Old path: `docs/handoff/2026-11-11-043740-coverage-floor-and-geometry-fixes-committed.md`.
- Outcome: implemented branch work; obsolete review-and-merge resume instructions retired.
- Superseded by: [Geometry and input validation](../architecture/geometry-and-validation.md) and the [coverage floor](../architecture/00-overview.md#just-test-enforces-a-95-percent-coverage-floor).
- Evidence: merge `175078d` contains the handoff branch through `673e5d9`; `47347a6`, `0f1f9c5`, `88b2cc7`, and `c379be3` are ancestors of local master. The baseline at `1b1605a` passed 1,324 tests at 96.92 percent on 2026-11-13.
- Rationale kept: the [archived handoff](../_archive/handoff/2026-11-11-043740-coverage-floor-and-geometry-fixes-committed.md) preserves the independent-review history, compatibility warning, and unscanned stored-NaN risk. Its [earlier measurement](../_archive/handoff/2026-11-11-032241-coverage-tests-committed-floor-left-at-a-probe-value.md) records 1,312 tests at 96.90 percent across Python 3.11 to 3.13. Those are historical results, distinct from this migration's baseline.
- Remaining work: consumer-suite verification, infinity policy, two coordinate-flag defects, and test ownership remain in the [roadmap](../plans/roadmap.md) and [intent map](intent-map.md). No consumer issue is closed by this migration.
- Removal commit: the migration manifest records the commit that archives the old path. No source behavior changed.

### 2026-11-13 — Retain current guidance and unresolved roadmap

- **Context:** The migration reviewed architecture, plans, process guidance, context, and handoffs against source, tests, and commits.
- **Decision:** Keep the roadmap active because its lazy import, docstring, geometry, test-ownership, and conditional extraction work remains unfinished. Keep `CODEX.md` as the short tool entry point that delegates to `DOCGRAPH.md`.
- **Rationale:** A shipped subset does not complete the roadmap. The retired coverage issue stays in place because conventions still cite its September measurements and rejected consumer-coverage approach. The shared no-floor text in `CONVENTIONS.md` remains explicitly overridden by that file's repository-specific 95 percent rule; this migration does not change shared policy.
- **Evidence:** `sources/pgdp/__init__.py` still imports F2 eagerly; `matching/match_type.py` retains the two deferred members as comments; `geometry/point.py` rejects NaN but accepts infinity. The final section of `CONVENTIONS.md` and `pyproject.toml` establish the current floor.
- **Remaining work:** The existing owner decisions in the intent map remain unresolved. No new repository or policy change is authorized by this retention decision.
