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
