# ADR 0009 — Bounded Hybrid-Agentic Execution (45s, Zero-Synthetic, Ollama-only)

* **Date:** 2026-09-05
* **Status:** Accepted (locks ADR 0008 posture; supersedes any generic agentic research proposal)
* **Scope:** orchestrator (graph, guardrails, error_handler, API health/tools), tests, docs, infra
* **Commit/PR:** `wip` branch `main`
* **Deciders:** OpenCode (Muse Spark) + human

## Context

After ADR 0008 Satiq is an 8-node LangGraph DAG (`input_validator→coreference→router→planner→task_agent→post_processing→error_handler→response_composer`) with 10 strict tool schemas, 4 real shims (`model{1..4}_shim.py`) that fail `MODEL_NOT_LINKED` when weights are absent, single-GPU `VRAM_SEMAPHORE(2)`, and a `45s TOTAL_BUDGET`. A generic agentic-research doc proposes unconstrained plan→decide→act→reflect loops with `web_search/web_fetch` and GraphRAG — incompatible with SIH `100Mpix` hard gate, CRS/band invariants (`docs/ETHICS.md:2`), and the Windows laptop where the system cannot run (no docker/GPU/weights; only `python -m py_compile` + `grep` verification).

## Decision

Satiq remains a **constrained hybrid-agentic system**: deterministic where geospatial truth matters, bounded-agentic where the path is unknown.

| Pattern | Generic impl | Satiq choice |
|---------|--------------|--------------|
| Planning | Unbounded decomposition + web sub-plans | Bounded `PlanSchema` max 10 steps, `validate_legality` per step |
| Tool use | Open web fetch / interpreter / social APIs | 10 schemas (`helpers/tool_schemas.py`) + Ollama function calling only |
| Reflection | Generator vs critic with re-querying | `post_processing` confidence gate with hard cap 2 reflection cycles |
| Orchestration | Multi-agent handoffs | Single 8-node DAG + `VRAM_SEMAPHORE(2)` — no distributed overhead |
| Memory | GraphRAG multi-hop traversal | Chroma `satiq_conversation` + Redis `satiq:exec:{id}` + SQLite |

**Rejections (explicit):** no `web_search/web_fetch`, no external code execution, no GraphRAG overlay (deferred until multi-orbit relational query demand exists), no MCP server until third-party SDK needed.

**Hardening (Phase 1, this ADR):**

1. **Per-step success_condition** in `PlanSchema` (`bbox_in_0_1`, `crs_valid`, `gsd_positive`) validated in `validate_plan`.
2. **Reflection cap 2** enforced as `MAX_REFLECTION_ITERATIONS=2` on the `post_processing → error_handler → router` retry edge (only `error_type==transient` retries; `permanent` never loops, preserving the `45s` budget).
3. **Deterministic replay cassette** `tests/e2e/replay.jsonl` + `tests/e2e/test_replay.py` cassetting `input_validator` rejections without live Ollama, enabling offline CI on the Windows host.
4. **Health + observability** `GET /health` includes `ollama_reachable` probe; `GET /api/v1/tools` serves the 10 schemas from `helpers/tool_schemas.py`.

## Alternatives Considered

| Alt | Why not |
|-----|---------|
| Full research-agent loop (web search, re-plan, GraphRAG) | Violates CRS truthfulness, blows `45s`/single-GPU, adds latency for SIH demo |
| Remove reflection cap | Risk runaway loop on `low_confidence` until budget exhaustion |
| GraphRAG now | Chroma+Redis satisfies single-node spatial QA; graph adds `>200ms` per query + maintenance |
| Keep static `/health` | Friend cannot diagnose Ollama missing until deep in pipeline |

## Consequences

* Positive: bounded retries auditable, cassette tests run with `pytest` and no Ollama/GPU/docker, dev friend gets `curl /health` + `curl /api/v1/tools` preflight.
* Negative: future multi-hop queries (e.g., multi-orbit pass history across admin boundaries) will need GraphRAG — ADR 0009 will be superseded then.
* Follow-ups: MCP if external clients require it; supersede when measurement shows Chroma miss rate.

## Verification

* `python -m py_compile orchestrator/helpers/guardrails.py orchestrator/graph/pipeline.py orchestrator/agents/error_handler.py orchestrator/api/main.py`
* `pytest tests/e2e/test_replay.py -v` 5 cases offline
* `curl /health` → `{status, ollama_reachable}`, `curl /api/v1/tools` → 10 entries
* `docker compose config` still valid (chroma `8001` already in ADR 0008)
