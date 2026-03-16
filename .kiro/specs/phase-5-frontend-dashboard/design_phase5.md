# Phase 5 Design: Frontend Dashboard

## Overview

Phase 5 builds a React SPA hosted on S3 + CloudFront. The frontend communicates exclusively with the existing API Gateway endpoints — no new backend work. The design is intentionally minimal: plain CSS, no component library, three views, one shared API client.

---

## Architecture

```
Browser
    │
    ▼
CloudFront (CDN)
    │
    ▼
S3 (static assets: index.html, JS, CSS)
    │  (React Router handles client-side routing)
    │
    ▼
API Gateway
    ├── GET  /scores
    ├── GET  /scores/{arn}
    ├── GET  /identities/{arn}
    ├── GET  /incidents
    ├── PATCH /incidents/{id}
    └── GET  /events?identity_arn={arn}
```

---

## API Access Model

The Phase 2 API Gateway deployment uses no custom authorizer — all methods are configured with `authorization = "NONE"` and the API is protected at the network/deployment level (REGIONAL endpoint, stage-scoped). The frontend reuses this existing access model directly. No new frontend authentication flow is introduced in Phase 5; authentication (e.g. Cognito, API keys) is deferred to a future phase.

---

## File Structure

```
frontend/
├── index.html
├── vite.config.js
├── package.json
├── .env.example
└── src/
    ├── main.jsx              ← React entry point, Router setup
    ├── App.jsx               ← Route definitions
    ├── api.js                ← All API calls (single module)
    ├── index.css             ← Global styles, CSS variables, dark theme
    ├── components/
    │   ├── NavBar.jsx        ← Persistent top nav
    │   ├── SeverityBadge.jsx ← Reusable colored badge
    │   ├── StatusBadge.jsx   ← Incident status pill
    │   └── SummaryStrip.jsx  ← Dashboard summary counts
    └── pages/
        ├── IdentityRiskTable.jsx   ← / (default)
        ├── IncidentFeed.jsx        ← /incidents
        └── IdentityDetail.jsx      ← /identities/:arn
```

---

## Component Design

### api.js

Single module — all `fetch()` calls live here. Components never call `fetch()` directly.

```js
const BASE = import.meta.env.VITE_API_BASE_URL;

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export const getScores = (params = {}) =>
  request(`/scores?${new URLSearchParams(params)}`);

export const getIdentity = (arn) =>
  request(`/identities/${encodeURIComponent(arn)}`);

export const getScore = (arn) =>
  request(`/scores/${encodeURIComponent(arn)}`);

export const getIncidents = (params = {}) =>
  request(`/incidents?${new URLSearchParams(params)}`);

export const patchIncident = (id, status) =>
  request(`/incidents/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });

export const getEvents = (params = {}) =>
  request(`/events?${new URLSearchParams(params)}`);
```

---

### NavBar.jsx

Persistent top bar on all views. Uses `NavLink` from React Router for active-state styling.

```jsx
<nav className="navbar">
  <span className="navbar-brand">Radius</span>
  <NavLink to="/">Dashboard</NavLink>
  <NavLink to="/incidents">Incidents</NavLink>
</nav>
```

---

### SummaryStrip.jsx

A lightweight summary strip rendered at the top of the Identity Risk Table (`/`). Derives counts from the already-fetched `scores` array — no additional API calls.

```jsx
// Counts derived client-side from the loaded scores result set
function SummaryStrip({ scores, incidents }) {
  const critical = scores.filter(s => s.severity_level === "Critical").length;
  const high     = scores.filter(s => s.severity_level === "High" ||
                                      s.severity_level === "Very High").length;
  const openInc  = incidents.filter(i => i.status === "open").length;

  return (
    <div className="summary-strip">
      <div className="summary-card">
        <span className="summary-value">{scores.length}</span>
        <span className="summary-label">Identities tracked</span>
      </div>
      <div className="summary-card critical">
        <span className="summary-value">{critical}</span>
        <span className="summary-label">Critical severity</span>
      </div>
      <div className="summary-card high">
        <span className="summary-value">{high}</span>
        <span className="summary-label">High / Very High</span>
      </div>
      <div className="summary-card">
        <span className="summary-value">{openInc}</span>
        <span className="summary-label">Open incidents</span>
      </div>
    </div>
  );
}
```

The `incidents` prop is fetched alongside scores on the dashboard mount (`getIncidents({ status: "open", limit: 100 })`). Both fetches are parallel via `Promise.allSettled`. The strip degrades gracefully — if either fetch fails, the affected count shows "—".

---

### SeverityBadge.jsx

Reusable badge used in both IdentityRiskTable and IncidentFeed.

```jsx
const SEVERITY_COLORS = {
  Critical:   "#dc2626",   // red
  "Very High":"#ea580c",   // deep orange
  High:       "#f97316",   // orange
  Moderate:   "#ca8a04",   // yellow
  Low:        "#16a34a",   // green
};

export function SeverityBadge({ severity }) {
  return (
    <span className="badge" style={{ background: SEVERITY_COLORS[severity] ?? "#6b7280" }}>
      {severity}
    </span>
  );
}
```

---

### StatusBadge.jsx

Incident status pill.

```jsx
const STATUS_COLORS = {
  open:          "#dc2626",
  investigating: "#ca8a04",
  resolved:      "#16a34a",
  false_positive:"#6b7280",
};
```

---

### IdentityRiskTable.jsx (`/`)

State: `scores`, `incidents`, `nextToken`, `loading`, `error`, `sortDir`

Data flow:
1. On mount: `Promise.allSettled([getScores({ limit: 25 }), getIncidents({ status: "open", limit: 100 })])` — parallel fetch for table data and summary strip counts
2. "Load more": `getScores({ limit: 25, next_token: nextToken })` → append to `scores`
3. Sort toggle: client-side sort of the **currently loaded** `scores` array by `score_value`

> Note: client-side sort applies only to the result set currently in memory. It does not re-sort the full backend dataset. Identities loaded via "Load more" are appended and sorted together with the existing set.

```jsx
function IdentityRiskTable() {
  const [scores, setScores] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [nextToken, setNextToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortDir, setSortDir] = useState("desc");

  const load = async (token = null) => { ... };

  const sorted = [...scores].sort((a, b) =>
    sortDir === "desc" ? b.score_value - a.score_value : a.score_value - b.score_value
  );

  return (
    <div>
      <SummaryStrip scores={scores} incidents={incidents} />
      {sorted.length === 0 && !loading && (
        <p className="empty-state">No identity scores found. Scores are calculated after CloudTrail events are processed.</p>
      )}
      <table>
        <thead>
          <tr>
            <th>Identity ARN</th>
            <th onClick={toggleSort}>Score ▲▼</th>
            <th>Severity</th>
            <th>Last Updated</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(s => (
            <tr key={s.identity_arn}>
              <td><Link to={`/identities/${encodeURIComponent(s.identity_arn)}`}>{s.identity_arn}</Link></td>
              <td>{s.score_value}</td>
              <td><SeverityBadge severity={s.severity_level} /></td>
              <td>{formatDate(s.calculation_timestamp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {nextToken && <button onClick={() => load(nextToken)}>Load more</button>}
    </div>
  );
}
```

---

### IncidentFeed.jsx (`/incidents`)

State: `incidents`, `nextToken`, `loading`, `error`

Data flow:
1. On mount: `getIncidents({ limit: 25 })` → populate `incidents`
2. "Load more": append
3. Status patch: `patchIncident(incident_id, newStatus)` → update item in local `incidents` state (no full re-fetch)

The PATCH call updates `status` only. The `notes` and `assigned_to` fields exist in the Incident schema but editing them is not implemented in Phase 5 — the UI exposes status transitions only.

Status transition map (enforced in UI, mirrors backend `_VALID_TRANSITIONS`):
```js
const TRANSITIONS = {
  open:          ["investigating", "false_positive"],
  investigating: ["resolved", "false_positive"],
  resolved:      [],
  false_positive:[],
};
```

Each incident card renders a `<select>` dropdown only when `TRANSITIONS[status].length > 0`. Terminal statuses render a status badge only.

Empty state: when `incidents.length === 0` and not loading, render:
```jsx
<p className="empty-state">No incidents found. Incidents are created when detection rules trigger.</p>
```

---

### IdentityDetail.jsx (`/identities/:arn`)

State: `profile`, `score`, `events`, `loading`, `error`

Data flow — parallel fetch on mount:
```js
const arn = useParams().arn;
const decoded = decodeURIComponent(arn);

const [profileRes, scoreRes, eventsRes] = await Promise.allSettled([
  getIdentity(decoded),
  getScore(decoded),
  getEvents({ identity_arn: decoded, limit: 20 }),
]);
```

Uses `Promise.allSettled` so a missing score doesn't block the profile from rendering. Each section handles its own settled/rejected state independently.

Sections:
1. **Identity profile card** — `identity_arn`, `identity_type`, `account_id`, `last_activity_timestamp`, `status`
   - `region` is not displayed — it is not a field in the Identity_Profile schema
2. **Blast radius score card** — large `score_value` number, `SeverityBadge`, `contributing_factors` list, `calculation_timestamp`
   - If score fetch returns 404 or fails: render "Score not yet calculated" in place of the card
3. **Recent events table** — shows the most recent 20 events (`limit=20`). No pagination is implemented for events in Phase 5. A note reads: "Showing latest 20 events."
   - Columns: `event_type`, `timestamp`, `source_ip` (rendered as "—" if absent)
   - Empty state: "No recent events found for this identity."

"Back to dashboard" link → `/`

If identity profile returns 404: render "Identity not found" and the back link only.

---

## Routing

```jsx
// App.jsx
<Routes>
  <Route path="/" element={<IdentityRiskTable />} />
  <Route path="/incidents" element={<IncidentFeed />} />
  <Route path="/identities/:arn" element={<IdentityDetail />} />
  <Route path="*" element={<p>Page not found.</p>} />
</Routes>
```

React Router `BrowserRouter` is used. CloudFront must be configured with a custom error response: 404 → `index.html` (status 200) to support client-side routing on direct URL access.

---

## Styling

Dark theme via CSS custom properties in `index.css`:

```css
:root {
  --bg:        #0f172a;   /* slate-900 */
  --surface:   #1e293b;   /* slate-800 */
  --border:    #334155;   /* slate-700 */
  --text:      #f1f5f9;   /* slate-100 */
  --text-muted:#94a3b8;   /* slate-400 */
  --accent:    #3b82f6;   /* blue-500  */
}

.empty-state {
  color: var(--text-muted);
  text-align: center;
  padding: 2rem;
}

.summary-strip {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.summary-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 1rem 1.5rem;
  min-width: 140px;
}
```

No external CSS framework. All styles in `index.css` and co-located `.css` files.

---

## Build and Deployment

```
npm install
npm run build        # outputs to frontend/dist/
aws s3 sync dist/ s3://<bucket-name> --delete
```

CloudFront invalidation after deploy:
```
aws cloudfront create-invalidation --distribution-id <id> --paths "/*"
```

Environment variables:
```
VITE_API_BASE_URL=https://<api-id>.execute-api.<region>.amazonaws.com/<stage>
```

---

## Key Design Decisions

- **Vite + React** — fast dev server, minimal config, standard static build output
- **No component library** — keeps bundle small, avoids dependency churn; plain CSS is sufficient for a security tool dashboard
- **Single `api.js` module** — all fetch logic in one place; easy to swap base URL or add auth headers later
- **`Promise.allSettled` in IdentityDetail** — partial data is better than a full-page error when one of three endpoints fails
- **Client-side sort on loaded set only** — sorting applies to the identities currently in memory. It does not re-query the backend. This is a known limitation: the full dataset is only sorted if all pages are loaded.
- **Status transitions enforced in UI** — mirrors the backend's `_VALID_TRANSITIONS` map; prevents invalid PATCH requests before they're sent
- **PATCH updates status only** — `notes` and `assigned_to` fields exist in the Incident schema but are not editable in Phase 5. This is intentional scope control, not an oversight.
- **No `region` in IdentityDetail** — `region` is not a field in the Identity_Profile DynamoDB schema. Only schema-confirmed fields are displayed.
- **Event list is fixed at 20, no pagination** — IdentityDetail fetches the latest 20 events and does not implement event pagination. This keeps the view simple; pagination can be added in a future phase.
- **SummaryStrip uses no new endpoints** — counts are derived from data already fetched for the dashboard. The open-incident count reuses `GET /incidents?status=open&limit=100`.
- **Dark theme** — appropriate for a security operations tool; CSS variables make it easy to theme
- **No new frontend authentication flow in Phase 5** — the frontend reuses the existing API access model from Phase 2. The API Gateway currently uses no custom authorizer. Authentication is deferred to a future phase.

---

## Correctness Properties

1. **No direct fetch calls** — all API calls go through `api.js`
2. **Loading states** — every data-fetching component shows a loading indicator before data arrives
3. **Error state rendering** — every data-fetching component renders an explicit error message on failure; no component renders a blank screen on error
4. **ARN encoding** — identity ARNs are always `encodeURIComponent`-encoded in URLs and decoded with `decodeURIComponent` before API calls
5. **Status transition safety** — the UI never offers an invalid status transition; terminal statuses show no dropdown
6. **Pagination correctness** — "Load more" appends to existing data, never replaces it
7. **Empty state coverage** — every list view renders an explicit empty state message when the result set is empty
