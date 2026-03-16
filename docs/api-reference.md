# API Reference

Base URL: `https://{api-id}.execute-api.{region}.amazonaws.com/{env}`

All responses use the envelope format:
```json
{
  "data": [...],
  "metadata": { "count": 25, "next_token": "...", "query_time_ms": 12.4 }
}
```
Single-item responses return the item directly (no envelope).

Pagination: pass `next_token` from the previous response as a query parameter to fetch the next page. Default page size is 25, maximum is 100.

---

## Identities

### GET /identities

List identity profiles.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| identity_type | string | Filter by IAMUser, AssumedRole, or AWSService |
| account_id | string | Filter by 12-digit AWS account ID |
| limit | integer | Page size (1–100, default 25) |
| next_token | string | Pagination cursor from previous response |

**Response:** 200 with identity profile array.

---

### GET /identities/{arn}

Retrieve a single identity profile. URL-encode the ARN.

**Response:** 200 with identity profile object, or 404 if not found.

---

## Scores

### GET /scores

List blast radius scores.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| severity_level | string | Filter by Low / Moderate / High / Very High / Critical |
| min_score | number | Minimum score value (0–100) |
| max_score | number | Maximum score value (0–100) |
| limit | integer | Page size (1–100, default 25) |
| next_token | string | Pagination cursor |

**Note:** `severity_level` and `min_score`/`max_score` cannot be combined in a single query.

**Response:** 200 with score array.

---

### GET /scores/{arn}

Retrieve the blast radius score for a specific identity. URL-encode the ARN.

**Response:** 200 with score object, or 404 if not found.

---

## Incidents

### GET /incidents

List incidents.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| status | string | Filter by open / investigating / resolved / false_positive |
| severity | string | Filter by severity level |
| identity_arn | string | Filter by identity ARN |
| start_date | string | ISO 8601 start of creation_timestamp range |
| end_date | string | ISO 8601 end of creation_timestamp range |
| limit | integer | Page size (1–100, default 25) |
| next_token | string | Pagination cursor |

**Unsupported combinations:** `identity_arn` + `status` together returns 400. Use one filter at a time.

**Response:** 200 with incident array.

---

### GET /incidents/{id}

Retrieve a single incident by ID.

**Response:** 200 with incident object, or 404 if not found.

---

### PATCH /incidents/{id}

Update incident status.

**Request body:**
```json
{ "status": "investigating" }
```

**Valid transitions:**
- open → investigating
- open → false_positive
- investigating → resolved
- investigating → false_positive

**Response:** 200 with updated incident object, 400 for invalid transition, 404 if not found.

---

## Events

### GET /events

List event summaries.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| identity_arn | string | Filter by identity ARN (queries primary table) |
| event_type | string | Filter by event type (queries EventTypeIndex) |
| start_date | string | ISO 8601 start date (queries TimeRangeIndex) |
| end_date | string | ISO 8601 end date |
| limit | integer | Page size (1–100, default 25) |
| next_token | string | Pagination cursor |

**Unsupported combinations:** `identity_arn` + `event_type` together returns 400.

**Response:** 200 with event summary array.

---

### GET /events/{id}

Retrieve a single event summary by CloudTrail event ID.

**Response:** 200 with event summary object, or 404 if not found.

---

## Trust Relationships

### GET /trust-relationships

List trust relationships.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| source_arn | string | Filter by source identity ARN |
| target_account_id | string | Filter by target account ID |
| relationship_type | string | Filter by relationship type |
| limit | integer | Page size (1–100, default 25) |
| next_token | string | Pagination cursor |

**Unsupported combinations:** `source_arn` + `relationship_type` together returns 400.

**Response:** 200 with trust relationship array.

---

## Error Responses

| Status | Meaning |
|---|---|
| 400 | Bad request — invalid parameters or unsupported query combination |
| 404 | Resource not found |
| 500 | Internal server error — check CloudWatch logs |

Error response format:
```json
{ "error": "Bad Request", "message": "Filtering by both 'identity_arn' and 'status' is not supported." }
```
