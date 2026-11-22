// frontend/src/pages/AdminPanel.jsx  (admin role only)
//
// Backend contract assumed (align with your backend team):
//   GET  /api/users          -> array or {users:[{id, name, email, role}]}
//   GET  /api/rules          -> { auto_threshold, ask_more_threshold,
//                                 low_confidence_threshold, keywords: [], schemes: [], version }
//   POST /api/rules          -> same body -> { version: N }
//   GET  /api/rules/history  -> [{ version, saved_at, saved_by, ... }]
//   POST /api/mock/{name}    -> arbitrary fake response, shown inline
import React, { useCallback, useEffect, useState } from 'react';
import { getJson, callApi, isLiteMode } from '../lib/hifazatApi.js';

const S = {
  page: { minHeight: '100vh', background: '#f4f7fb', color: '#1f2933', fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif', padding: '16px 0 48px' },
  inner: { maxWidth: 960, margin: '0 auto', padding: '0 12px', width: '100%', boxSizing: 'border-box' },
  title: { fontSize: 24, fontWeight: 900, color: '#0b3d6b', margin: '12px 0 12px' },
  tabs: { display: 'flex', flexWrap: 'wrap', gap: 8 },
  tab: { border: '1.5px solid #cbd5e1', background: '#fff', color: '#334155', borderRadius: 999, padding: '8px 18px', fontSize: 14, fontWeight: 700, cursor: 'pointer' },
  tabOn: { background: '#0b5cad', borderColor: '#0b5cad', color: '#fff' },
  card: { background: '#fff', border: '2px solid #dbe4ec', borderRadius: 12, padding: 16, marginTop: 14 },
  h3: { fontSize: 16, fontWeight: 800, color: '#0b3d6b', margin: '0 0 10px' },
  field: { marginTop: 12 },
  label: { fontSize: 13, fontWeight: 700, color: '#334155', display: 'block', marginBottom: 5 },
  input: { width: '100%', boxSizing: 'border-box', padding: '9px 10px', fontSize: 15, borderRadius: 8, border: '1.5px solid #cbd5e1' },
  numRow: { display: 'flex', flexWrap: 'wrap', gap: 10 },
  numField: { flex: '1 1 150px', minWidth: 140 },
  area: { width: '100%', boxSizing: 'border-box', minHeight: 110, padding: 10, fontSize: 14, borderRadius: 8, border: '1.5px solid #cbd5e1', lineHeight: 1.7, resize: 'vertical' },
  save: { marginTop: 14, background: '#188038', color: '#fff', border: 'none', borderRadius: 8, padding: '12px 22px', fontSize: 15, fontWeight: 800, cursor: 'pointer' },
  live: { marginTop: 10, background: '#e6f4ea', border: '1px solid #b7dfc2', color: '#116932', borderRadius: 8, padding: '10px 14px', fontSize: 14, fontWeight: 800 },
  err: { marginTop: 10, background: '#fdecea', border: '1px solid #f5c6bf', color: '#8c1d18', borderRadius: 8, padding: '10px 14px', fontSize: 14 },
  tableWrap: { width: '100%', overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', minWidth: 480, fontSize: 14 },
  th: { textAlign: 'left', padding: '8px 10px', background: '#eef3f8', borderBottom: '2px solid #dbe4ec', whiteSpace: 'nowrap' },
  td: { padding: '8px 10px', borderBottom: '1px solid #e8eef4' },
  mockBtn: { border: '1.5px solid #0b5cad', background: '#fff', color: '#0b5cad', borderRadius: 8, padding: '10px 16px', fontSize: 14, fontWeight: 700, cursor: 'pointer', margin: '0 8px 8px 0' },
  pre: { background: '#0f172a', color: '#e2e8f0', borderRadius: 8, padding: 12, fontSize: 12, overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word' },
  hist: { marginTop: 16 },
  histItem: { background: '#f8fafc', borderRadius: 8, padding: '8px 12px', fontSize: 13, marginBottom: 6 },
};

const TABS = ['Users', 'Rules', 'Mock services'];
const MOCKS = [
  { key: 'sms', label: 'Send fake SMS' },
  { key: 'whatsapp', label: 'Send fake WhatsApp' },
  { key: 'payment', label: 'Credit fake relief payment' },
  { key: 'identity', label: 'Run fake identity check' },
  { key: 'reset', label: 'Reset mock data' },
];

function num(v, fallback) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

export default function AdminPanel() {
  const [tab, setTab] = useState('Users');

  // Users
  const [users, setUsers] = useState([]);
  const [usersErr, setUsersErr] = useState('');

  // Rules
  const [autoT, setAutoT] = useState('0.85');
  const [askT, setAskT] = useState('0.60');
  const [lowT, setLowT] = useState('0.60');
  const [keywords, setKeywords] = useState('');
  const [schemes, setSchemes] = useState('');
  const [rulesVersion, setRulesVersion] = useState(null);
  const [history, setHistory] = useState(null);
  const [rulesMsg, setRulesMsg] = useState('');
  const [rulesErr, setRulesErr] = useState('');
  const [saving, setSaving] = useState(false);

  // Mock
  const [mockOut, setMockOut] = useState({});
  const [mockBusy, setMockBusy] = useState('');

  const loadUsers = useCallback(async () => {
    setUsersErr('');
    try {
      const data = await getJson('/api/users');
      const list = Array.isArray(data) ? data : ((data && (data.users || data.items)) || []);
      setUsers(list);
    } catch (e) {
      setUsersErr('Could not load users: ' + String((e && e.message) || e));
    }
  }, []);

  const loadRules = useCallback(async () => {
    setRulesErr('');
    try {
      const data = await getJson('/api/rules');
      const r = (data && (data.rules || data)) || {};
      setAutoT(String(num(r.auto_threshold, 0.85)));
      setAskT(String(num(r.ask_more_threshold, 0.6)));
      setLowT(String(num(r.low_confidence_threshold, 0.6)));
      setKeywords(Array.isArray(r.keywords) ? r.keywords.join('\n') : String(r.keywords || ''));
      setSchemes(Array.isArray(r.schemes) ? r.schemes.join('\n') : String(r.schemes || ''));
      setRulesVersion(r.version ?? null);
    } catch (e) {
      setRulesErr('Could not load rules: ' + String((e && e.message) || e));
    }
    try {
      const h = await getJson('/api/rules/history');
      setHistory(Array.isArray(h) ? h : ((h && (h.items || h.history)) || []));
    } catch (e) {
      setHistory(null); // history endpoint may not exist yet in the prototype
    }
  }, []);

  useEffect(() => {
    if (tab === 'Users') loadUsers();
    if (tab === 'Rules') loadRules();
    // Mock tab needs no initial load.
  }, [tab, loadUsers, loadRules]);

  const saveRules = async () => {
    setSaving(true);
    setRulesMsg('');
    setRulesErr('');
    try {
      const body = {
        auto_threshold: Number(autoT),
        ask_more_threshold: Number(askT),
        low_confidence_threshold: Number(lowT),
        keywords: keywords.split('\n').map((s) => s.trim()).filter(Boolean),
        schemes: schemes.split('\n').map((s) => s.trim()).filter(Boolean),
      };
      const resp = await callApi('/api/rules', { method: 'POST', body });
      const v = resp && (resp.version ?? resp.rule_version);
      setRulesVersion(v ?? null);
      setRulesMsg(v !== undefined && v !== null
        ? 'Now live as version ' + v + ' — no redeploy needed'
        : 'Saved. The engine now uses the new rules.');
      try {
        const h = await getJson('/api/rules/history');
        setHistory(Array.isArray(h) ? h : ((h && (h.items || h.history)) || []));
      } catch (e2) { /* keep old history */ }
    } catch (e) {
      setRulesErr('Save failed: ' + String((e && e.message) || e));
    } finally {
      setSaving(false);
    }
  };

  const runMock = async (key) => {
    setMockBusy(key);
    try {
      const resp = await callApi('/api/mock/' + key, { method: 'POST' });
      setMockOut((prev) => ({ ...prev, [key]: JSON.stringify(resp, null, 2) }));
    } catch (e) {
      setMockOut((prev) => ({ ...prev, [key]: 'Error: ' + String((e && e.message) || e) }));
    } finally {
      setMockBusy('');
    }
  };

  return (
    <div style={S.page}>
      <div style={S.inner}>
        <div style={S.title}>Admin Panel</div>
        <div style={S.tabs}>
          {TABS.map((t) => (
            <button key={t} type="button" style={tab === t ? { ...S.tab, ...S.tabOn } : S.tab} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </div>

        {tab === 'Users' && (
          <div style={S.card}>
            <div style={S.h3}>Users ({users.length})</div>
            {usersErr && <div style={S.err}>{usersErr}</div>}
            <div style={S.tableWrap}>
              <table style={S.table}>
                <thead>
                  <tr><th style={S.th}>ID</th><th style={S.th}>Name</th><th style={S.th}>Email / Phone</th><th style={S.th}>Role</th></tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td style={S.td}>{u.id}</td>
                      <td style={S.td}>{u.name || u.full_name || '-'}</td>
                      <td style={S.td}>{u.email || u.phone || '-'}</td>
                      <td style={S.td}>{u.role || '-'}</td>
                    </tr>
                  ))}
                  {users.length === 0 && !usersErr && (
                    <tr><td style={S.td} colSpan={4}>No users found.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === 'Rules' && (
          <div style={S.card}>
            <div style={S.h3}>Decision rules {rulesVersion !== null ? '(current version ' + rulesVersion + ')' : ''}</div>
            {rulesErr && <div style={S.err}>{rulesErr}</div>}

            <div style={S.numRow}>
              <div style={S.numField}>
                <label style={S.label} htmlFor="autoT">Auto-handle threshold (confidence &ge;)</label>
                <input id="autoT" style={S.input} type="number" step="0.01" min="0" max="1" value={autoT} onChange={(e) => setAutoT(e.target.value)} />
              </div>
              <div style={S.numField}>
                <label style={S.label} htmlFor="askT">Ask-more threshold (lower bound)</label>
                <input id="askT" style={S.input} type="number" step="0.01" min="0" max="1" value={askT} onChange={(e) => setAskT(e.target.value)} />
              </div>
              <div style={S.numField}>
                <label style={S.label} htmlFor="lowT">Human-handoff cutoff (below)</label>
                <input id="lowT" style={S.input} type="number" step="0.01" min="0" max="1" value={lowT} onChange={(e) => setLowT(e.target.value)} />
              </div>
            </div>

            <div style={S.field}>
              <label style={S.label} htmlFor="kw">High-risk keywords (one per line)</label>
              <textarea id="kw" style={S.area} value={keywords} onChange={(e) => setKeywords(e.target.value)}
                placeholder={'OTP\nPIN\nsend money\nrelief payment'} />
            </div>

            <div style={S.field}>
              <label style={S.label} htmlFor="sc">Relief scheme list (one per line)</label>
              <textarea id="sc" style={S.area} value={schemes} onChange={(e) => setSchemes(e.target.value)}
                placeholder={'Bait-ul-Mal\nEhsaas Program\nBenazir Income Support'} />
            </div>

            <button type="button" style={{ ...S.save, opacity: saving ? 0.6 : 1 }} disabled={saving} onClick={saveRules}>
              {saving ? 'Saving…' : 'Save rules'}
            </button>
            {rulesMsg && <div style={S.live}>{rulesMsg}</div>}

            {history !== null && (
              <div style={S.hist}>
                <div style={S.h3}>Version history</div>
                {history.length === 0 && <div style={{ fontSize: 13, color: '#64748b' }}>No saved versions yet.</div>}
                {history.map((h) => (
                  <div key={(h.version ?? '') + String(h.saved_at ?? '')} style={S.histItem}>
                    <b>v{h.version}</b> — saved {h.saved_at || '-'} by {h.saved_by || '-'} |
                    auto &ge; {h.auto_threshold ?? '-'} / ask &ge; {h.ask_more_threshold ?? '-'} / human &lt; {h.low_confidence_threshold ?? '-'}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'Mock services' && (
          <div style={S.card}>
            <div style={S.h3}>Mock services (all data is fake)</div>
            {MOCKS.map((m) => (
              <button key={m.key} type="button" style={S.mockBtn} disabled={mockBusy === m.key}
                onClick={() => runMock(m.key)}>
                {mockBusy === m.key ? 'Calling…' : m.label}
              </button>
            ))}
            {MOCKS.map((m) => mockOut[m.key] ? (
              <div key={m.key} style={{ marginTop: 10 }}>
                <div style={S.label}>POST /api/mock/{m.key} response:</div>
                <pre style={S.pre}>{mockOut[m.key]}</pre>
              </div>
            ) : null)}
          </div>
        )}
      </div>
    </div>
  );
}
