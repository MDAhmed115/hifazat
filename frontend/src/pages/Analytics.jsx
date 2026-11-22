// frontend/src/pages/Analytics.jsx  (admin/officer roles only — read-only, no mutations)
//
// ================= ADD THESE 2 LINES TO App.jsx (App.jsx is owned by the integrator) ==========
// 1. import Analytics from './pages/Analytics.jsx';
// 2. <Route path="/analytics" element={<Analytics />} />   // gate with your existing role guard: allow ONLY 'admin' and 'officer'
// ==============================================================================================
//
// Backend contract assumed (align with your backend team):
//   GET /api/analytics -> {
//     total, handoff_rate (0..1 or 0..100), false_alarms, avg_confidence (0..1),
//     anomalies,
//     routing: { auto, ask_more, human },
//     false_alarm_rows: [{ case_id, at, original_label, corrected_to, officer }]
//   }
//   (alternative key names are normalized below)
import React, { useCallback, useEffect, useState } from 'react';
import { getJson, isLiteMode } from '../lib/hifazatApi.js';

const S = {
  page: { minHeight: '100vh', background: '#f4f7fb', color: '#1f2933', fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif', padding: '16px 0 48px' },
  inner: { maxWidth: 960, margin: '0 auto', padding: '0 12px', width: '100%', boxSizing: 'border-box' },
  titleRow: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  title: { fontSize: 24, fontWeight: 900, color: '#0b3d6b', margin: '12px 0 4px' },
  sub: { fontSize: 13, color: '#64748b' },
  refreshBtn: { background: '#0b5cad', color: '#fff', border: 'none', borderRadius: 8, padding: '9px 16px', fontSize: 14, fontWeight: 700, cursor: 'pointer' },
  cards: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10, marginTop: 14 },
  card: { background: '#fff', border: '2px solid #dbe4ec', borderRadius: 12, padding: 14, minWidth: 0 },
  cardNum: { fontSize: 26, fontWeight: 900, color: '#0b3d6b', lineHeight: 1.2 },
  cardLabel: { fontSize: 12, fontWeight: 700, color: '#64748b', marginTop: 4 },
  cost: { marginTop: 14, background: '#e6f4ea', border: '1.5px solid #b7dfc2', borderRadius: 10, padding: '12px 16px', fontSize: 16, fontWeight: 900, color: '#116932' },
  tableCard: { background: '#fff', border: '2px solid #dbe4ec', borderRadius: 12, padding: 16, marginTop: 14 },
  h3: { fontSize: 16, fontWeight: 800, color: '#0b3d6b', margin: '0 0 10px' },
  tableWrap: { width: '100%', overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', minWidth: 420, fontSize: 14 },
  th: { textAlign: 'left', padding: '8px 10px', background: '#eef3f8', borderBottom: '2px solid #dbe4ec', whiteSpace: 'nowrap' },
  td: { padding: '8px 10px', borderBottom: '1px solid #e8eef4' },
  err: { marginTop: 12, background: '#fdecea', border: '1px solid #f5c6bf', color: '#8c1d18', borderRadius: 8, padding: '10px 14px', fontSize: 14 },
};

function pct(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return '-';
  const x = n <= 1 ? n * 100 : n; // accept 0..1 or 0..100
  return Math.round(x * 10) / 10 + '%';
}

export default function Analytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const d = await getJson('/api/analytics');
      setData(d || {});
    } catch (e) {
      setError('Could not load analytics: ' + String((e && e.message) || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    if (isLiteMode()) return undefined;
    const t = window.setInterval(load, 60000);
    return () => window.clearInterval(t);
  }, [load]);

  const d = data || {};
  const total = Number(d.total ?? d.total_cases ?? 0);
  const handoffRate = d.handoff_rate ?? d.human_handoff_rate ?? 0;
  const falseAlarms = Number(d.false_alarms ?? d.false_alarm_count ?? 0);
  const avgConf = Number(d.avg_confidence ?? d.average_confidence ?? 0);
  const anomalies = Number(d.anomalies ?? d.anomaly_count ?? 0);
  const routing = d.routing || d.routing_breakdown || { auto: 0, ask_more: 0, human: 0 };
  const routingRows = [
    { name: 'auto (handled automatically)', v: Number(routing.auto ?? routing.auto_handle ?? 0) },
    { name: 'ask_more (asked for proof)', v: Number(routing.ask_more ?? routing.ask_more_proof ?? 0) },
    { name: 'human (officer handoff)', v: Number(routing.human ?? routing.human_handoff ?? 0) },
  ];
  const routingTotal = routingRows.reduce((s, r) => s + r.v, 0) || 1;
  const falseRows = d.false_alarm_rows || d.false_alarms_list || d.recent_false_alarms || [];

  return (
    <div style={S.page}>
      <div style={S.inner}>
        <div style={S.titleRow}>
          <div>
            <div style={S.title}>Analytics</div>
            <div style={S.sub}>Evaluation dashboard — routing quality, false alarms, cost.</div>
          </div>
          <button type="button" style={S.refreshBtn} onClick={load}>{loading ? 'Refreshing…' : 'Refresh'}</button>
        </div>

        {error && <div style={S.err}>{error}</div>}

        <div style={S.cards}>
          <div style={S.card}>
            <div style={S.cardNum}>{total}</div>
            <div style={S.cardLabel}>Total cases</div>
          </div>
          <div style={S.card}>
            <div style={S.cardNum}>{pct(handoffRate)}</div>
            <div style={S.cardLabel}>Human handoff rate</div>
          </div>
          <div style={S.card}>
            <div style={S.cardNum}>{falseAlarms}</div>
            <div style={S.cardLabel}>False alarms</div>
          </div>
          <div style={S.card}>
            <div style={S.cardNum}>{pct(avgConf)}</div>
            <div style={S.cardLabel}>Average confidence</div>
          </div>
          <div style={S.card}>
            <div style={S.cardNum}>{anomalies}</div>
            <div style={S.cardLabel}>Anomalies flagged</div>
          </div>
        </div>

        <div style={S.cost}>Model cost: PKR 0 (free-tier LLMs)</div>

        <div style={S.tableCard}>
          <div style={S.h3}>Routing breakdown</div>
          <div style={S.tableWrap}>
            <table style={S.table}>
              <thead>
                <tr><th style={S.th}>Route</th><th style={S.th}>Cases</th><th style={S.th}>Share</th></tr>
              </thead>
              <tbody>
                {routingRows.map((r) => (
                  <tr key={r.name}>
                    <td style={S.td}>{r.name}</td>
                    <td style={S.td}>{r.v}</td>
                    <td style={S.td}>{Math.round((r.v / routingTotal) * 1000) / 10 + '%'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div style={S.tableCard}>
          <div style={S.h3}>False-alarm tracker</div>
          <div style={S.tableWrap}>
            <table style={S.table}>
              <thead>
                <tr>
                  <th style={S.th}>Case</th>
                  <th style={S.th}>Date</th>
                  <th style={S.th}>Original label</th>
                  <th style={S.th}>Corrected to</th>
                  <th style={S.th}>Officer</th>
                </tr>
              </thead>
              <tbody>
                {falseRows.map((r, i) => (
                  <tr key={String(r.case_id ?? i)}>
                    <td style={S.td}>#{r.case_id ?? '-'}</td>
                    <td style={S.td}>{r.at || r.date || '-'}</td>
                    <td style={S.td}>{r.original_label ?? '-'}</td>
                    <td style={S.td}>{r.corrected_to ?? '-'}</td>
                    <td style={S.td}>{r.officer ?? '-'}</td>
                  </tr>
                ))}
                {falseRows.length === 0 && (
                  <tr><td style={S.td} colSpan={5}>No false alarms recorded.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
