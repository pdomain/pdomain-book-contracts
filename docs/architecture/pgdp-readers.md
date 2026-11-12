---
Status: active
Owner: CT
Created: 2026-11-12
Last verified: 2026-11-12
Kind: architecture
---

# PGDP readers

## Agent Index

- **Kind:** architecture
- **Status:** active
- **Owner:** CT
- **Created:** 2026-11-12
- **Last verified:** 2026-11-12
- **Read when:** changing round JSON, the F2 parser, project rules, or layout hints from F2 tokens.
- **Search terms:** PGDP, F2, P3, rounds, offsets, lexical index, F2Parser.

PGDP round text is read in this package. The shared container is separate from F2 markup. There is no P3 markup module, because P3 text has no markup of its own.

`pdomain-pgdp-api-client` imports `PGDPExport` from `rounds.py` to read a mirrored project. That import currently loads more than `rounds.py`.

## The shared container

`rounds.py` holds `PGDPResults` and `PGDPExport`.

`PGDPResults` takes a png path and page text and derives processed lines and words.

`PGDPExport` reads a round export from JSON.

`offsets.py` reads the round-JSON container, a JSON object of page keys to page text. It tracks byte offsets into that payload. The readers are `read_lexical_index`, `read_lexical_page`, and `read_lexical_json`.

The types still carry F2 in the name: `LexicalF2Index`, `LexicalF2Page`, `LexicalF2Document`, `LexicalF2PageIndex`, and `DecodedF2Character`. The functions do not.

Every PGDP round shares this container. `pdomain-source-data` uses it for P3 as well as F2.

`offsets.py` used to live under `f2/`. It moved up because it contains no F2 markup.

## F2 markup

`f2/` is the markup that is actually F2.

- `tokens.py` tokenizes a page into `F2PageTokens` and can read an F2 JSON document.
- `parser.py` turns those tokens into a typography page record through `F2Parser`.
- `project_rules.py` holds `ProjectRule` and `ProjectRuleRegistry`.
- `warnings.py` classifies parse warnings, including `warning_blocks_training`.
- `structure.py` turns tokens into layout text hints.

A later round parser, or another source with its own container, would sit beside `f2/`. `sources/__init__.py` says that. No second source is implemented.

## What importing a round loads

`rounds.py` imports `regex` and the standard library. It does not import shapely.

`sources/pgdp/__init__.py` imports `f2` at package import time. Python runs that file before it runs `rounds.py`. On 2026-11-12, importing `PGDPExport` loaded the F2 parser, the typography package, annotation, layout, geometry, shapely, and numpy. It did not load `matching`, `ocr`, `text`, or `licensing`.

The chain is `f2` to `typography.records`. `records.py` imports `BoundingBox`. Importing any typography submodule also runs `typography/__init__.py`, which loads the rest of the typography package.

The api-client test says `PGDPExport` depends only on pydantic, shapely, and regex. It also says that the import carries none of the book-tools imaging stack. That imaging claim holds. The import does load shapely, because of the package init, not because `rounds.py` asks for it.
