// frontend/src/pages/Consent.jsx
// STUB — next step: POST consent record to backend consents table.
import React, { useState } from "react";
import PageShell from "../components/PageShell.jsx";
import { api } from "../api.js";

const CONSENT_KEY = "hifazat_consent_v1";

export default function Consent() {
  const [given, setGiven] = useState(
    localStorage.getItem(CONSENT_KEY) === "yes"
  );
  const [saved, setSaved] = useState("");

  async function handleToggle(e) {
    const value = e.target.checked;
    setGiven(value);
    localStorage.setItem(CONSENT_KEY, value ? "yes" : "no");
    // Wire to the backend consents table; kept non-blocking so the demo
    // still works if the endpoint is not up yet.
    const res = await api("/api/consents", "POST", { granted: value });
    if (res.error === "network") {
      setSaved("Saved on this device only (backend unreachable).");
    } else if (res.ok) {
      setSaved("Saved.");
    } else {
      setSaved("Saved on this device only (endpoint not ready yet).");
    }
  }

  return (
    <PageShell title="Data consent">
      <div className="notice">
        PROTOTYPE — All data is simulated. Not an official service.
      </div>
      <h2>Your consent</h2>
      <div className="consent-box">
        <label>
          <input
            type="checkbox"
            checked={given}
            onChange={handleToggle}
          />
          <span>
            I allow Hifazat to store the suspicious message I submit and the
            decision made about it, so officers can review the case. I
            understand this is a prototype and all data is mock data.
          </span>
        </label>
      </div>
      {saved && <p className="form-hint">{saved}</p>}
    </PageShell>
  );
}
