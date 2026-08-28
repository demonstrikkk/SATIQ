# ADR — Architecture Decision Records (Satiq)

> Use ADRs for any decision that changes **behavior, data handling, storage, APIs, dependencies, or model/prompt strategy**. Line items in `docs/DECISIONS.md` alone are not enough for these.

## When You Need an ADR

* Library / model / checkpoint selection (e.g., CROMA vs. dual encoders, GroundingDINO vs. alternatives)
* Schema change (`raster_asset`, `analysis_result`), API contract change
* CRS / resolution / band handling, pairing / co-registration strategy, fusion method (cross-attention vs. concat)
* Prompt strategy, tool-calling schema, supervisor/critic policy
* Adding a dependency, changing `docker-compose.yml` topology
* Privacy / tenancy / retention / credential handling

If unsure: write the ADR. Cost is low; untracked decisions are expensive.

## Numbering

Sequential `NNNN` — zero-padded, monotonic. Next available after `0001` is `0002`.

## Template

Copy this into `docs/adr/NNNN-title.md` (kebab-case title, e.g., `0002-crs-hard-gate.md`):

```markdown
# ADR 000N — Title

* **Date:** YYYY-MM-DD
* **Status:** Proposed | Accepted | Rejected | Superseded by ADR XXXX
* **Scope:** orchestrator / capabilities / gateway / frontend / adaptation / evaluation / repo
* **Commit/PR:** <hash or PR link> (fill after merge)
* **Deciders:** <agents/humans>

## Context

What problem are we solving? What constraints (compute, hackathon time, dataset, CRS correctness)?

## Decision

What we will do, in one paragraph + bullet specifics.

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| ... | ... |

## Consequences

* Positive:
* Negative / risks:
* Follow-ups (update PROGRESS, TODOs):

## Verification

How will we prove it works? (tests, benchmark, compose check — paste command/output later)
```

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0000](0000-scaffold.md) | Initialize monorepo scaffold | Accepted | 2026-08-26 |
| [0001](0001-agent-governance.md) | Agent governance docs | Accepted | 2026-08-26 |
| [0003](0003-frontend-workstation.md) | Frontend Analysis Workstation (Phase 0–12) | Accepted | 2026-08-28 |

## Existing ADRs

* `0000-scaffold.md` — scaffold + build priority
* `0001-agent-governance.md` — agent workflow + traceability
* `0003-frontend-workstation.md` — frontend workstation (Phase 0–12)

Create new ADRs by copying the template above. Link them from `docs/DECISIONS.md` Index and from this table.
