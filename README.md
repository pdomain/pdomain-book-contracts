# pdomain-book-contracts

## Agent Index

- **Kind:** usage
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-11-12
- **Provenance:** agent-authored at repository creation.
- **Disposition:** Retained as the project entry point.

`pdomain-book-contracts` is pure-Python contracts shared across the
`pdomain-*` OCR suite. Those contracts are geometry value types, typography
and matching algorithms, OCR result types, layout contracts, and the PGDP
round readers.

See [the documentation map](docs/README.md) and [`AGENTS.md`](AGENTS.md) for
contributor and agent guidance.

## Why one value type cost the imaging stack

Historically `pdomain-book-tools` held both the pure-Python contracts and the
imaging stack of cv2, numpy, torch, and doctr. That stack reads and corrects
scanned pages.

A consumer that only wanted one value type paid for the entire imaging stack
anyway, because the root package eagerly imported it. Such a value type is,
for example, a `Point`, a matched span, or a PGDP page.

`pdomain-book-contracts` is the light third. It is the value types, contracts,
and pure algorithms. Runtime dependencies are pydantic, pydantic-core,
shapely, regex, and typing-extensions.

`pdomain-book-tools` depends on this package and re-exports its names, so
existing imports through `pdomain-book-tools` keep working.

Nothing depends on `pdomain-book-contracts` in the other direction.

## Shared contracts with a coverage floor

The package holds the shared contracts. The layout and the dependency
boundary are in the
[architecture overview](docs/architecture/00-overview.md).

Remaining work is the [roadmap](docs/plans/roadmap.md). No issue is open.
`make test` enforces a 95 percent coverage floor. See the
[issue index](docs/issues/README.md).

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
