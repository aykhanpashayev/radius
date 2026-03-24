import { useState, useEffect } from "react";
import { getIncidents, patchIncident } from "../api";
import SeverityBadge from "../components/SeverityBadge";
import StatusBadge from "../components/StatusBadge";

const TRANSITIONS = {
  open: ["investigating"],
  investigating: ["resolved", "false_positive"],
  resolved: [],
  false_positive: [],
};

export default function IncidentFeed() {
  const [incidents, setIncidents] = useState([]);
  const [nextToken, setNextToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [cardErrors, setCardErrors] = useState({});

  useEffect(() => {
    getIncidents({ limit: 25 })
      .then((data) => {
        setIncidents(data.incidents ?? []);
        setNextToken(data.next_token ?? null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  function handleLoadMore() {
    setLoadingMore(true);
    getIncidents({ limit: 25, next_token: nextToken })
      .then((data) => {
        setIncidents((prev) => [...prev, ...(data.incidents ?? [])]);
        setNextToken(data.next_token ?? null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoadingMore(false));
  }

  function handleStatusChange(incidentId, newStatus) {
    patchIncident(incidentId, newStatus)
      .then(() => {
        setIncidents((prev) =>
          prev.map((inc) =>
            inc.incident_id === incidentId ? { ...inc, status: newStatus } : inc
          )
        );
        setCardErrors((prev) => ({ ...prev, [incidentId]: null }));
      })
      .catch((err) => {
        setCardErrors((prev) => ({ ...prev, [incidentId]: err.message }));
      });
  }

  return (
    <div className="page-content">
      <h1 style={{ marginBottom: "1.5rem" }}>Incident Feed</h1>

      {loading && <p className="loading">Loading incidents…</p>}

      {error && <p className="error-message">{error}</p>}

      {!loading && !error && incidents.length === 0 && (
        <p className="empty-state">No incidents found.</p>
      )}

      {incidents.map((incident, idx) => (
        <div key={incident.incident_id} className="card" style={{ marginBottom: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "0.5rem" }}>
            <div>
              <span style={{ fontFamily: "monospace", fontSize: "13px", color: "var(--text-muted)" }}>
                {incident.incident_id.slice(0, 8)}…
              </span>
            </div>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <SeverityBadge severity={incident.severity} />
              {TRANSITIONS[incident.status]?.length > 0 ? (
                <select
                  value={incident.status}
                  onChange={(e) => handleStatusChange(incident.incident_id, e.target.value)}
                  style={{ fontSize: "13px" }}
                >
                  <option value={incident.status} disabled>
                    {incident.status}
                  </option>
                  {TRANSITIONS[incident.status].map((next) => (
                    <option key={next} value={next}>
                      {next}
                    </option>
                  ))}
                </select>
              ) : (
                <StatusBadge status={incident.status} />
              )}
            </div>
          </div>

          {cardErrors[incident.incident_id] && (
            <p className="error-message" style={{ marginTop: "0.5rem", marginBottom: 0 }}>
              {cardErrors[incident.incident_id]}
            </p>
          )}

          <div style={{ marginTop: "0.75rem", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.5rem" }}>
            <div>
              <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Identity ARN</span>
              <p style={{ marginTop: "2px", wordBreak: "break-all" }}>{incident.identity_arn}</p>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Detection Type</span>
              <p style={{ marginTop: "2px" }}>{incident.detection_type}</p>
            </div>
            <div>
              <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Created</span>
              <p style={{ marginTop: "2px" }}>
                {incident.creation_timestamp
                  ? new Date(incident.creation_timestamp).toLocaleString()
                  : "—"}
              </p>
            </div>
          </div>
        </div>
      ))}

      {nextToken && (
        <div style={{ textAlign: "center", marginTop: "1.5rem" }}>
          <button onClick={handleLoadMore} disabled={loadingMore}>
            {loadingMore ? "Loading…" : "Load more"}
          </button>
        </div>
      )}
    </div>
  );
}
