import { Routes, Route } from "react-router-dom";
import NavBar from "./components/NavBar";
import IdentityRiskTable from "./pages/IdentityRiskTable";
import IncidentFeed from "./pages/IncidentFeed";
import IdentityDetail from "./pages/IdentityDetail";
import Login from "./pages/Login";

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={
          <>
            <NavBar />
            <Routes>
              <Route path="/" element={<IdentityRiskTable />} />
              <Route path="/incidents" element={<IncidentFeed />} />
              <Route path="/identities/:arn" element={<IdentityDetail />} />
              <Route path="*" element={<p className="empty-state">Page not found.</p>} />
            </Routes>
          </>
        } />
      </Routes>
    </>
  );
}
