// frontend/src/App.jsx
import React from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import { getRole, getToken } from "./api.js";
import Login from "./pages/Login.jsx";
import Citizen from "./pages/Citizen.jsx";
import Officer from "./pages/Officer.jsx";
import Admin from "./pages/Admin.jsx";
import Auditor from "./pages/Auditor.jsx";
import Consent from "./pages/Consent.jsx";

// Which page each role lands on after login. "helper" shares the citizen
// console for now; give it its own page later if judges need to see it.
const ROLE_HOME = {
  citizen: "/citizen",
  helper: "/citizen",
  officer: "/officer",
  admin: "/admin",
  auditor: "/auditor",
};

// Blocks a page until the user is logged in (token present). If a role is
// given, also blocks a logged-in user with the wrong role and bounces them
// to their own home page instead.
function RoleGuard({ role, children }) {
  const token = getToken();
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  if (role) {
    const current = getRole();
    if (current !== role) {
      const home = ROLE_HOME[current];
      return <Navigate to={home || "/login"} replace />;
    }
  }
  return children;
}

// Send "/" to the logged-in user's home, or to /login if not logged in.
function RootRedirect() {
  const home = ROLE_HOME[getRole()];
  return <Navigate to={home || "/login"} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      {/* Permanent prototype disclaimer — never remove for the demo */}
      <div className="proto-banner">
        PROTOTYPE — All data is simulated. Not an official service.
      </div>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/login" element={<Login />} />
        <Route
          path="/citizen"
          element={
            <RoleGuard role="citizen">
              <Citizen />
            </RoleGuard>
          }
        />
        <Route
          path="/officer"
          element={
            <RoleGuard role="officer">
              <Officer />
            </RoleGuard>
          }
        />
        <Route
          path="/admin"
          element={
            <RoleGuard role="admin">
              <Admin />
            </RoleGuard>
          }
        />
        <Route
          path="/auditor"
          element={
            <RoleGuard role="auditor">
              <Auditor />
            </RoleGuard>
          }
        />
        {/* Consent page is reachable by any logged-in user */}
        <Route
          path="/consent"
          element={
            <RoleGuard>
              <Consent />
            </RoleGuard>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
