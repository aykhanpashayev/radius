import { Routes, Route } from "react-router-dom";

export default function App() {
  return (
    <Routes>
      <Route path="*" element={<p className="empty-state">Coming soon.</p>} />
    </Routes>
  );
}
