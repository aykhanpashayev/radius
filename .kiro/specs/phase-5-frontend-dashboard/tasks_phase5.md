# Implementation Plan: Phase 5 Frontend Dashboard

## Overview

Phase 5 builds the Radius security dashboard — a React SPA hosted on S3 + CloudFront. All work is additive — no backend APIs, Lambda functions, or DynamoDB tables are modified.

**Implementation Language:** JavaScript (React 18, Vite)

**Key Deliverables:**
- Vite + React project scaffold
- Shared API client (`api.js`)
- Identity Risk Table view (`/`)
- Incident Feed view (`/incidents`)
- Identity Detail view (`/identities/:arn`)
- Shared components: NavBar, SeverityBadge, StatusBadge
- Dark theme CSS
- Frontend documentation

**Important Constraints:**
- Do NOT modify any backend code, API endpoints, or infrastructure
- Do NOT use external component libraries (no MUI, Ant Design, Chakra, etc.)
- Do NOT use Tailwind CSS — plain CSS only
- The API base URL must come from `VITE_API_BASE_URL` env var
- All `fetch()` calls must go through `api.js` — never directly in components

**Priority Labels:**
- **must-have**: Required for Phase 5 functionality
- **should-have**: Important but not blocking
- **nice-to-have**: Optional enhancements

---

## Tasks

### Milestone 1: Project Scaffold

- [x] 1. Initialize Vite + React project (must-have)
  - Create `frontend/package.json` with dependencies: `react`, `react-dom`, `react-router-dom`; devDependencies: `vite`, `@vitejs/plugin-react`
  - Create `frontend/vite.config.js` with React plugin
  - Create `frontend/index.html` — root HTML with `<div id="root">` and script entry
  - Create `frontend/src/main.jsx` — React entry point with `BrowserRouter`
  - Create `frontend/src/App.jsx` — route definitions for `/`, `/incidents`, `/identities/:arn`
  - Create `frontend/.env.example` documenting `VITE_API_BASE_URL`
  - **Deliverable:** Working Vite dev server (`npm run dev`) and build (`npm run build`)
  - _Requirements: 1.1, 1.2, 1.3, 1.5_

- [x] 2. Implement global CSS and dark theme (must-have)
  - Create `frontend/src/index.css`
  - Define CSS custom properties: `--bg`, `--surface`, `--border`, `--text`, `--text-muted`, `--accent`
  - Dark theme base: `body { background: var(--bg); color: var(--text); }`
  - Base styles for: `table`, `th`, `td`, `button`, `select`, `a`, `.badge`, `.card`
  - **Deliverable:** Dark theme applied globally
  - _Requirements: 6.1, 6.2, 6.3_

### Milestone 2: Shared Components and API Client

- [ ] 3. Implement API client (must-have)
  - Create `frontend/src/api.js`
  - Read base URL from `import.meta.env.VITE_API_BASE_URL`
  - Implement `request(path, options)` — throws on non-2xx
  - Export: `getScores(params)`, `getIdentity(arn)`, `getScore(arn)`, `getIncidents(params)`, `patchIncident(id, status)`, `getEvents(params)`
  - All list functions accept a `params` object and serialize to query string via `URLSearchParams`
  - `patchIncident` sends `Content-Type: application/json` with `{ status }` body
  - **Deliverable:** `api.js` with all 6 exported functions
  - _Requirements: 7.1, 7.2, 7.3_

- [ ] 4. Implement NavBar component (must-have)
  - Create `frontend/src/components/NavBar.jsx`
  - Render app name "Radius" and nav links to `/` ("Dashboard") and `/incidents` ("Incidents")
  - Use `NavLink` from `react-router-dom` for active-state class
  - Style: dark background, horizontal layout, active link highlighted with `--accent` color
  - **Deliverable:** `NavBar` rendered on all pages
  - _Requirements: 5.1, 5.2, 5.3_

- [ ] 5. Implement SeverityBadge, StatusBadge, and SummaryStrip components (must-have)
  - Create `frontend/src/components/SeverityBadge.jsx`
  - Color map: Critical=`#dc2626`, Very High=`#ea580c`, High=`#f97316`, Moderate=`#ca8a04`, Low=`#16a34a`, unknown=`#6b7280`
  - Create `frontend/src/components/StatusBadge.jsx`
  - Color map: open=`#dc2626`, investigating=`#ca8a04`, resolved=`#16a34a`, false_positive=`#6b7280`
  - Both render a `<span className="badge">` with inline background color
  - Create `frontend/src/components/SummaryStrip.jsx`
  - Accept `scores` and `incidents` props; derive counts client-side (no extra API calls)
  - Show: total identities loaded, Critical count, High/Very High count, open incident count
  - Render "—" for any count whose source data failed to load
  - **Deliverable:** Reusable badge and summary strip components
  - _Requirements: 2.4, 2.8, 3.4, 3.5, 6.4_

### Milestone 3: Identity Risk Table

- [ ] 6. Implement Identity Risk Table page (must-have)
  - Create `frontend/src/pages/IdentityRiskTable.jsx`
  - On mount: `Promise.allSettled([getScores({ limit: 25 }), getIncidents({ status: "open", limit: 100 })])` — parallel fetch for table data and summary strip
  - Render `<SummaryStrip scores={scores} incidents={incidents} />` above the table
  - Render table with columns: Identity ARN (link to `/identities/:arn`), Score, Severity, Last Updated
  - `identity_arn` column: `<Link>` with `encodeURIComponent(arn)`
  - `severity_level` column: `<SeverityBadge>`
  - `calculation_timestamp` column: formatted as locale date string
  - Show loading spinner/text while fetching
  - Show error message if fetch fails
  - Show explicit empty state message when scores list is empty and not loading
  - **Deliverable:** Identity Risk Table with summary strip, scores from API, and empty state
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6, 2.8, 2.9_

- [ ] 7. Add pagination and sort to Identity Risk Table (must-have)
  - Store `nextToken` from API response metadata
  - "Load more" button: calls `getScores({ limit: 25, next_token: nextToken })`, appends to `scores`
  - Hide "Load more" when `nextToken` is null
  - Add sort toggle on Score column header — client-side sort of the **currently loaded** `scores` array by `score_value`
  - Toggle between ascending and descending on click
  - Note: sort applies only to identities currently in memory, not the full backend dataset
  - **Deliverable:** Paginated, sortable Identity Risk Table
  - _Requirements: 2.5, 2.7_

### Milestone 4: Incident Feed

- [ ] 8. Implement Incident Feed page (must-have)
  - Create `frontend/src/pages/IncidentFeed.jsx`
  - On mount: call `getIncidents({ limit: 25 })`, store in `incidents` state
  - Render incident cards with: `incident_id` (first 8 chars + "..."), `identity_arn`, `detection_type`, `severity` (`<SeverityBadge>`), `status` (`<StatusBadge>`), `creation_timestamp`
  - Show loading state and error message
  - "Load more" pagination — append to `incidents`
  - Show explicit empty state message when incident list is empty and not loading
  - **Deliverable:** Incident Feed rendering incidents from API with empty state
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.8, 3.9, 3.10_

- [ ] 9. Add status transition control to Incident Feed (must-have)
  - For each incident card, check `TRANSITIONS[status]` — if non-empty, render a `<select>` dropdown
  - Dropdown options: current status (disabled, selected) + valid next statuses
  - On change: call `patchIncident(incident_id, newStatus)` — updates `status` field only
  - On success: update the incident's status in local `incidents` state (no full re-fetch)
  - On error: show inline error message on the card
  - Terminal statuses (`resolved`, `false_positive`): render status badge only, no dropdown
  - Note: `notes` and `assigned_to` fields exist in the Incident schema but are not editable in Phase 5
  - **Deliverable:** Status transitions working from the Incident Feed
  - _Requirements: 3.6, 3.7_

### Milestone 5: Identity Detail View

- [ ] 10. Implement Identity Detail page (must-have)
  - Create `frontend/src/pages/IdentityDetail.jsx`
  - Read `:arn` from `useParams()`, decode with `decodeURIComponent`
  - On mount: `Promise.allSettled([getIdentity(arn), getScore(arn), getEvents({ identity_arn: arn, limit: 20 })])`
  - Each section handles its own settled/rejected state independently — a failure in one must not block the others
  - Render three sections:
    1. Identity profile card: `identity_arn`, `identity_type`, `account_id`, `last_activity_timestamp`, `status`
       - Do NOT display `region` — it is not a field in the Identity_Profile schema
    2. Blast radius score card: large `score_value`, `<SeverityBadge severity_level>`, `contributing_factors` list, `calculation_timestamp`
       - If score returns 404 or fails: render "Score not yet calculated" in place of the card
    3. Recent events table: `event_type`, `timestamp`, `source_ip` (render "—" if absent)
       - Fetches latest 20 events only (`limit=20`) — no event pagination in Phase 5
       - Render note: "Showing latest 20 events."
       - Empty state: "No recent events found for this identity."
  - "Back to dashboard" link → `/`
  - If identity profile returns 404: render "Identity not found" and the back link only
  - **Deliverable:** Identity Detail page with correct field set, per-section error states, and explicit empty states
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

### Milestone 6: Integration and Polish

- [ ] 11. Wire up App.jsx routes and NavBar (must-have)
  - Update `frontend/src/App.jsx` to include all three routes
  - Render `<NavBar />` outside `<Routes>` so it appears on every page
  - Ensure 404 route shows a simple "Page not found" message
  - **Deliverable:** Full routing working with persistent nav
  - _Requirements: 1.3, 5.1, 5.2_

- [ ] 12. Write frontend documentation (must-have)
  - Create `docs/frontend.md`
  - Document: prerequisites (Node 18+), local dev setup (`npm install`, `npm run dev`), environment variables (`VITE_API_BASE_URL`), production build (`npm run build`), S3 deployment (`aws s3 sync`), CloudFront invalidation, CloudFront custom error response for SPA routing
  - **Deliverable:** `docs/frontend.md`
  - _Requirements: 9.1_

---

## Notes

**Task Organization:**
- Milestone 1: Project Scaffold (2 tasks)
- Milestone 2: Shared Components and API Client (3 tasks)
- Milestone 3: Identity Risk Table (2 tasks)
- Milestone 4: Incident Feed (2 tasks)
- Milestone 5: Identity Detail (1 task)
- Milestone 6: Integration and Documentation (2 tasks)

**Key Architecture Decisions:**
- Vite for fast builds and native ESM dev server
- React Router v6 `BrowserRouter` for client-side routing
- `Promise.allSettled` in IdentityDetail for resilient parallel fetching — per-section error states, not full-page failures
- All API calls centralized in `api.js` — no `fetch()` in components
- Plain CSS with custom properties — no framework dependency
- Status transitions enforced client-side to mirror backend `_VALID_TRANSITIONS`; PATCH updates `status` only in Phase 5
- Client-side sort applies to the currently loaded result set only — not the full backend dataset
- `region` is not displayed in IdentityDetail — it is not a field in the Identity_Profile schema
- Event list fixed at 20 with no pagination in Phase 5 — keeps the view simple; can be extended later
- SummaryStrip derives counts from already-fetched data — no additional API endpoints required
- No new frontend authentication flow in Phase 5 — reuses the existing Phase 2 API access model

**Deferred to Future Phases:**
- Incident `notes` and `assigned_to` editing (schema fields exist, UI not implemented)
- Event pagination on IdentityDetail
- Frontend authentication (Cognito, API keys, etc.)

**API Endpoints Used:**
- `GET /scores` — Identity Risk Table list
- `GET /scores/{arn}` — Identity Detail score section
- `GET /identities/{arn}` — Identity Detail profile section
- `GET /incidents` — Incident Feed list
- `PATCH /incidents/{id}` — Incident status update
- `GET /events?identity_arn={arn}` — Identity Detail events section

**No Backend Changes:**
All existing API Gateway endpoints already return CORS headers (`Access-Control-Allow-Origin: *`). No backend modifications are needed.
