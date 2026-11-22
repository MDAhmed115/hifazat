// frontend/src/pages/Citizen.jsx
// STUB — next step: form to submit suspicious SMS/voice transcript + result card.
import React from "react";
import { Link } from "react-router-dom";
import PageShell from "../components/PageShell.jsx";

export default function Citizen() {
  return (
    <PageShell title="Citizen console">
      <div className="notice">
        PROTOTYPE — All data is simulated. Not an official service.
      </div>
      <h2>Report a suspicious message</h2>
      <div className="card">
        <p>
          The submission form (paste SMS, voice transcript, document text) and
          the AI decision result (scam / genuine / complaint / service_request
          with confidence and simple-Urdu explanation) will be wired here next.
        </p>
        <p>
          <Link to="/consent">Review data consent →</Link>
        </p>
      </div>
    </PageShell>
  );
}
