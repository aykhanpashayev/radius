const BASE = import.meta.env.VITE_API_BASE_URL;

if (!BASE) {
  console.error(
    "VITE_API_BASE_URL is not set. Create frontend/.env with:\n" +
    "VITE_API_BASE_URL=https://<your-api-id>.execute-api.<region>.amazonaws.com/dev\n" +
    "Then restart the dev server."
  );
}

async function request(path, options = {}) {
  if (!BASE) {
    throw new Error(
      "API URL not configured. Create frontend/.env with VITE_API_BASE_URL=<your api_endpoint>. " +
      "Run: terraform -chdir=infra/envs/dev output api_endpoint"
    );
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(`${BASE}${path}`, { ...options, signal: controller.signal });
    if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
    return res.json();
  } finally {
    clearTimeout(timeout);
  }
}

// Unwraps the standard list envelope { data: [...], metadata: { next_token, count } }
// Returns { items: [], nextToken: string|null }
async function requestList(path) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(`${BASE}${path}`, { signal: controller.signal });
    if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
    const json = await res.json();
    return {
      items: Array.isArray(json.data) ? json.data : (Array.isArray(json) ? json : []),
      nextToken: json.metadata?.next_token ?? null,
    };
  } finally {
    clearTimeout(timeout);
  }
}

export const getScores = (params = {}) =>
  requestList(`/scores?${new URLSearchParams(params)}`);

export const getIdentity = (arn) =>
  request(`/identities/${encodeURIComponent(arn)}`);

export const getScore = (arn) =>
  request(`/scores/${encodeURIComponent(arn)}`);

export const getIncidents = (params = {}) =>
  requestList(`/incidents?${new URLSearchParams(params)}`);

export const patchIncident = (id, status) =>
  request(`/incidents/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });

export const getEvents = (params = {}) =>
  requestList(`/events?${new URLSearchParams(params)}`);
