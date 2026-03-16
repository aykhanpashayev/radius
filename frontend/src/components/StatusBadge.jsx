const STATUS_COLORS = {
  "open":           "#dc2626",
  "investigating":  "#ca8a04",
  "resolved":       "#16a34a",
  "false_positive": "#6b7280",
};

export default function StatusBadge({ status }) {
  const color = STATUS_COLORS[status] ?? "#6b7280";
  return (
    <span className="badge" style={{ backgroundColor: color }}>
      {status ?? "unknown"}
    </span>
  );
}
