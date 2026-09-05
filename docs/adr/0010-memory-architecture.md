# ADR 0010 — Proper Memory System (4-Tier, Hybrid Retrieval, TTL, Observability)

* **Date:** 2026-09-05
* **Status:** Accepted (builds on ADR 0008/0009, replaces ad-hoc SQLite+Chroma stitching)
* **Scope:** orchestrator/memory/*, services/conversation.py, agents/planner, API, gateway
* **Commit/PR:** `wip`
* **Deciders:** OpenCode + human

## Context

After ADR 0009 the memory was a 2-store patchwork: `rag_store.py` (single Chroma collection `satiq_conversation`, vector cosine only, no BM25, no time-decay, no TTL), `services/conversation.py` (SQLite + MEM_HISTORY + disk `history/*.json` triple-write, fire-and-forget RAG without await, `load_history_hybrid` deduped by substring `query in doc`), `entity_registry.py` (bbox only), and `core/redis_state.py` (1h EXECUTIONS) plus gateway `assetStore` (1h). No semantic distillation, no forgetting, no `GET /memory` observability. Web research (May 2026 TACNODE/Mem0/Zep) shows production agents need 4 tiers — working, episodic, semantic, state — with hybrid vector+BM25, time-decay, and consolidation not per-turn semantic writes. Satiq is constrained: `45s` budget, single-GPU, `100Mpix`, no GraphRAG overhead, Ollama-only.

## Decision

Implement **4-tier memory** with constrained workloads:

| Tier | Store | TTL | Write rule | Retrieve |
|------|-------|-----|------------|----------|
| **Working** | in-context `history[-3]` + `entity_registry` | 45s thread | always ( <1k tokens) | direct |
| **Episodic** | Chroma `satiq_conversation` (HNSW cosine) | 90 days | append-only every turn via `add_turn` with `ts` | hybrid 0.7 vector + 0.3 BM25 overlap, session boost, `threshold 0.72`, `top_k 6` |
| **Semantic** | Chroma `satiq_semantic` (new) | 180 days | via `consolidate()` every 4 turns or AOI repeat, `extract_semantic_fact` rule-based (AOI/sensor/bbox/CRS/temporal), provenance + confidence 0.75 | vector `threshold 0.6`, `top_k 3` |
| **State** | Redis `satiq:exec:{id}` + `gateway assetStore` + SQLite `conversation_history (50 per session)` | 1h / 1h / persistent | authoritative live | direct |

**Key files:**
- `memory/rag_store.py` — dual collections, `add_semantic`, `retrieve` hybrid, `retrieve_semantic`, `ttl_cleanup(90/180)`, `clear_collection` both
- `memory/memory_orchestrator.py` *(new)* — `build_working_context`, `retrieve_episodic` (time-decay `exp(-age/168h)`), `extract_semantic_fact`, `retrieve_for_planner` (working+episodic+semantic merged 1200 chars), `consolidate` trigger
- `services/conversation.py` — `load_history_hybrid` now delegates to `retrieve_episodic` (hybrid score sort), `save_history` now `create_task(add_turn)` + `create_task(consolidate)` with metadata `image_ids`, TTL cleanup via `DELETE ... LIMIT 50`
- `memory/entity_registry.py` — pronouns (`it/that area/that water body`), `image_*_id`, `crs`, `ts` tagging, `ts` in resolution for recency
- `agents/planner_agent.py:104` — RAG now `retrieve_for_planner` (4-tier merged), falls back to `load_history_hybrid`
- `api/main.py:775` — `GET /api/v1/memory/{session_id}?n=5` (history+episodic), `DELETE /api/v1/memory/{session_id}` (SQLite + disk + Chroma both, scoped by `session_id`, rebuild from retained)

Isolation: all ops scoped by `session_id` (tenant = session). No cross-session leakage; `DELETE` propagates to indexes or rebuilds.

## Alternatives Considered

| Alt | Why not |
|-----|---------|
| Mem0/Letta/Zep managed service | External dep, SIH offline demo budget, adds latency; Chroma+SQLite already provisioned |
| GraphRAG (Neo4j) now | Satiq single-node spatial QA needs keyword+vector, not multi-hop `supplier-of-supplier`; deferred per ADR 0009 |
| Per-turn direct semantic writes | Violates TacNODE rule: write via consolidation not turn loop; would poison semantic with low-confidence facts |
| Long-context stuffing | 93.4% cost per TacNODE; Satiq `45s` budget needs tiered retrieval not 1M window |

## Consequences

* Positive: hybrid fixes recall+precision over pure vector (BM25 catches exact SKUs/error codes), time-decay prevents stale AOI, consolidation reduces redundancy, `/memory` gives observability + GDPR-like deletion, TTL sweep via `ttl_cleanup()` caps Chroma growth (<1M vectors, decision matrix dev/prototype range).
* Negative: two Chroma collections double upsert cost (still <10ms per turn, mocked in tests); `consolidate` fire-and-forget may skip if no running loop (sync test) — acceptable, next async turn catches.
* Follow-ups: schedule `ttl_cleanup` in `_periodic_disk_cleanup` (weekly), benchmark recall with `tests/e2e/replay` extended, add `GET /memory/export`.

## Verification

* `python -m py_compile memory/rag_store.py memory/memory_orchestrator.py memory/entity_registry.py services/conversation.py agents/planner_agent.py api/main.py` → 0
* `pytest tests/e2e/test_replay.py` → 7 passed (unchanged)
* Manual: `curl GET /api/v1/memory/{sid}` returns `history` + `episodic_hits` scoped; `DELETE` clears both collections + SQLite + disk
