# ADR 0001 — Agent Governance Docs

* **Date:** 2026-08-26
* **Status:** Accepted
* **Scope:** docs / repo
* **Commit/PR:** `5703720` + this commit
* **Deciders:** governance agent + maintainer

## Context

Satiq is built by mixed human + LLM agents (Cursor, Copilot, Codex, custom). Without enforced traceability, edits go silent, CRS/band handling changes go unaudited, and hallucinated geospatial results can be presented as real. Need lightweight but enforceable rules that work at hackathon speed.

## Decision

Adopt 6-file governance surface:

* `AGENTS.md` — mandatory 5-step workflow (Plan→Implement→Record→Verify→Review) + Definition of Done + verification + security boundaries. Enforced in CI: every PR touching `orchestrator/`, `capabilities/`, `gateway/`, `frontend/` must also touch `docs/DECISIONS.md` + `docs/PROGRESS.md`.
* `CONTRIBUTING.md` — branch/commit/PR contract for humans and agents, location table, verification commands.
* `docs/DECISIONS.md` — append-only log + ADR index (single source of why).
* `docs/PROGRESS.md` — Kanban + milestones + verification log + deferred stubs (single source of what/next).
* `docs/ETHICS.md` — geospatial integrity, hallucination controls, privacy/tenancy/data lifecycle invariants.
* `docs/adr/README.md` + `0000`/`0001` — ADR process and first records.

Adding a dependency, changing schema/CRS/API/fusion/prompt, or touching tenancy → ADR required.

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| No governance, rely on PR review | LLM agents can bypass intent; audits become forensic, not preventive |
| Heavyweight process (Jira + Confluence) | Too slow for hackathon; markdown in repo is reviewable and diffable |
| Single CONTRIBUTING only | Insufficient — Satiq needs audit trace (AGENTS), ethics invariants (ETHICS), and progress/ADR separation |

## Consequences

* Positive: Every behavioral/data/dep change is traceable; onboarding is one read (`AGENTS.md`); ethics invariants are explicit and reviewable.
* Negative: Extra doc touches per PR — intentional cost for auditability.
* Follow-ups: Wire CI check (PR touches code ⇒ must touch `docs/DECISIONS.md` + `docs/PROGRESS.md`); add PR template referencing `AGENTS.md:8`.

## Verification

* Files present: `AGENTS.md`, `CONTRIBUTING.md`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/ETHICS.md`, `docs/adr/README.md`, `docs/adr/0000-scaffold.md`, `docs/adr/0001-agent-governance.md`
* `git status` clean after commit; history shows `aa6fef2` → `5703720` → governance commit
