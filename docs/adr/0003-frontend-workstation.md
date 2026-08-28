# ADR 0003 — Frontend Analysis Workstation (Phase 0-12)

* **Date:** 2026-08-28
* **Status:** Accepted
* **Scope:** frontend
* **Commit/PR:** wip
* **Deciders:** OpenCode (Muse Spark)

## Context

Satiq frontend must behave as a professional remote-sensing analysis workstation, not a generic AI chat + map demo. It must make 5 pipelines visible/manipulable: Query/Attachment → Planning → Execution Trace (VQA/Grounding/Change/Fusion) → Evidence → Composed Answer + Spatial State. It must run fully mocked today and point at real Gateway/Orchestrator tomorrow without UI path divergence. Stack choices and architecture boundaries needed locking before building.

## Decision

Build frontend on Vite + React + TypeScript + React Router + Tailwind v4 + shadcn/ui primitives + Lucide + Motion + MapLibre GL + TanStack Query (server state) + Zustand (client/workspace state) + react-markdown/remark-gfm + Recharts + TanStack Table + Zod + Sonner + cmdk + react-dropzone. Separate concerns strictly: TanStack Query for analyses/assets, Zustand for selectedFeature/map/activeLayer/inspector/sidebar/composer draft, local state for hover/popover. Create typed contracts in `src/schemas/*` validated with Zod at SSE/HTTP boundary. Create single transport `src/lib/sse.ts` + `useAgentQuery` hook + `src/mocks/mockStream.ts` scenario engine so mock and real SSE share the same event reducer/store path.

Layout: collapsible app sidebar (full → icon rail → hidden), `WorkspaceHeader` with command palette (Cmd+K), central MapLibre workspace (dominant surface, 55-60% height), floating Chat+ExecutionTrace overlay, right Inspector (collapsible). Routes: `/`, `/workspace`, `/analysis`, `/analysis/:analysisId`, `/explore`, `/data`, `/maps`, `/settings`, `/design-system`. Map supports satellite/street/terrain, imagery tint, change mask, detections (GeoJSON, feature-state selected), layer toggles, fly-to, coordinates. Chat supports markdown with custom renderers, spatial reference chips (click → select → fly → inspector), streaming via chunk buffer. ExecutionTrace shows Planner/Models/Evidence/Composer with pending/running/completed/failed/skipped and expandable details. EvidencePanel tabs: Inspector, Evidence, Compare (ImageComparison/SplitViewer + MetadataPanel + ConfidenceChart/ChangeTimeline).

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| assistant-ui abstraction | Simplifies first demo but constrains Satiq-specific chat (map context, spatial refs, execution state, multi-modal evidence) |
| All state in Zustand | Conflates server vs client state; TanStack Query gives caching/sync for analyses/assets correctly |
| React Flow for EvidenceGraph | Overkill for initial clean DOM/SVG graph; adopt only when graph becomes highly interactive |
| Giant monolithic UI library controlling design | shadcn Vite model is additive primitives; keeps product-specific components controllable |

## Consequences

* Positive: auditable trace + spatial interactivity end-to-end; mock/real parity via same hooks/stores; professional dark workstation aesthetic (restrained cyan accents, surface hierarchy, 4-8-12-16 radii).
* Negative / risks: bundle ~1.9MB (chunk splitting follow-up); MapLibre style URL external (needs offline fallback); motion import quirk handled by removing motion from ExecutionTrace (follow-up: standardize on `motion` vs `framer-motion`).
* Follow-ups: code-split routes, generate TS types from gateway OpenAPI, add CRS-mismatch upload error UX tied to validator, add a11y/axe audit.

## Verification

`npm run build` passes (2725 modules, gzip ~534kB JS + 18kB CSS). No `any` leak beyond controlled GeoJSON. Manual run via Vite dev server; routes, map interactions, mock scenarios (coastal-change, grounding, fusion, multiturn) drive same stores as real SSE.
