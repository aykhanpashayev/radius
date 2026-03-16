# Phase 5 Requirements: Frontend Dashboard

## Overview

Phase 5 builds the Radius security dashboard — a React single-page application hosted on S3 + CloudFront. The dashboard gives security teams visibility into identity risk, active incidents, and event history. All data is fetched from the existing API Gateway endpoints. No backend APIs are modified.

---

## Constraints

- Do NOT modify any backend Lambda functions, API Gateway endpoints, or DynamoDB tables
- Do NOT add new API endpoints — use only the existing ones
- The frontend must be a static build deployable to S3
- No server-side rendering — static React SPA only
- Keep dependencies minimal — no large UI frameworks beyond React itself
- The API base URL must be configurable via environment variable (`VITE_API_BASE_URL`)

---

## Requirement 1: Project Structure

**1.1** The frontend must be a React application using Vite as the build tool.

**1.2** The project must live in `frontend/` with the standard Vite + React layout: `src/`, `public/`, `index.html`, `vite.config.js`, `package.json`.

**1.3** The application must use React Router for client-side routing with three routes:
- `/` — Identity Risk Table (default view)
- `/incidents` — Incident Feed
- `/identities/:arn` — Identity Detail View

**1.4** A shared `api.js` module must centralize all API calls. No component may call `fetch()` directly.

**1.5** The API base URL must be read from `import.meta.env.VITE_API_BASE_URL`. A `.env.example` file must document this variable.

**1.6** The frontend reuses the existing API access model from Phase 2. No new frontend authentication flow is introduced in Phase 5. The API Gateway currently uses no custom authorizer; authentication is deferred to a future phase.

---

## Requirement 2: Identity Risk Table

**2.1** The Identity Risk Table must be the default view at `/`.

**2.2** It must fetch data from `GET /scores` and display a table with columns: `identity_arn`, `score_value`, `severity_level`, `calculation_timestamp`.

**2.3** Each row's `identity_arn` must be a link to `/identities/:arn` (URL-encoded).

**2.4** The `severity_level` column must render a colored badge: Critical=red, High=orange, Very High=deep orange, Moderate=yellow, Low=green.

**2.5** The table must support pagination using the `next_token` returned by the API. A "Load more" button must appear when a `next_token` is present.

**2.6** The table must display a loading state while fetching and an error message if the request fails.

**2.7** The table must be sortable by `score_value` (client-side sort on the currently loaded result set only — not the full backend dataset).

**2.8** A summary strip must appear above the table showing: total identities loaded, count of Critical severity, count of High/Very High severity, and count of open incidents. Counts are derived from data already fetched — no additional API endpoints are required. If a fetch fails, the affected count renders as "—".

**2.9** When the scores list is empty and not loading, the table must display an explicit empty state message.

---

## Requirement 3: Incident Feed

**3.1** The Incident Feed must be accessible at `/incidents`.

**3.2** It must fetch data from `GET /incidents` and display a list of incidents sorted by `creation_timestamp` descending.

**3.3** Each incident card must display: `incident_id` (truncated), `identity_arn`, `detection_type`, `severity`, `status`, `creation_timestamp`.

**3.4** The `severity` field must use the same colored badge system as the Identity Risk Table.

**3.5** The `status` field must render a pill badge: `open`=red, `investigating`=yellow, `resolved`=green, `false_positive`=grey.

**3.6** Each incident card must include a status update control — a dropdown to transition status — using `PATCH /incidents/{id}`. The PATCH call updates `status` only. The `notes` and `assigned_to` fields exist in the Incident schema but editing them is not implemented in Phase 5.

**3.7** Valid status transitions must be enforced in the UI: `open → investigating | false_positive`, `investigating → resolved | false_positive`. Terminal statuses (`resolved`, `false_positive`) must show no dropdown.

**3.10** When the incident list is empty and not loading, the feed must display an explicit empty state message.

**3.8** The feed must support pagination via "Load more".

**3.9** The feed must display a loading state and error message on failure.

---

## Requirement 4: Identity Detail View

**4.1** The Identity Detail View must be accessible at `/identities/:arn`.

**4.2** It must fetch and display data from three endpoints in parallel:
- `GET /identities/{arn}` — identity profile
- `GET /scores/{arn}` — current blast radius score
- `GET /events?identity_arn={arn}&limit=20` — recent events

**4.3** The identity profile section must display: `identity_arn`, `identity_type`, `account_id`, `last_activity_timestamp`, `status`. The `region` field is not displayed — it is not part of the Identity_Profile schema.

**4.4** The blast radius score section must display: `score_value` as a large numeric indicator, `severity_level` badge, `contributing_factors` as a list, `calculation_timestamp`. If the score has not yet been calculated (404), render "Score not yet calculated" in place of the card.

**4.5** The recent events section must display a table with columns: `event_type`, `timestamp`, `source_ip` (rendered as "—" if absent). The table shows the latest 20 events only (`limit=20`). Event pagination is not implemented in Phase 5. A note "Showing latest 20 events" must appear above the table.

**4.8** Each section (profile, score, events) must render an explicit error or empty state message independently — a failure in one section must not prevent the others from rendering.

**4.6** A "Back to dashboard" link must navigate to `/`.

**4.7** If the identity is not found (404), a clear "Identity not found" message must be shown.

---

## Requirement 5: Navigation

**5.1** A persistent top navigation bar must appear on all views with links to: "Dashboard" (`/`) and "Incidents" (`/incidents`).

**5.2** The active route must be visually indicated in the nav bar.

**5.3** The application name "Radius" must appear in the nav bar.

---

## Requirement 6: Styling

**6.1** The dashboard must use a dark theme appropriate for a security tool.

**6.2** Styling must use plain CSS (no CSS-in-JS, no Tailwind, no external component libraries).

**6.3** The layout must be responsive — usable on screens ≥ 1024px wide (desktop-first).

**6.4** Severity badges must use consistent colors across all views (same color map).

---

## Requirement 7: API Client

**7.1** The `api.js` module must export functions: `getScores(params)`, `getIdentity(arn)`, `getScore(arn)`, `getIncidents(params)`, `patchIncident(id, status)`, `getEvents(params)`.

**7.2** All API functions must throw a descriptive error on non-2xx responses.

**7.3** The API client must pass `Content-Type: application/json` on PATCH requests.

---

## Requirement 8: Build and Deployment

**8.1** `npm run build` must produce a static build in `frontend/dist/`.

**8.2** The build output must be deployable to S3 with `aws s3 sync dist/ s3://<bucket>`.

**8.3** A `frontend/.env.example` file must document all required environment variables.

**8.4** The existing `infra/modules/s3/` and `infra/modules/cloudfront/` Terraform modules must not be modified — the frontend build is deployed separately from infrastructure provisioning.

---

## Requirement 9: Documentation

**9.1** A `docs/frontend.md` file must document: local development setup, environment variables, build process, and deployment to S3 + CloudFront.
