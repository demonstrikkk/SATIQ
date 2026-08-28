# Decisions Log — Satiq (SatQuery AI)

> Single source of truth for **why** the system is the way it is. Every behavioral, data-handling, or dependency change must append here. Architecture-worthy decisions get a full ADR in `docs/adr/NNNN-*.md` — this file indexes them.

## How to Use

* **Append-only.** Never rewrite history; strikethrough + supersede if needed.
* **One line per change**, plus link to ADR if present. Every entry references a commit/PR.
* **No silent edits** — if `orchestrator/`, `capabilities/`, `gateway/`, or `frontend/` changed and this file didn't, the PR is incomplete (enforced in CI — see `AGENTS.md:8`).
* Format: `| Date | ADR | Title | Scope | Commit/PR | Status |`

## Index

| Date | ADR | Title | Scope | Commit/PR | Status |
|------|-----|-------|-------|-----------|--------|
| 2026-08-26 | [ADR 0000](adr/0000-scaffold.md) | Initialize monorepo scaffold (no code) | repo | `aa6fef2` | Accepted |
| 2026-08-26 | [ADR 0001](adr/0001-agent-governance.md) | Adopt agent governance docs (AGENTS, DECISIONS, PROGRESS, ETHICS) | docs | `5703720` | Accepted |
| 2026-08-26 | — | Add SatQuery architecture README (4 models, orchestrator, input gate) | docs | `5703720` | Logged |
| 2026-08-28 | [ADR 0002](adr/0002-api-gateway.md) | Implement API gateway and rate limiter | gateway | `<fill>` | Accepted |

<!-- New entries append below. Keep newest at bottom for git-friendly diffs. -->

## Decision Records

### 2026-08-26 — Scaffold

* **What:** Created monorepo directories per `README.md` structure (frontend/gateway/orchestrator/capabilities/adaptation/evaluation) + `docker-compose.yml` skeleton, `.gitignore`, `README.md`. No implementation — `.gitkeep` placeholders only.
* **Why:** Establish build-priority order (Pydantic models → CRS gate → Model 4 → Model 3 → ...) before any code.
* **Consequences:** `docker compose config` passes; services are no-ops until uncommented.

### 2026-08-26 — Agent Governance

* **What:** Added `AGENTS.md`, `CONTRIBUTING.md`, `docs/ETHICS.md`, `docs/DECISIONS.md` (this file), `docs/PROGRESS.md`, `docs/adr/README.md` + ADR template. Established 5-step workflow (Plan→Implement→Record→Verify→Review) and Definition of Done.
* **Why:** Satiq is built by mixed human+LLM agents; auditability (execution_trace) applies to development too — every edit must be traceable. Prevents hallucinated geospatial results, silent CRS changes, and untracked dependency bloat.
* **Consequences:** All future PRs touching product code must also touch `docs/DECISIONS.md` + `docs/PROGRESS.md`; ADRs required for behavior/data/dep changes.

### 2026-08-28 — API Gateway and Rate Limiter

* **What:** Implemented the Express + TypeScript API Gateway and Rate Limiter, adding `package.json`, `tsconfig.json`, `src/index.ts`, custom middlewares (auth, upload, rateLimiter), and routes (auth, upload, session, query).
* **Why:** Fulfills Milestone M6 gateway requirement: provides security boundaries, rate limiting, and structured session persistence with tenant isolation.
* **Consequences:** Client requests are authenticated via JWT, session store is safe against path traversal, and down-stream orchestration queries are proxied.

---

## Adding a New Decision

1. Append a row to the Index table.
2. If ADR-worthy (architecture, model/library selection, schema/CRS/band handling, API contract, dependency, prompt/fusion strategy), create `docs/adr/NNNN-title.md` from `docs/adr/README.md` template and link it.
3. If docs-only/ trivial, just add the row + a short paragraph in this file under a new `### YYYY-MM-DD — Title` heading.
4. Reference the commit hash after committing.
5. Update `docs/PROGRESS.md` in the same PR.

**Ask:** Does this change alter behavior, data handling, storage, external API, or dependencies? → ADR. Otherwise → line item here is enough.
