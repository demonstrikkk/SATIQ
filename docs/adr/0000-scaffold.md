# ADR 0000 — Initialize Monorepo Scaffold

* **Date:** 2026-08-26
* **Status:** Accepted
* **Scope:** repo
* **Commit/PR:** `aa6fef2`
* **Deciders:** init agent

## Context

Satiq (SatQuery AI) needs a monorepo covering frontend (React+MapLibre), gateway (Node/Express+TS), orchestrator (Python), isolated capabilities (single_image/temporal/fusion/geospatial), adaptation (BigEarthNet) and evaluation (VRSBench/RSVQA/CDVQA). Build-priority requires Pydantic models + CRS hard gate before any model code. Need empty but trackable structure.

## Decision

Create skeleton directories per `README.md` structure (23 dirs) with `.gitkeep` so git tracks empties. Add `docker-compose.yml` skeleton (services commented), `.gitignore` (node/python/OS/secrets), and architecture `README.md`. No implementation — `git init` on `main`.

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| Monorepo tool (Nx/Turborepo) | Overkill for hackathon scaffold; adds dep before code exists |
| Separate repos per service | Breaks orchestrator↔capabilities shared `orchestrator/models` contract |

## Consequences

* Positive: `docker compose config` passes; clear build order; agents know where to place code.
* Negative: Empty dirs require hygiene (remove `.gitkeep` when real file lands, or keep — either is fine).
* Follow-ups: M1 Pydantic + validator (see `docs/PROGRESS.md` T-010..T-012).

## Verification

* `docker compose config` — valid
* `git log --oneline` — `aa6fef2 chore: initialize monorepo scaffold`
* `git status` — clean
