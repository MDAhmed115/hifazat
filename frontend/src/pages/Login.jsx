// frontend/src/pages/Login.jsx
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, TOKEN_KEY, ROLE_KEY, NAME_KEY } from "../api.js";

const ROLES = ["citizen", "helper", "officer", "admin", "auditor"];

// Where to send each role after a successful login.
const ROLE_HOME = {
  citizen: "/citizen",
  helper: "/citizen",
  officer: "/officer",
  admin: "/admin",
  auditor: "/auditor",
};

export default function Login() {
  const navigate = useNavigate();
  const [role, setRole] = useState("citizen");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const res = await api("/api/auth/login", "POST", {
      phone: phone,
      password: password,
      role: role,
    });
    setBusy(false);

    if (res.error === "network") {
      setError("Network error. Is the backend running on port 8000?");
      return;
    }
    if (res.status === 200 && res.data && res.data.token) {
      // Trust the role the server returns; fall back to the selected one.
      const serverRole = res.data.role || role;
      localStorage.setItem(TOKEN_KEY, res.data.token);
      localStorage.setItem(ROLE_KEY, serverRole);
      localStorage.setItem(NAME_KEY, res.data.name || "");
      navigate(ROLE_HOME[serverRole] || "/citizen");
      return;
    }
    if (res.status === 401) {
      setError("Wrong phone number or password.");
      return;
    }
    setError(
      "Login failed (" + res.status + "). " +
        ((res.data && (res.data.detail || res.data.error)) || "Try again.")
    );
  }

  return (
    <main className="page login-page">
      <h1 className="app-title">Hifazat</h1>
      <p className="app-subtitle">
        Protection from fake relief-payment scams.
      </p>

      <form className="card" onSubmit={handleSubmit}>
        <fieldset className="role-picker">
          <legend>I am logging in as</legend>
          <div className="role-grid">
            {ROLES.map((r) => (
              <button
                key={r}
                type="button"
                className={"role-btn" + (role === r ? " role-btn-active" : "")}
                onClick={() => setRole(r)}
              >
                {r}
              </button>
            ))}
          </div>
        </fieldset>

        <label className="field">
          <span className="field-label">Phone number</span>
          <input
            type="tel"
            inputMode="tel"
            placeholder="03XX-XXXXXXX"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            autoComplete="tel"
            required
          />
        </label>

        <label className="field">
          <span className="field-label">Password</span>
          <input
            type="password"
            placeholder="Your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        {error && <p className="form-error">{error}</p>}

        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Logging in…" : "Log in"}
        </button>

        <p className="form-hint">
          New here? Ask the hackathon desk for a demo account, or register
          through the backend seed script.
        </p>
      </form>
    </main>
  );
}
