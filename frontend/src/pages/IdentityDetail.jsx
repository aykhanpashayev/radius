import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getIdentity, getScore, getEvents } from "../api";
import SeverityBadge from "../components/SeverityBadge";

export default function IdentityDetail() {
  const { arn } = useParams();
  const decodedArn = decodeURIComponent(arn);

  const [identity, setIdentity] = useState(null);
  const [identityError, setIdentityError] = useState(null);
  const [identityNotFound, setIdentityNotFound] = useState(false);

  const [score, setScore] = useState(null);
  const [scoreError, setScoreError] = useState(null);

  const [events, setEvents] = useState(null);
  const [eventsError, setEventsError] = useState(null);

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      getIdentity(decodedArn),
      getScore(decodedArn),
      getEvents({ identity_arn: decodedArn, limit: 20 }),
    ]).then(([identityResult, scoreResult, eventsResult]) => {
      // Identity
      if (identityResult.status === "fulfilled") {
        setIdentity(identityResult.value);
      } else {
        const msg = identityResult.reason?.message ?? "";
        if (msg.includes("404")) {
          setIdentityNotFound(true);
        } else {
          setIdentityError(msg || "Failed to load identity.");
        }
      }

      // Score
      if (scoreResult.status === "fulfilled") {
        setScore(scoreResult.value);
      } else {
        setScoreError(scoreResult.reason?.message || "Failed to load score.");
      }

      // Events
      if (eventsResult.status === "fulfilled") {
        setEvents(eventsResult.value.items);
      } else {
        setEventsError(eventsResult.reason?.message || "Failed to load events.");
      }

      setLoading(false);
    });
  }, [decodedArn]);

  if (loading) {
    return (
      <div className="page-content">
        <p className="loading">Loading identity details…</p>
      </div>
    );
  }

  // Identity not found — render only the not-found message and back link
  if (identityNotFound) {
    return (
      <div className="page-content">
        <Link to="/">← Back to dashboard</Link>
        <p className="empty-state" style={{ marginTop: "2rem" }}>
          Identity not found.
        </p>
      </div>
    );
  }

  return (
    <div className="page-content">
      <Link to="/">← Back to dashboard</Link>

      {/* ── Identity Profile Card ─────────────────────────── */}
      <section style={{ marginTop: "1.5rem" }}>
        <h2 style={{ marginBottom: "1rem" }}>Identity Profile</h2>
        {identityError ? (
          <p className="error-message">{identityError}</p>
        ) : identity ? (
          <div className="card">
            <dl style={{ display: "grid", gridTemplateColumns: "max-content 1fr", gap: "0.5rem 1.5rem" }}>
              <dt style={{ color: "var(--text-muted)" }}>ARN</dt>
              <dd>{identity.identity_arn}</dd>

              <dt style={{ color: "var(--text-muted)" }}>Type</dt>
              <dd>{identity.identity_type}</dd>

              <dt style={{ color: "var(--text-muted)" }}>Account ID</dt>
              <dd>{identity.account_id}</dd>

              <dt style={{ color: "var(--text-muted)" }}>Last Activity</dt>
              <dd>
                {identity.last_activity_timestamp
                  ? new Date(identity.last_activity_timestamp).toLocaleString()
                  : "—"}
              </dd>

              <dt style={{ color: "var(--text-muted)" }}>Status</dt>
              <dd>{identity.status}</dd>
            </dl>
          </div>
        ) : null}
      </section>

      {/* ── Blast Radius Score Card ───────────────────────── */}
      <section style={{ marginTop: "1.5rem" }}>
        <h2 style={{ marginBottom: "1rem" }}>Blast Radius Score</h2>
        {scoreError || !score ? (
          <p className="empty-state">Score not yet calculated.</p>
        ) : (
          <div className="card">
            <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1rem" }}>
              <span style={{ fontSize: "3rem", fontWeight: 700, color: "var(--text)" }}>
                {score.score_value}
              </span>
              <SeverityBadge severity={score.severity_level} />
            </div>

            {score.contributing_factors?.length > 0 && (
              <div style={{ marginBottom: "1rem" }}>
                <p style={{ color: "var(--text-muted)", fontSize: "12px", marginBottom: "0.5rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Contributing Factors
                </p>
                <ul style={{ paddingLeft: "1.25rem", color: "var(--text)" }}>
                  {score.contributing_factors.map((factor, i) => (
                    <li key={i}>{factor}</li>
                  ))}
                </ul>
              </div>
            )}

            <p style={{ color: "var(--text-muted)", fontSize: "12px" }}>
              Calculated:{" "}
              {score.calculation_timestamp
                ? new Date(score.calculation_timestamp).toLocaleString()
                : "—"}
            </p>
          </div>
        )}
      </section>

      {/* ── Recent Events Table ───────────────────────────── */}
      <section style={{ marginTop: "1.5rem" }}>
        <h2 style={{ marginBottom: "1rem" }}>Recent Events</h2>
        {eventsError ? (
          <p className="error-message">{eventsError}</p>
        ) : (
          <>
            {events && events.length > 0 ? (
              <table>
                <thead>
                  <tr>
                    <th>Event Type</th>
                    <th>Timestamp</th>
                    <th>Source IP</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((evt, i) => (
                    <tr key={i}>
                      <td>{evt.event_type}</td>
                      <td>{evt.timestamp ? new Date(evt.timestamp).toLocaleString() : "—"}</td>
                      <td>{evt.source_ip ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="empty-state">No recent events found for this identity.</p>
            )}
            <p style={{ color: "var(--text-muted)", fontSize: "12px", marginTop: "0.5rem" }}>
              Showing latest 20 events.
            </p>
          </>
        )}
      </section>
    </div>
  );
}
