# Progress Tracker — Satiq (SatQuery AI)

> Kanban + milestone view. Every task that writes/edits/deletes code must move a row here in the **same commit/PR** that changes code. Stale = incomplete.

**Last updated:** 2026-08-26 · **Branch:** `main` · **Head:** `5703720`

## Milestones

| Milestone | Scope | Status | Owner | ETA | Notes |
|-----------|-------|--------|-------|-----|-------|
| M0 — Scaffold | Repo structure, compose, README, governance docs | **Done** | — | 2026-08-26 | `aa6fef2`, `5703720` |
| M1 — Core Contracts | `raster_asset.py`, `analysis_result.py`, `validator.py` (CRS hard gate) | **Planned** | — | — | Build first; validator needs mismatched-CRS regression test |
| M2 — Fusion (Model 4) | CROMA-based optical+SAR cross-attention, seg head, BigEarthNet S1+S2 | Planned | — | — | Highest priority; closest to primary dataset |
| M3 — Change (Model 3) | Change-VQA/Desc + change map, bi-temporal FM | Planned | — | — | Second mandatory multi-image |
| M4 — Single-Image (M1+M2) | RS-VQA (GeoChat) + Grounding (GroundingDINO+SAM) | Planned | — | — | Leverage existing RS-VLM checkpoints |
| M5 — Orchestrator | `llm_planner`, `capability_registry`, `topo_resolver`, `execution_engine`, `evidence_graph`, `vlm_composer`, supervisor/critic loop | Planned | — | — | Single LLM call for planner + composer |
| M6 — Gateway & Frontend | GeoTIFF upload, session, MapLibre workspace, ExecutionTrace inspector | **Done** | — | 2026-08-28 | ADR 0002; 12 phases complete, mocked SSE + spatial multiturn verified |
| M7 — Adaptation & Eval | BigEarthNet fine-tune (LoRA), VRSBench/RSVQA/CDVQA harness, PDF reports | Planned | — | — | — |

## Task Board

| ID | Title | Phase | Status | Assignee | PR/Commit | Blockers / Next |
|----|-------|-------|--------|----------|-----------|-----------------|
| T-001 | Init monorepo + compose skeleton | M0 | **Done** | — | `aa6fef2` | — |
| T-002 | SatQuery architecture README | M0 | **Done** | — | `5703720` | — |
| T-003 | Agent governance docs (AGENTS, DECISIONS, PROGRESS, ETHICS, ADR) | M0 | **Done** | — | this commit | — |
| T-010 | Pydantic `raster_asset.py` (CRS, resolution, bands, timestamp) | M1 | **Todo** | — | — | Needs CRS enum decision (ADR) |
| T-011 | Pydantic `analysis_result.py` (answer + evidence + confidence + trace) | M1 | Todo | — | — | Depends on T-010 |
| T-012 | Deterministic validator — CRS hard gate + format/modality/pairing checks | M1 | Todo | — | — | Must add `pytest` rejecting EPSG mismatch |
| T-020 | Query normalizer | M5 | Todo | — | — | — |
| T-030 | Model 4: CROMA fusion layer + seg head | M2 | Todo | — | — | Checkpoint availability (fallback: dual encoders) |
| T-031 | Model 3: bi-temporal encoder + change map + CDVQA tuning | M3 | Todo | — | — | — |
| T-032 | Model 1: RS-VQA projection + LoRA | M4 | Todo | — | — | — |
| T-033 | Model 2: GroundingDINO + SAM mask | M4 | Todo | — | — | — |
| T-040 | Orchestrator planner (function-calling) | M5 | Todo | — | — | — |
| T-041 | Capability registry + topo resolver | M5 | Todo | — | — | — |
| T-042 | Execution engine + result cache | M5 | Todo | — | — | — |
| T-043 | Evidence graph + confidence engine | M5 | Todo | — | — | — |
| T-044 | Supervisor/critic loop (max N iter, legality checks) | M5 | Todo | — | — | — |
| T-045 | VLM composer + PDF report | M5 | Todo | — | — | — |
| T-050 | Gateway: upload, session, routes | M6 | Todo | — | — | — |
| T-051 | Frontend workspace + ExecutionTrace inspector | M6 | **Done** | OpenCode | wip | All 12 phases: foundation, design system, shell, map, chat/markdown, execution trace, evidence/inspector, mock engine, multiturn, polish, QA |
| T-052 | Frontend polish + responsive + a11y + chunk split | M6 | Done | OpenCode | wip | Bundle 1.91MB — follow-up code-split |
| T-053 | Mock scenarios (coastal, grounding, fusion, failure) | M6 | Done | OpenCode | wip | mockStream + executionEvents driving same stores as real SSE |
| T-054 | Redesign primary chat as product-specific conversational surface | M6 | Done | OpenCode | wip | seed + semantic messages + inline ActivityStream + context-aware Composer; removed generic ruixen template |
| T-060 | Adaptation configs + train/eval scripts | M7 | Todo | — | — | — |
| T-061 | Evaluation suites (vrsbench, rsvqa, cdvqa) | M7 | Todo | — | — | — |

**Statuses:** `Todo` → `In Progress` → `In Review` → `Done` · Mark `Blocked` if waiting on external (checkpoint, dataset).

## Deferred / Stubs

> Anything marked `STUB:` in code must be listed here with reason.

| Location | Stub | Reason | Created |
|----------|------|--------|---------|
| — | (none yet) | — | — |

## Verification Log

| Date | Task | Command | Outcome | Commit |
|------|------|---------|---------|--------|
| 2026-08-26 | T-001 | `docker compose config` | valid (services stubbed) | `aa6fef2` |
| 2026-08-26 | T-003 | `git status` / `git log --oneline` | clean, `5703720` | this commit |
| 2026-08-28 | T-051 | `npm run build` (frontend) | pass — 2725 modules, built in 3.83s | wip |
| 2026-08-28 | T-051 | `npm run build` re-check after path-fix | pass | wip |
| 2026-08-28 | T-054 | `npm run build` (chat redesign) | pass — 2152 modules, built in ~1s; only pre-existing GeoCanvas chunk-size warning | wip |

*Paste real command output in PRs — "tests pass" without evidence is not accepted (see `AGENTS.md:5`).*

## How to Update

1. Move the row: `Todo` → `In Progress` when you start, → `In Review` when PR open, → `Done` when merged.
2. Fill `PR/Commit` and `Blockers / Next`.
3. If you add a stub, append to **Deferred / Stubs**.
4. Append to **Verification Log** with the actual command + outcome.
5. Keep this file and `docs/DECISIONS.md` in sync — they are the two files CI checks alongside code.

## Risks & Watchlist

* CROMA checkpoint availability → fallback to dual Sentinel encoders + cross-attention (log ADR if switching).
* Sentinel ↔ Cartosat/RISAT domain gap (GSD, bands, radiometry) → Input Handler normalization + CORAL/few-shot; track eval gap qualitatively.
* GroundingDINO bbox → mask refinement with SAM is optional but satisfies visual evidence stronger — defer if compute-constrained, log it.
