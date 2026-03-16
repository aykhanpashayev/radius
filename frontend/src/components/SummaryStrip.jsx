export default function SummaryStrip({ scores, incidents }) {
  const total     = scores    ? scores.length                                                          : null;
  const critical  = scores    ? scores.filter(s => s.severity_level === "Critical").length             : null;
  const highVH    = scores    ? scores.filter(s => s.severity_level === "High" || s.severity_level === "Very High").length : null;
  const openCount = incidents ? incidents.filter(i => i.status === "open").length                      : null;

  const fmt = v => v === null ? "—" : v;

  return (
    <div className="summary-strip">
      <div className="summary-card">
        <span className="summary-value">{fmt(total)}</span>
        <span className="summary-label">Total Identities</span>
      </div>
      <div className="summary-card">
        <span className="summary-value">{fmt(critical)}</span>
        <span className="summary-label">Critical</span>
      </div>
      <div className="summary-card">
        <span className="summary-value">{fmt(highVH)}</span>
        <span className="summary-label">High / Very High</span>
      </div>
      <div className="summary-card">
        <span className="summary-value">{fmt(openCount)}</span>
        <span className="summary-label">Open Incidents</span>
      </div>
    </div>
  );
}
