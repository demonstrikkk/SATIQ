# Contributing to Satiq

This is the single workflow for humans and AI agents. If you use an LLM to contribute (Cursor, Copilot, Codex, etc.), you must still follow it — the LLM is not exempt.

## Quick Contract

1. **Branch** from `main`: `feat/<scope>-<slug>` or `fix/<scope>-<slug>`
2. **Implement** smallest production-quality path — no mocked geospatial results, no hidden TODOs
3. **Record** every behavioral/data/dependency change in `docs/DECISIONS.md` (+ `docs/adr/NNNN-*.md` if ADR-worthy)
4. **Update** `docs/PROGRESS.md` (move task, note blockers)
5. **Verify** with targeted checks, paste output in PR
6. **Open PR** — must touch `docs/DECISIONS.md` + `docs/PROGRESS.md` if you touched `orchestrator/`, `capabilities/`, `gateway/`, `frontend/`

## Setup

```bash
git clone <repo>
docker compose config        # validate compose (scaffold ok)
# per-service as implemented:
# gateway:   npm ci && npm run typecheck
# orchestrator: uv sync / pip install -e . && pytest
```

Copy env: `cp .env.example .env` — never commit `.env`.

## Where to Put Code

| Concern | Location | Notes |
|---------|----------|-------|
| Pydantic schemas | `orchestrator/models/raster_asset.py`, `analysis_result.py` | Build first; frozen, validated |
| CRS/resolution gate | `orchestrator/ingestion/validator.py` | Deterministic, hard-reject on mismatch |
| Query understanding | `orchestrator/understanding/query_normalizer.py` | Deterministic + light LLM |
| Tool routing | `orchestrator/planner/llm_planner.py`, `registry/capability_registry.py`, `registry/topo_resolver.py` | Single LLM call for planning |
| Execution & caching | `orchestrator/engine/` | Sequential tool chaining, result_cache |
| Evidence & confidence | `orchestrator/evidence/` | evidence_graph + confidence calibration |
| Final answer | `orchestrator/composer/vlm_composer.py` | Single VLM call, must include execution_trace |
| Capabilities | `capabilities/single_image|temporal|fusion|geospatial/` | Isolated, no cross-imports except `orchestrator/models` |
| Fine-tuning | `adaptation/train.py`, `eval.py`, `configs/` | BigEarthNet configs, LoRA settings |
| Benchmarks | `evaluation/suites/*.py` | VRSBench, RSVQA, CDVQA adapters |

Do not create top-level folders without an ADR.

## Commit & PR Rules

* Commits: `type(scope): imperative summary` — types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`. Scope = folder (`orchestrator`, `gateway`, `frontend`, `capabilities`).
* One concern per PR. No drive-by formatting.
* PR template must include: objective, files changed, decisions + assumptions, verification commands + outputs (copy-paste), risks, and whether root-cause complete or intentionally limited.
* Adding a dependency → ADR required. State alternatives considered and what trivial code the dep actually saves.

## Verification (paste output)

```bash
# Python
ruff check orchestrator/ && mypy orchestrator/ && pytest orchestrator/models -v

# Gateway (if present)
npm --prefix gateway run lint && npm --prefix gateway run typecheck && npm --prefix gateway test

# Frontend
npm --prefix frontend run build

# Docker
docker compose config
```

Any change to `validator.py` must include a failing test with mismatched CRS (e.g., EPSG:4326 vs EPSG:3857) that is **rejected** — attach proof.

## Documentation You Must Maintain

| File | When to update |
|------|----------------|
| `docs/DECISIONS.md` | Every write/edit/delete that changes behavior, data handling, or deps |
| `docs/adr/NNNN-*.md` | Architecture / model / schema / API / CRS decisions |
| `docs/PROGRESS.md` | Every task — move rows, note blockers, list deferred stubs |
| `docs/ETHICS.md` | Any privacy, tenant isolation, credential, or hallucination-risk change |
| `README.md` | When structure, tech stack, or build priority changes |

If you touched `orchestrator/`, `capabilities/`, `gateway/`, or `frontend/` and did **not** update `docs/DECISIONS.md` + `docs/PROGRESS.md`, CI fails.

## Stubs & Deferred Work

If you cannot finish a full path:

```python
# STUB: grounding returns mock bbox until GroundingDINO checkpoint wired
# Deferred in docs/PROGRESS.md — Phase 3 — blocked on checkpoint download
```

Do not present stubs as finished.

## Getting Help

* Architecture questions → `README.md` + `docs/adr/README.md`
* Governance/ethics → `docs/ETHICS.md` + `AGENTS.md`
* Progress/blockers → `docs/PROGRESS.md`

Maintainers enforce these rules in review. Repeated silent edits or undocumented behavior changes will be reverted.
