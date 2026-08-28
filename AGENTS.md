# AGENTS.md — Rules for Human & AI Agents Working on Satiq

> **Satiq is SatQuery AI:** a multi-agent geospatial QA system. Every agent that touches this repo — human, Cursor, Copilot, Codex, custom LLM — must follow these rules. They are non-negotiable and auditable via `docs/DECISIONS.md` and `docs/PROGRESS.md`.

## 1. Read Before You Write

1. Read `README.md` (architecture + build priority) and `docs/ETHICS.md` before any code.
2. Inspect the repo: run `git status`, check `docker-compose.yml`, check existing `orchestrator/models/*.py` before creating new models.
3. Search before you create — reuse existing `capability_registry`, `validator`, `execution_engine` helpers. Do not duplicate a capability.

## 2. Manner & Ethics of Modification

### Every change must be traceable
* **No silent edits.** Every write/update/modify/delete must be recorded in `docs/DECISIONS.md` (ADR) and reflected in `docs/PROGRESS.md`.
* Commit messages are imperative and scoped: `feat(orchestrator): add topo resolver`, `fix(gateway): reject CRS mismatch before LLM`, `docs: log ADR 0004`.
* No force-push to `main`. Work on branches, open PRs.

### Smallest responsible change
* Prefer framework-native / built-ins over new dependencies. Adding a dependency requires an ADR — justify what trivial code it actually saves.
* Keep changes focused: one concern per commit/PR. No unrelated formatting, renames, or upgrades.

### Truthfulness over speed
* Never claim a test/build passed unless you ran it and saw output.
* Never hallucinate geospatial results — confidence scores, bboxes, change maps must come from model outputs or deterministic tools, not mocked plausible text.
* CRS/resolution/band handling is safety-critical. Treat a wrong CRS as a hard failure, not a warning.

### No placeholders presented as finished
* Stubs/mocks/demo data must be explicitly marked `// TODO(STUB)` or `STUB:` and listed in `docs/PROGRESS.md` under "Deferred".
* Do not hide TODOs. If you cannot build a full path, state what is deferred and why.

## 3. Mandatory Workflow (5 steps, every task)

```
1. PLAN   → read acceptance criteria, note assumptions
2. IMPLEMENT → smallest code that satisfies requirements
3. RECORD → update docs/DECISIONS.md (why) + docs/PROGRESS.md (what)
4. VERIFY → run targeted checks (see §5), observe output
5. REVIEW → self-check against docs/ETHICS.md invariants
```

Skip step 3 = incomplete task, even if code works.

## 4. What to Record — and Where

| Event | Where to record | Template |
|-------|-----------------|----------|
| Architecture choice, library/model selection, schema change, API contract change | `docs/DECISIONS.md` + new file `docs/adr/NNNN-title.md` | ADR template in `docs/adr/README.md` |
| Schema/CRS/band handling decision, prompt strategy, fusion method | Same — ADR required | Same |
| Any `write`/`edit`/`delete` affecting `orchestrator/`, `capabilities/`, `gateway/`, `frontend/` | `docs/DECISIONS.md` line item + commit body | — |
| Progress, blockers, next steps | `docs/PROGRESS.md` | Kanban + milestone table |
| Ethical/safety-relevant change (privacy, tenant isolation, credential handling) | `docs/ETHICS.md` + ADR | — |

**Rule:** If it changes behavior, data handling, or dependencies, it needs an ADR. If it only changes docs/comments, a `docs/DECISIONS.md` line entry suffices.

## 5. Verification Requirements

Run proportionally — do not skip:

* **Python (orchestrator/capabilities):** `ruff check` / `mypy` / `pytest` (targeted, not full suite if slow). For Pydantic models, run `pytest orchestrator/models -v`.
* **Gateway (Node):** `npm run lint && npm run typecheck && npm test` if present.
* **Frontend:** `npm run build` must pass; check MapLibre + ExecutionTrace renders.
* **Docker:** `docker compose config` validates compose; `docker compose up --build` for integration.
* **CRS gate:** any change to `orchestrator/ingestion/validator.py` must include a regression test with mismatched CRS input that is **rejected**.

Paste the actual command output in the PR description. “Tests pass” without evidence is not accepted.

## 6. Security & Data Boundaries

* Never commit secrets (`.env`, API keys, HF tokens). Use `.env.example`.
* Do not log raw GeoTIFF bytes or full prompts with PII. Evidence logs store metadata + execution_trace, not raw imagery unless explicitly required.
* Tenant isolation: session data in `gateway/session/` must not leak across users. Changing auth/tenancy → pause and get human approval (see `docs/ETHICS.md`).
* Treat model output as untrusted input — validate schema before composing final answer.

## 7. Communication Style

* Be concise, factual, no superlatives. Reference files as `path:line` (e.g., `orchestrator/models/raster_asset.py:12`).
* Report at task end: objective completed, files changed/created, design decisions + assumptions, commands executed + outcomes, unresolved risks, whether fix is root-cause complete or intentionally limited.

## 8. Definition of Done

A task is done only when:
- [ ] Code implements the requirement + handles edge cases (CRS mismatch, single-image vs. pair, empty query)
- [ ] `docs/DECISIONS.md` updated (and ADR file if needed)
- [ ] `docs/PROGRESS.md` updated (phase / task row moved)
- [ ] Targeted verification ran with observed output
- [ ] No secrets or unrelated diffs in the commit

---

*This file is enforced in CI via a simple check: every PR touching `orchestrator/`, `capabilities/`, `gateway/`, `frontend/` must also touch `docs/DECISIONS.md` and `docs/PROGRESS.md`. Bypass requires explicit maintainer approval + ADR explaining why.*
