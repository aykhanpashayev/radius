import { NavLink } from "react-router-dom";
import "./NavBar.css";

export default function NavBar() {
  return (
    <nav className="navbar">
      <span className="navbar-brand">Radius</span>
      <ul className="navbar-links">
        <li>
          <NavLink to="/" end className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
            Dashboard
          </NavLink>
        </li>
        <li>
          <NavLink to="/incidents" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
            Incidents
          </NavLink>
        </li>
      </ul>
    </nav>
  );
}
