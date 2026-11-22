// frontend/src/pages/Auditor.jsx
// STUB — next step: read-only audit_log viewer with filters.
import React from "react";
import PageShell from "../components/PageShell.jsx";

export default function Auditor() {
  return (
    <PageShell title="Auditor console">
      <div className="notice">
        PROTOTYPE — All data is simulated. Not an official service.
      </div>
      <h2>Audit trail</h2>
      <div className="card">
        <p>
          A read-only, filterable view of every audit_log row (who did what,
          when) will be rendered here. Auditors can see traces but can never
          mutate case data — enforced server-side by RBAC.
        </p>
      </div>
    </PageShell>
  );
}
