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

Sequential `NNNN` — zero-padded, monotonic. Next available after `0003` is `0004`.

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
| [0002](0002-api-gateway.md) | Implement API gateway and rate limiter | Accepted | 2026-08-28 |
| [0003](0003-frontend-workstation.md) | Frontend Analysis Workstation (Phase 0–12) | Accepted | 2026-08-28 |
| [0004](0004-orchestrator-pipeline.md) | Orchestrator LangGraph Pipeline with Dummy Vision & Mocked Qwen 3.5 9B | Accepted | 2026-08-29 |
| [0005](0005-resilience-optimization.md) | Pipeline Resilience & Performance Optimization | Accepted | 2026-08-29 |
| [0006](0006-full-integration.md) | Full System Integration Frontend↔Gateway↔Orchestrator | Accepted | 2026-08-29 |
| [0007](0007-real-models.md) | Replace Dummy/Mock Models with Real Fine-Tuned Models | Accepted | 2026-08-31 |
| [0008](0008-pipeline-redesign-shims.md) | Pipeline Redesign Without Running — 8-Node Minimal Graph + Pluggable Shims (No Mocks) | Accepted | 2026-09-05 |
| [0009](0009-bounded-agentic-execution.md) | Bounded Hybrid-Agentic Execution (45s, Zero-Synthetic, Ollama-only) | Accepted | 2026-09-05 |
| [0010](0010-memory-architecture.md) | Proper Memory System (4-Tier, Hybrid Retrieval, TTL, Observability) | Accepted | 2026-09-05 |

## Existing ADRs

* `0000-scaffold.md` — scaffold + build priority
* `0001-agent-governance.md` — agent workflow + traceability
* `0002-api-gateway.md` — API gateway and rate limiter implementation
* `0003-frontend-workstation.md` — frontend workstation (Phase 0–12)
* `0004-orchestrator-pipeline.md` — orchestrator LangGraph pipeline with dummy vision & mocked Qwen
* `0005-resilience-optimization.md` — pipeline resilience (timeout, retry, circuit breaker, checkpoint, queue, TTL cache)
* `0006-full-integration.md` — full integration frontend↔gateway↔orchestrator (agentic bridge, mock LLM, Docker)
* `0007-real-models.md` — replace dummy/mocks with real fine-tuned models (GDINO+SAM, VQA, Change-VQA hybrid, CROMA)
* `0008-pipeline-redesign-shims.md` — 8-node minimal graph + pluggable shims, portability & honesty (no mocks, no C:/ absolutes)
* `0009-bounded-agentic-execution.md` — bounded hybrid-agentic locks + Phase 1 hardening (reflection cap 2, success_condition, replay cassette, health/tools)
* `0010-memory-architecture.md` — 4-tier memory (working/episodic/semantic/state), hybrid vector+BM25+decay, consolidation, TTL, /memory observability

Create new ADRs by copying the template above. Link them from `docs/DECISIONS.md` Index and from this table.
