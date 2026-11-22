// frontend/src/components/PageShell.jsx
// Shared top bar for logged-in pages: shows who you are + logout.
import React from "react";
import { useNavigate } from "react-router-dom";
import { clearAuth, getRole, NAME_KEY } from "../api.js";

export default function PageShell({ title, children }) {
  const navigate = useNavigate();
  const name = localStorage.getItem(NAME_KEY) || "";

  function handleLogout() {
    clearAuth();
    navigate("/login");
  }

  return (
    <main className="page page-wide">
      <div className="topbar">
        <span className="topbar-user">
          {title}{" "}
          <span className="topbar-role">
            — {name} ({getRole()})
          </span>
        </span>
        <button type="button" className="btn-secondary" onClick={handleLogout}>
          Log out
        </button>
      </div>
      {children}
    </main>
  );
}
