# ADR 0002 — Express API Gateway and Rate Limiter Implementation

* **Date:** 2026-08-28
* **Status:** Accepted
* **Scope:** gateway
* **Commit/PR:** <fill after merge>
* **Deciders:** Antigravity (AI Agent)

## Context

Satiq requires an API gateway layer to handle client requests (from the frontend), implement JWT authentication, apply API rate limiting to protect downstream LLM orchestration, manage user sessions securely (preventing tenant data leakage), and handle file uploads (specifically GeoTIFF/TIFF/PNG/JPEG files) before forwarding query payloads to the orchestrator.

The gateway needs to be built with Node.js, Express, and TypeScript in the `gateway` directory.

## Decision

We implemented a modular Express server in TypeScript with the following specifics:
- **Core Server (`src/index.ts`):** Standard Express server with Helmet (security), CORS, Morgan (logging), and JSON parser. It runs on port `4000`.
- **Rate Limiting (`src/middleware/rateLimiter.ts`):** Uses `express-rate-limit` to apply general rate limiting (100 reqs/15 min) and strict upload rate limiting (10 uploads/15 min).
- **Authentication (`src/middleware/auth.ts`):** Uses JWT token verification. Decodes token details and injects user profile (`userId`, `username`) into request context.
- **Upload (`src/middleware/upload.ts`):** Uses `multer` configured to allow `.tif`, `.tiff`, `.png`, `.jpg`, and `.jpeg` file extensions, storing files in the `upload/` directory.
- **Sessions (`src/routes/session.ts`):** Implements JSON-file-based session persistence in the `session/` folder, mapping filenames safely as `${userId}_${sessionId}.json` to prevent path traversal and enforce tenant isolation.
- **Proxy (`src/routes/query.ts`):** Routes requests dynamically to the downstream orchestrator. Falls back to a mock execution trace response if the orchestrator is offline/not yet implemented.

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| In-memory session store only | Session state would be lost on server restart, which degrades development usability. File-based persistence offers lightweight durability without requiring a database dependency (e.g. Redis/PostgreSQL). |
| Standard Reverse Proxy | A pure Nginx reverse proxy wouldn't easily handle JWT parsing, dynamic file-based session management, and custom mock fallbacks without complex Lua scripting. |

## Consequences

* Positive:
  - Strong, structured security boundaries (Helmet, CORS, JWT authentication).
  - Explicit rate limits to prevent orchestrator resource exhaustion.
  - Safe, file-system-isolated multi-tenant session storage.
  - Seamless fallback support when downstream services are not yet developed.
* Negative / risks:
  - Session files must be periodically cleaned up in production to prevent disk exhaustion.
* Follow-ups:
  - Link from `docs/DECISIONS.md` and `docs/PROGRESS.md`.

## Verification

We will verify compilation via `npm run build` and Typecheck via `npm run typecheck` once dependencies are installed.
