// frontend/src/pages/ConsentCenter.jsx  (citizen role only)
//
// Backend contract assumed (align with your backend team):
//   GET  /api/consents        -> { sharing: { with_officer, with_helper },
//                                  access_log: [{ who, role, what, at }] }
//        (flat shapes normalized below)
//   POST /api/consents/toggle { target: 'officer'|'helper', allow: bool }
//   POST /api/consents/withdraw -> { audit_entry: { action, actor, at, summary, ... } }
import React, { useCallback, useEffect, useState } from 'react';
import { getJson, callApi, isLiteMode } from '../lib/hifazatApi.js';

const S = {
  page: { minHeight: '100vh', background: '#f4f7fb', color: '#1f2933', fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif', padding: '16px 0 48px' },
  inner: { maxWidth: 720, margin: '0 auto', padding: '0 12px', width: '100%', boxSizing: 'border-box' },
  title: { fontSize: 24, fontWeight: 900, color: '#0b3d6b', margin: '12px 0 4px' },
  sub: { fontSize: 13, color: '#64748b' },
  card: { background: '#fff', border: '2px solid #dbe4ec', borderRadius: 12, padding: 16, marginTop: 14 },
  h3: { fontSize: 16, fontWeight: 800, color: '#0b3d6b', margin: '0 0 10px' },
  toggleRow: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, padding: '10px 0', borderBottom: '1px solid #e8eef4', flexWrap: 'wrap' },
  toggleName: { fontSize: 15, fontWeight: 700 },
  toggleDesc: { fontSize: 12, color: '#64748b' },
  chip: { padding: '3px 10px', borderRadius: 999, fontSize: 12, fontWeight: 800, color: '#fff' },
  chipOn: { background: '#188038' },
  chipOff: { background: '#9db4c9' },
  switch: { width: 52, height: 28, borderRadius: 999, border: 'none', cursor: 'pointer', position: 'relative', flexShrink: 0 },
  knob: { position: 'absolute', top: 3, width: 22, height: 22, borderRadius: '50%', background: '#fff', transition: 'left 0.15s' },
  tableWrap: { width: '100%', overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', minWidth: 420, fontSize: 13 },
  th: { textAlign: 'left', padding: '8px 10px', background: '#eef3f8', borderBottom: '2px solid #dbe4ec', whiteSpace: 'nowrap' },
  td: { padding: '8px 10px', borderBottom: '1px solid #e8eef4' },
  withdraw: { marginTop: 16, width: '100%', background: '#a50e0e', color: '#fff', border: 'none', borderRadius: 10, padding: '16px 0', fontSize: 17, fontWeight: 900, cursor: 'pointer' },
  err: { marginTop: 10, background: '#fdecea', border: '1px solid #f5c6bf', color: '#8c1d18', borderRadius: 8, padding: '10px 14px', fontSize: 14 },
  success: { background: '#fff', border: '2px solid #b7dfc2', borderRadius: 12, padding: 20, marginTop: 14 },
  quote: { borderLeft: '4px solid #188038', background: '#f6faf7', padding: '10px 14px', margin: '12px 0', fontSize: 14, lineHeight: 1.8, wordBreak: 'break-word' },
  pre: { background: '#0f172a', color: '#e2e8f0', borderRadius: 8, padding: 12, fontSize: 12, overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word' },
  backBtn: { marginTop: 8, background: 'transparent', border: '1.5px solid #0b5cad', color: '#0b5cad', borderRadius: 8, padding: '10px 16px', fontSize: 14, fontWeight: 700, cursor: 'pointer' },
};

function Toggle({ on, onChange, disabled }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      disabled={disabled}
      style={{ ...S.switch, background: on ? '#188038' : '#9db4c9', opacity: disabled ? 0.5 : 1 }}
      onClick={() => onChange(!on)}
    >
      <span style={{ ...S.knob, left: on ? 27 : 3 }} />
    </button>
  );
}

export default function ConsentCenter() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [withOfficer, setWithOfficer] = useState(false);
  const [withHelper, setWithHelper] = useState(false);
  const [accessLog, setAccessLog] = useState([]);
  const [withdrawn, setWithdrawn] = useState(false);
  const [auditEntry, setAuditEntry] = useState(null);
  const [busy, setBusy] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getJson('/api/consents');
      const d = data || {};
      const sharing = d.sharing || d.consents || {};
      setWithOfficer(Boolean(sharing.with_officer ?? sharing.officer ?? false));
      setWithHelper(Boolean(sharing.with_helper ?? sharing.helper ?? false));
      setAccessLog(d.access_log || d.accesses || d.history || []);
      setWithdrawn(Boolean(d.withdrawn));
    } catch (e) {
      setError('Could not load your consent settings: ' + String((e && e.message) || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  // Consent re-check every 30s unless Lite mode (Helper Mode depends on fresh consent).
  useEffect(() => {
    if (isLiteMode()) return undefined;
    const t = window.setInterval(load, 30000);
    return () => window.clearInterval(t);
  }, [load]);

  const toggle = async (target, allow) => {
    setBusy(target);
    setError('');
    try {
      await callApi('/api/consents/toggle', { method: 'POST', body: { target, allow } });
      if (target === 'officer') setWithOfficer(allow);
      if (target === 'helper') setWithHelper(allow);
    } catch (e) {
      setError('Could not save the toggle: ' + String((e && e.message) || e));
      load();
    } finally {
      setBusy('');
    }
  };

  const withdraw = async () => {
    const ok = window.confirm(
      'Withdraw ALL data sharing? Officers and helpers will lose access to your cases immediately. Continue?'
    );
    if (!ok) return;
    setBusy('withdraw');
    setError('');
    try {
      const resp = await callApi('/api/consents/withdraw', { method: 'POST', body: { confirm: true } });
      setAuditEntry((resp && (resp.audit_entry || resp.audit)) || resp || {});
      setWithdrawn(true);
    } catch (e) {
      setError('Could not withdraw: ' + String((e && e.message) || e));
    } finally {
      setBusy('');
    }
  };

  if (withdrawn && auditEntry) {
    const e = auditEntry;
    return (
      <div style={S.page}>
        <div style={S.inner}>
          <div style={S.title}>Data withdrawn</div>
          <div dir="rtl" style={S.sub}>آپ کا ڈیٹا واپس لے لیا گیا ہے۔</div>
          <div style={S.success}>
            <div style={{ ...S.h3, color: '#116932' }}>Your request was recorded in the audit log</div>
            <div style={S.quote}>
              {e.action ? <><b>Action:</b> {e.action}<br /></> : null}
              {e.actor ? <><b>Actor:</b> {e.actor}<br /></> : null}
              {e.at ? <><b>At:</b> {e.at}<br /></> : null}
              {e.summary ? <><b>Summary:</b> {e.summary}<br /></> : null}
              {e.entry_id !== undefined ? <><b>Audit entry:</b> #{e.entry_id}</> : null}
            </div>
            <pre style={S.pre}>{JSON.stringify(e, null, 2)}</pre>
            <button type="button" style={S.backBtn} onClick={() => { setWithdrawn(false); setAuditEntry(null); load(); }}>
              Back to Consent Center
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={S.page}>
      <div style={S.inner}>
        <div style={S.title}>Consent Center</div>
        <div style={S.sub}>You decide who can see your data. Every change is written to the audit log.</div>

        {error && <div style={S.err}>{error}</div>}

        <div style={S.card}>
          <div style={S.h3}>Sharing settings</div>
          <div style={S.toggleRow}>
            <div>
              <div style={S.toggleName}>Share with officers</div>
              <div style={S.toggleDesc}>Department officers reviewing your cases can see your messages.</div>
            </div>
            <Toggle on={withOfficer} disabled={busy !== '' || loading} onChange={(v) => toggle('officer', v)} />
          </div>
          <div style={{ ...S.toggleRow, borderBottom: 'none' }}>
            <div>
              <div style={S.toggleName}>Share with my helper</div>
              <div style={S.toggleDesc}>Your helper (family/community worker) can submit checks on your behalf.</div>
            </div>
            <Toggle on={withHelper} disabled={busy !== '' || loading} onChange={(v) => toggle('helper', v)} />
          </div>
        </div>

        <div style={S.card}>
          <div style={S.h3}>Who accessed my data</div>
          <div style={S.tableWrap}>
            <table style={S.table}>
              <thead>
                <tr><th style={S.th}>Who</th><th style={S.th}>Role</th><th style={S.th}>What</th><th style={S.th}>When</th></tr>
              </thead>
              <tbody>
                {accessLog.map((a, i) => (
                  <tr key={i}>
                    <td style={S.td}>{a.who || a.actor || a.name || '-'}</td>
                    <td style={S.td}>{a.role || '-'}</td>
                    <td style={S.td}>{a.what || a.action || '-'}</td>
                    <td style={S.td}>{a.at || a.timestamp || '-'}</td>
                  </tr>
                ))}
                {accessLog.length === 0 && (
                  <tr><td style={S.td} colSpan={4}>No access recorded yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <button type="button" style={{ ...S.withdraw, opacity: busy === 'withdraw' ? 0.6 : 1 }} disabled={busy !== ''} onClick={withdraw}>
          {busy === 'withdraw' ? 'Withdrawing…' : 'Withdraw my data'}
        </button>
      </div>
    </div>
  );
}
