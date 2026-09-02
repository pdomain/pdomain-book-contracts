# Conventions — pdomain-book-contracts

## Agent Index

- **Kind:** process
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-09-02
- **Provenance:** agent-authored at repository creation, following the
  workspace-shared conventions block used across sibling repositories.
- **Disposition:** Retained as authoritative repository conventions.

Read this with [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md), and the
documentation rules in [`DOCGRAPH.md`](DOCGRAPH.md).

## Rule: No heavy dependency, ever

**The rule.** This package's dependencies are pydantic, pydantic-core,
shapely, and regex — nothing else. Never add torch, doctr, torchvision, cv2,
numpy, pandas, matplotlib, ipython, or transformers, even as a test-only or
optional dependency. Code that needs any of those belongs in
`pdomain-book-tools`, not here.

**Why.** This package exists so a consumer that wants one pure-Python
contract does not pay for an imaging stack. A single heavy import defeats the
entire reason the package was split out.

**Common high-confidence violations** (bot auto-fix candidates)

- Any of the blocked names added to `[project] dependencies` or
  `[dependency-groups]` in `pyproject.toml`.
- A module-level `import numpy`, `import cv2`, `import torch`, or similar
  anywhere under `pdomain_book_contracts/`.

**Common judgment-call violations** (bot flags, CT decides)

- A `TYPE_CHECKING`-only import of a `pdomain-book-tools` type (e.g. `Block`,
  `Page`, `Word`) for an annotation. This does not break the runtime
  boundary, but it does mean the package cannot type-check alone; see the
  book-contracts module layout spec in `pdomain-ops` before adding one.

<!-- workspace-conventions:start -->

## Rule: Do not read this package's coverage as a pass

This package enforces no coverage floor. Its own 12 tests reach 36 percent, and the code is
actually exercised by `pdomain-book-tools`' suite through the re-export shims, which measures
none of it. See
[extracted code left its coverage gate behind](docs/issues/2026-09-02-contracts-code-left-its-coverage-gate-behind.md).

Do not add a floor here until enough tests live here for the number to mean something, and
do not restore the gate by measuring this package from book-tools.

## Rule: Write docs clearly

**The rule.** Follow [Writing Style](docs/process/writing-style.md) for docs,
reports, issue text, PR text, and user-facing copy.

**Why.** Detailed style guidance belongs in a process doc. CONVENTIONS.md
should stay short.

## Rule: No comments explaining what code does

**The rule.** Don't add comments that restate what the code does;
well-named identifiers already do that. Only add a comment when the
WHY is non-obvious: a hidden constraint, a subtle invariant, or a
workaround for a specific bug.

**Why.** Comments rot when code changes and become misleading. The rule
also applies to docstrings — one short line max; no multi-paragraph
docstrings and no multi-line comment blocks.

**Common high-confidence violations** (bot auto-fix candidates)

- One-line summary comment immediately above a function that restates its name.
- `# returns the X` or `# sets the Y` before a return/assignment statement.
- Multi-line docstrings that explain every parameter with no non-obvious WHY.
- Section divider blocks: `# ---…---` / `# ===…===` multi-line banners used as
  navigation headers in test files — class names and blank lines already
  provide structure; remove the banner, keep the blank lines.
- Multi-paragraph module or class docstrings with a "Focus on:" / "Covers:"
  section — collapse to a single-line summary.

**Common judgment-call violations** (bot flags, CT decides)

- Comments that reference the PR, issue, or task that introduced the code — belongs in commit message, not source.
- Multi-line preamble that mixes WHY (worth keeping) with WHAT (worth removing).

## Rule: Unicode escape sequences for ruff-flagged ambiguous characters

**The rule.** Characters ruff flags under RUF001/002/003 (ambiguous Unicode —
curly quotes, en-dashes, em-dashes, multiplication signs, non-breaking spaces,
etc.) must be written as `\uXXXX` escape sequences in string and docstring
literals. In comments, replace with the plain ASCII equivalent. In every case
include a short inline comment naming the character, e.g.
`"""  # LEFT DOUBLE QUOTATION MARK`.

**Why.** Literal curly quotes and dashes are visually indistinguishable from
ASCII equivalents in most editors and diff views, making string comparisons and
grep silently fragile. Escape sequences make intent explicit and are safe across
all encodings. `# noqa: RUF00x` masks the problem instead of fixing it.

**Common high-confidence violations** (bot auto-fix candidates)

- A string literal containing `"hello – world"` written with the literal
  `–` character instead of the escape sequence.
- `# noqa: RUF001`, `# noqa: RUF002`, or `# noqa: RUF003` suppressions instead
  of escape sequences.
- `RUF002` or `RUF003` added to `[tool.ruff.lint] ignore` in `pyproject.toml`
  to paper over ambiguous characters.

**Common judgment-call violations** (bot flags, CT decides)

- Test strings that intentionally exercise curly-quote round-trip and must
  contain the literal character — keep the literal with an explicit
  `# noqa: RUF001  # intentional: testing curly-quote round-trip` comment
  that names the character and states the reason.

## Rule: Use `uv run` for all Python and tool invocation

**The rule.** Invoke Python, pytest, ruff, and basedpyright through `uv run`.
Never call bare `python`, `python3`, or `pytest` from a Makefile target or CI
step.

**Why.** Direct invocation skips the project's `.venv` and the lockfile-pinned
toolchain; tests pass locally and fail in CI (or vice versa) because the bare
interpreter sees different installed package versions. `uv run` is uniformly
fast (<200 ms warm) and always selects the project venv.

**Common high-confidence violations** (bot auto-fix candidates)

- `python -m pytest` or `python3 script.py` in any `Makefile` or CI step.
- `ruff check` or `basedpyright` (bare) in scripts that don't activate a venv first.

**Common judgment-call violations** (bot flags, CT decides)

- One-off REPL commands typed in CT's interactive shell — out of scope for this rule.

## Rule: Document every lint-rule suppression

**The rule.** Prefer fixing the underlying issue; suppress a lint rule only
when the deviation is genuinely correct. When a suppression *is* warranted —
`# pyright: ignore[...]`, `# noqa: ...`, or a `[tool.ruff.lint]` `ignore` /
`per-file-ignores` entry — it must (1) carry a short inline rationale at the
point of deviation explaining *why* the suppression is safe, and (2) be
catalogued in [`docs/process/lint-deviations.md`](docs/process/lint-deviations.md),
which records the rule, the tool, the file locations, and the justification.
Use basedpyright's native `# pyright: ignore[reportRuleName]` form —
mypy-style `# type: ignore[code]` codes are not honored by basedpyright.

**Why.** A bare suppression hides whether the deviation was a deliberate,
reviewed decision or a shortcut, and rots silently when the surrounding code
changes. The inline comment makes intent visible where the code is read; the
central doc makes the whole suppression set auditable in one place so it can't
quietly grow.

**Common high-confidence violations** (bot auto-fix candidates)

- A `# pyright: ignore` or `# noqa` with no adjacent comment stating why the
  suppression is safe.
- mypy-style `# type: ignore[import-not-found]` used to suppress a basedpyright
  diagnostic — replace with `# pyright: ignore[reportMissingImports]`.
- A bare unscoped `# type: ignore` / `# noqa` with no bracketed rule code.

**Common judgment-call violations** (bot flags, CT decides)

- A suppression whose inline rationale exists but is missing from
  [`docs/process/lint-deviations.md`](docs/process/lint-deviations.md) — CT
  decides whether to catalogue it or remove the suppression.
- A long-standing suppression whose stated rationale no longer holds after a
  refactor — CT decides whether to drop the suppression.

<!-- workspace-conventions:end -->
