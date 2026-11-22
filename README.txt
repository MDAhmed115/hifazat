HIFAZAT FRONTEND — file drop (PROTOTYPE, all data mock)
========================================================

WHAT IS IN THIS ZIP
-------------------
frontend/src/lib/hifazatApi.js            API helper + Lite mode + offline queue (REPLACES your old hifazatApi.js; exports analyzeMessage / reportScam unchanged, so CitizenHome needs no edits)
frontend/src/components/LowBandwidth.jsx  Offline / slow-connection banner + Lite mode toggle + pending-queue counter
frontend/src/components/VoiceButton.jsx   ur-PK voice input (Web Speech API, en-US fallback)
frontend/src/components/VerdictCard.jsx   Traffic light + 5-dot confidence meter + Urdu TTS verdict card
frontend/src/pages/CitizenHome.jsx        Citizen experience page (paste / speak / upload)
frontend/src/pages/OfficerQueue.jsx       Officer queue (15s polling, detail panel, Escalate/Approve/Reject)
frontend/src/pages/AdminPanel.jsx         Admin panel (Users / Rules / Mock services tabs)
frontend/src/pages/ConsentCenter.jsx      Citizen consent (toggles, access log, withdraw)
frontend/src/pages/AuditorView.jsx        Audit log table + decision trace viewer
frontend/src/pages/HelperDashboard.jsx    Helper Mode ("one shared phone, 40 families")
frontend/src/pages/Analytics.jsx          Evaluation dashboard (admin/officer, no chart libs)

HOW TO INSTALL
--------------
1. Extract this zip at your project ROOT. It creates/overwrites frontend/src/...
   (It will NOT touch your App.jsx, Login, api.js, package.json or CSS.)
2. No new npm packages are required. Files use only React + browser APIs + fetch.

LINES TO ADD TO App.jsx (App.jsx is owned by you — not included in the zip)
---------------------------------------------------------------------------
import LowBandwidth from './components/LowBandwidth.jsx';
import CitizenHome from './pages/CitizenHome.jsx';
import OfficerQueue from './pages/OfficerQueue.jsx';
import AdminPanel from './pages/AdminPanel.jsx';
import ConsentCenter from './pages/ConsentCenter.jsx';
import AuditorView from './pages/AuditorView.jsx';
import HelperDashboard from './pages/HelperDashboard.jsx';
import Analytics from './pages/Analytics.jsx';

Render <LowBandwidth /> ONCE above your <Routes> (sticky banner on every page).

Routes (gate each with your existing role guard):
  <Route path="/citizen"   element={<CitizenHome />} />     // citizen
  <Route path="/queue"     element={<OfficerQueue />} />    // officer
  <Route path="/admin"     element={<AdminPanel />} />      // admin
  <Route path="/consents"  element={<ConsentCenter />} />   // citizen
  <Route path="/audit"     element={<AuditorView />} />     // auditor
  <Route path="/helper"    element={<HelperDashboard />} /> // helper
  <Route path="/analytics" element={<Analytics />} />       // admin + officer ONLY

RUN (backend first)
-------------------
Linux/macOS:
  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
Windows (PowerShell):
  cd backend; .\.venv\Scripts\Activate.ps1; python -m uvicorn app.main:app --reload --port 8000

Then, in a second terminal (both OS):
  cd frontend && npm install && npm run dev
Open http://localhost:5173

CONFIG
------
Backend on another host/port? Create frontend/.env with:
  VITE_API_URL=http://localhost:8000

JWT TOKEN KEY
-------------
hifazatApi.js looks for the token in localStorage/sessionStorage under:
  token, hifazat_token, auth_token, access_token, jwt
If your Login stores it under a different key, add that key to TOKEN_KEYS
at the top of frontend/src/lib/hifazatApi.js.

BACKEND CONTRACTS ASSUMED (forward to your backend team)
--------------------------------------------------------
POST /api/analyze            {message_text} -> {label, confidence, route, explanation_user, case_id?}
POST /api/cases              {type:"scam_report", message_text, citizen_id?}
GET  /api/cases/queue        -> [{id, citizen_name, type, status, priority, confidence, created_at}]
GET  /api/cases/{id}         -> {case, messages:[{sender,text,created_at}], decision:{label, confidence, route, matched_keywords, rule_version, sources}}
POST /api/cases/{id}/action  {action:'escalate'|'approve'|'reject', reason}
GET  /api/users              -> [{id, name, email, role}]
GET/POST /api/rules          -> {auto_threshold, ask_more_threshold, low_confidence_threshold, keywords:[], schemes:[], version}
GET  /api/rules/history      -> [{version, saved_at, saved_by, ...}]
POST /api/mock/{name}        -> fake response (sms, whatsapp, payment, identity, reset)
GET  /api/consents           -> {sharing:{with_officer, with_helper}, access_log:[{who, role, what, at}]}
POST /api/consents/toggle    {target:'officer'|'helper', allow:bool}
POST /api/consents/withdraw  -> {audit_entry:{action, actor, at, summary, ...}}
GET  /api/audit              -> [{id, at, actor, role, action, target, summary, decision_id?}]
GET  /api/decisions/{id}/trace -> {label, confidence, route, matched_keywords, rule_version, sources, model, latency_ms}
GET  /api/helper/citizens    -> [{id, name, phone, consent_status}]
GET  /api/helper/citizens/{id}/consent -> {consent_status}
GET  /api/analytics          -> {total, handoff_rate, false_alarms, avg_confidence, anomalies, routing:{auto,ask_more,human}, false_alarm_rows:[...]}

Each page also documents its assumed contract in a comment block at the top
of the file, and normalizes a few alternative key names defensively.

RESILIENCE FEATURES (already wired inside the files)
----------------------------------------------------
- Lite mode: banner toggle or auto-on when offline. Hides images, disables
  page polling, adds ?lite=1 to all API calls (backend may ignore).
- Offline queue: POST /api/analyze and POST /api/cases made while offline are
  stored in localStorage with a uuid idempotency key (X-Idempotency-Key header
  + idempotency_key in the body) and flushed exactly once each on reconnect.
- All pages pass at 320px width (tables scroll horizontally inside their own
  wrapper; grids use auto-fit/minmax; no fixed widths).
