// frontend/src/pages/Admin.jsx
// STUB — next step: user management, rule version activation, scam patterns.
import React from "react";
import PageShell from "../components/PageShell.jsx";

export default function Admin() {
  return (
    <PageShell title="Admin console">
      <div className="notice">
        PROTOTYPE — All data is simulated. Not an official service.
      </div>
      <h2>Administration</h2>
      <div className="stat-row">
        <div className="stat">
          <div className="stat-value">—</div>
          <div className="stat-label">Users</div>
        </div>
        <div className="stat">
          <div className="stat-value">—</div>
          <div className="stat-label">Cases</div>
        </div>
        <div className="stat">
          <div className="stat-value">—</div>
          <div className="stat-label">Active rule version</div>
        </div>
      </div>
      <div className="card">
        <p>
          User management, rule-version activation and scam-pattern editing
          will be wired here next. All actions already write to the audit log
          on the backend.
        </p>
      </div>
    </PageShell>
  );
}
