// frontend/src/pages/Officer.jsx
// STUB — next step: human-handoff queue (cases with confidence < 0.60 or high risk).
import React from "react";
import PageShell from "../components/PageShell.jsx";

export default function Officer() {
  return (
    <PageShell title="Officer console">
      <div className="notice">
        PROTOTYPE — All data is simulated. Not an official service.
      </div>
      <h2>Human handoff queue</h2>
      <div className="card">
        <p>
          Cases escalated by the decision engine (confidence below 0.60 or
          high-risk keywords) will be listed here for review, with the full
          decision trace available per case.
        </p>
      </div>
    </PageShell>
  );
}
