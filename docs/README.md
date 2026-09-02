# docs/

## Agent Index

- **Kind:** process
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-09-02
- **Read when:** navigating repository documentation.
- **Search terms:** documentation map, docs layout, folder purpose.

Start with the [current state](context/current-state.md), [intent
map](context/intent-map.md), and [durable decisions](context/decisions.md).
Process references include the [writing style](process/writing-style.md) and
[lint suppression catalogue](process/lint-deviations.md).

How documentation is organized in this repo.

| Folder | Purpose | Use when |
| --- | --- | --- |
| `architecture/` | Durable reference — how the system works today. | Capturing current shape (modules, data flow, contracts, current-state diagrams). |
| `archive/` | Cold storage. Mirrors the nine active folders. | A doc is no longer in force (shipped, superseded, abandoned). |
| `decisions/` | ADRs — dated, append-only "we chose X because Y." | Recording a specific design choice with context, alternatives, consequences. |
| `plans/` | Active execution — what order to make a spec real. | Sequencing work for an approved spec. |
| `process/` | Cross-cutting workflow conventions. | Capturing how the team works, not what the system does. |
| `research/` | Investigation in progress. Messy by design. | Exploring before committing to a design. |
| `runbooks/` | Operational reference — something is broken or being operated. | An on-call or ops task needs a recipe. |
| `specs/` | Aspirational, pre-implementation design. | Describing what to build, before code. |
| `templates/` | Issue, spec, plan, ADR boilerplate. | Adding a starter template for a new doc type. |
| `usage/` | Downstream reference — how to consume this library. | A user or integrator needs to know how to use it. |

Empty folders are intentional and tracked via `.gitkeep`.

This layout is workspace-standard; see the sibling repositories for the
master pattern.
