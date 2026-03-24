import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { getScores, getIncidents } from "../api";
import SummaryStrip from "../components/SummaryStrip";
import SeverityBadge from "../components/SeverityBadge";

export default function IdentityRiskTable() {
  const [scores, setScores] = useState(null);
  const [nextToken, setNextToken] = useState(null);
  const [incidents, setIncidents] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [sortDir, setSortDir] = useState(null); // null | "asc" | "desc"

  useEffect(() => {
    Promise.allSettled([
      getScores({ limit: 25 }),
      getIncidents({ status: "open", limit: 100 }),
    ]).then(([scoresResult, incidentsResult]) => {
      if (scoresResult.status === "fulfilled") {
        const data = scoresResult.value;
        setScores(data.scores ?? data);
        setNextToken(data.next_token ?? null);
      } else {
        setError(scoresResult.reason?.message ?? "Failed to load scores.");
      }

      if (incidentsResult.status === "fulfilled") {
        const data = incidentsResult.value;
        setIncidents(data.incidents ?? data);
      }
      // incidents failure is non-fatal — SummaryStrip handles null gracefully

      setLoading(false);
    });
  }, []);

  function handleLoadMore() {
    setLoadingMore(true);
    getScores({ limit: 25, next_token: nextToken })
      .then((data) => {
        setScores((prev) => [...(prev ?? []), ...(data.scores ?? data)]);
        setNextToken(data.next_token ?? null);
      })
      .catch(() => {
        // non-fatal — existing rows remain visible
      })
      .finally(() => setLoadingMore(false));
  }

  function handleSortToggle() {
    setSortDir((prev) => {
      if (prev === null) return "desc";
      if (prev === "desc") return "asc";
      return "desc";
    });
  }

  const sortIndicator = sortDir === "asc" ? " ↑" : sortDir === "desc" ? " ↓" : "";

  const displayedScores = scores
    ? sortDir === null
      ? scores
      : [...scores].sort((a, b) =>
          sortDir === "asc"
            ? a.score_value - b.score_value
            : b.score_value - a.score_value
        )
    : null;

  return (
    <div className="page-content">
      <SummaryStrip scores={scores} incidents={incidents} />

      {loading && <p className="loading">Loading identities…</p>}

      {!loading && error && (
        <p className="error-message">{error}</p>
      )}

      {!loading && !error && scores && scores.length === 0 && (
        <p className="empty-state">No identity risk scores found.</p>
      )}

      {!loading && !error && displayedScores && displayedScores.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Identity ARN</th>
              <th className="sortable" onClick={handleSortToggle}>
                Score{sortIndicator}
              </th>
              <th>Severity</th>
              <th>Last Updated</th>
            </tr>
          </thead>
          <tbody>
            {displayedScores.map((s) => (
              <tr key={s.identity_arn}>
                <td>
                  <Link to={`/identities/${encodeURIComponent(s.identity_arn)}`}>
                    {s.identity_arn}
                  </Link>
                </td>
                <td>{s.score_value}</td>
                <td>
                  <SeverityBadge severity={s.severity_level} />
                </td>
                <td>
                  {s.calculation_timestamp
                    ? new Date(s.calculation_timestamp).toLocaleDateString()
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!loading && nextToken && (
        <div style={{ marginTop: "1rem", textAlign: "center" }}>
          <button onClick={handleLoadMore} disabled={loadingMore}>
            {loadingMore ? "Loading…" : "Load more"}
          </button>
        </div>
      )}
    </div>
  );
}
