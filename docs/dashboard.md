# Dashboard Reference

The Radius dashboard is a React single-page application that provides real-time visibility into identity risk, incidents, and Blast Radius Scores across your AWS Organization.

---

## Pages

### Identity Risk Table — `/`

The default landing page. Displays all IAM identities that have a calculated Blast Radius Score, sorted by score descending by default.

Columns:
- Identity ARN — links to the Identity Detail page
- Score — numeric value 0–100; click the column header to toggle ascending/descending sort
- Severity — colour-coded badge (see Severity Colour Coding below)
- Last Updated — date the score was last calculated

A summary strip at the top shows total identity count and a breakdown of open incidents by severity.

Pagination: the table loads 25 rows at a time. A "Load more" button appends the next page without a full reload.

**Filtering by severity or account ID** is done via the URL query string or by using the severity badge as a filter toggle (click a severity badge in the summary strip to filter the table to that level). Account ID filtering is available via the `account_id` query parameter, e.g. `/?account_id=123456789012`.

---

### Identity Detail — `/identities/:arn`

Drill-down view for a single IAM identity. The ARN in the URL is URL-encoded.

Sections:
1. Identity Profile — ARN, type (User / Role / Root), account ID, last activity timestamp, status
2. Blast Radius Score — numeric score, severity badge, contributing factors list, calculation timestamp
3. Recent Events — last 20 CloudTrail events for this identity (event type, timestamp, source IP)

Navigate back to the Identity Risk Table using the "← Back to dashboard" link.

---

### Incident Feed — `/incidents`

Chronological feed of all incidents. Each incident card shows:
- Incident ID (first 8 characters)
- Severity badge
- Status control (dropdown for active statuses, static badge for terminal statuses)
- Identity ARN
- Detection type
- Creation timestamp

Pagination: loads 25 incidents at a time with a "Load more" button.

---

## Incident Status Transitions

Incidents follow a linear state machine. Terminal statuses cannot be changed from the UI.

```
open → investigating → resolved
                    └→ false_positive
```

| From          | Allowed transitions          | Terminal? |
|---------------|------------------------------|-----------|
| open          | investigating                | No        |
| investigating | resolved, false_positive     | No        |
| resolved      | —                            | Yes       |
| false_positive| —                            | Yes       |

To update status: open the Incident Feed, find the incident card, and use the status dropdown. The change is applied immediately via a PATCH request to the API.

---

## Blast Radius Score Display

### Severity Colour Coding

| Severity   | Colour | Score range |
|------------|--------|-------------|
| Critical   | Red    | 80–100      |
| Very High  | Orange | 60–79       |
| High       | Amber  | 40–59       |
| Moderate   | Yellow | 20–39       |
| Low        | Green  | 0–19        |

### Contributing Factors

The Identity Detail page lists each scoring rule that contributed non-zero points in the format:

```
<RuleName>: +<points>
```

Example:
```
AdminPrivileges: +20
LoggingDisruption: +20
IAMModification: +10
CrossAccountTrust: +10
RoleChaining: +5
```

Rules that contributed 0 points are omitted from the list.

---

## Local Development Setup

### Prerequisites

- Node.js 18+
- npm 9+
- A running Radius API (local or deployed)

### Steps

```bash
cd frontend
npm install
```

Create a `.env.local` file in the `frontend/` directory:

```
VITE_API_BASE_URL=https://your-api-gateway-url/dev
```

For local API development, point to `http://localhost:3000` or your SAM local endpoint.

Start the dev server:

```bash
npm run dev
```

The app runs at `http://localhost:5173` by default. Vite proxies are not configured — the `VITE_API_BASE_URL` variable must point to a reachable API endpoint.

---

## Production Build and S3 Deployment

### Build

```bash
cd frontend
VITE_API_BASE_URL=https://your-api-gateway-url/prod npm run build
```

Output is written to `frontend/dist/`.

### Deploy to S3

```bash
aws s3 sync frontend/dist/ s3://<your-cloudfront-bucket>/ \
  --delete \
  --cache-control "max-age=31536000,immutable"

# HTML entry point should not be cached aggressively
aws s3 cp frontend/dist/index.html s3://<your-cloudfront-bucket>/index.html \
  --cache-control "no-cache"
```

### Invalidate CloudFront Cache

After each deployment, invalidate the CloudFront distribution to serve the new build immediately:

```bash
aws cloudfront create-invalidation \
  --distribution-id <DISTRIBUTION_ID> \
  --paths "/*"
```

The distribution ID is available in the Terraform outputs:

```bash
terraform -chdir=infra/envs/dev output cloudfront_distribution_id
```
