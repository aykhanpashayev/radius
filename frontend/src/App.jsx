import { Routes, Route } from "react-router-dom";
import NavBar from "./components/NavBar";

export default function App() {
  return (
    <>
      <NavBar />
      <Routes>
        <Route path="*" element={<p className="empty-state">Coming soon.</p>} />
      </Routes>
    </>
  );
}
