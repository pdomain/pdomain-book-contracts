# pdomain-book-contracts

## Agent Index

- **Kind:** usage
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-09-02
- **Provenance:** agent-authored at repository creation.
- **Disposition:** Retained as the project entry point.

Pure-Python contracts shared across the `pdomain-*` OCR suite: geometry value
types, typography and matching algorithms, OCR result types, layout
contracts, and the PGDP round readers. See
[the documentation map](docs/README.md) and [`AGENTS.md`](AGENTS.md) for
contributor and agent guidance.

## Why

Historically `pdomain-book-tools` held both the pure-Python contracts and the
imaging stack (cv2, numpy, torch, doctr) that reads and corrects scanned
pages. A consumer that only wanted one value type — a `Point`, a matched
span, a PGDP page — paid for the entire imaging stack anyway, because the
root package eagerly imported it. `pdomain-book-contracts` is the light
third: the value types, contracts, and pure algorithms that need nothing
beyond pydantic, pydantic-core, shapely, and regex.

`pdomain-book-tools` depends on this package and re-exports its names, so
existing imports through `pdomain-book-tools` keep working. Nothing depends
on `pdomain-book-contracts` in the other direction.

## Status

This repository currently holds an empty skeleton: the package layout,
gate, and lightness test exist, but no contract has moved here yet. Each
subpackage's `__init__.py` docstring names what it will own. The code moves
from `pdomain-book-tools` in a later task of the `pdomain-ops` extraction
plan (`docs/plans/2026-09-01-extract-book-contracts-and-retire-pd-repos.md`),
following the layout in the `pdomain-ops` book-contracts module layout spec
(`docs/specs/2026-09-02-book-contracts-module-layout.md`).

## Install

```bash
pip install pdomain-book-contracts
```

## Development

```bash
make setup   # uv sync
make ci      # lint, typecheck, test, build, docgraph check
```

See [`AGENTS.md`](AGENTS.md) for the full command reference.
