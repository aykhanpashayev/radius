const SEVERITY_COLORS = {
  "Critical":   "#dc2626",
  "Very High":  "#ea580c",
  "High":       "#f97316",
  "Moderate":   "#ca8a04",
  "Low":        "#16a34a",
};

export default function SeverityBadge({ severity }) {
  const color = SEVERITY_COLORS[severity] ?? "#6b7280";
  return (
    <span className="badge" style={{ backgroundColor: color }}>
      {severity ?? "Unknown"}
    </span>
  );
}
