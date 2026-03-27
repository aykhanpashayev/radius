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
