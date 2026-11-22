// frontend/src/pages/AuditorView.jsx  (auditor role; admin may also use it)
//
// Backend contract assumed (align with your backend team):
//   GET /api/audit                 -> array or {audit_log|items: [
//        { id, at, actor, role, action, target, summary, decision_id? }]}
//   GET /api/decisions/{id}/trace  -> { label, confidence, route, matched_keywords,
//                                       rule_version, sources, model, latency_ms, raw? }
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { getJson, isLiteMode } from '../lib/hifazatApi.js';

const S = {
  page: { minHeight: '100vh', background: '#f4f7fb', color: '#1f2933', fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif', padding: '16px 0 48px' },
  inner: { maxWidth: 960, margin: '0 auto', padding: '0 12px', width: '100%', boxSizing: 'border-box' },
  titleRow: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  title: { fontSize: 24, fontWeight: 900, color: '#0b3d6b', margin: '12px 0 4px' },
  sub: { fontSize: 13, color: '#64748b' },
  refreshBtn: { background: '#0b5cad', color: '#fff', border: 'none', borderRadius: 8, padding: '9px 16px', fontSize: 14, fontWeight: 700, cursor: 'pointer' },
  filters: { display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 },
  input: { flex: '1 1 160px', minWidth: 140, padding: '9px 10px', fontSize: 14, borderRadius: 8, border: '1.5px solid #cbd5e1', boxSizing: 'border-box' },
  select: { padding: '9px 10px', fontSize: 14, borderRadius: 8, border: '1.5px solid #cbd5e1', background: '#fff' },
  tableWrap: { width: '100%', overflowX: 'auto', background: '#fff', border: '2px solid #dbe4ec', borderRadius: 12, marginTop: 12 },
  table: { width: '100%', borderCollapse: 'collapse', minWidth: 640, fontSize: 13 },
  th: { textAlign: 'left', padding: '8px 10px', background: '#eef3f8', borderBottom: '2px solid #dbe4ec', whiteSpace: 'nowrap' },
  td: { padding: '8px 10px', borderBottom: '1px solid #e8eef4', whiteSpace: 'nowrap' },
  traceBtn: { border: '1.5px solid #0b5cad', background: '#fff', color: '#0b5cad', borderRadius: 6, padding: '5px 10px', fontSize: 12, fontWeight: 700, cursor: 'pointer' },
  traceBtnOff: { border: '1.5px solid #cbd5e1', background: '#f1f5f9', color: '#94a3b8', borderRadius: 6, padding: '5px 10px', fontSize: 12, fontWeight: 700, cursor: 'not-allowed' },
  panel: { background: '#fff', border: '2px solid #0b5cad', borderRadius: 12, padding: 16, marginTop: 14 },
  h3: { fontSize: 16, fontWeight: 800, color: '#0b3d6b', margin: '0 0 8px' },
  kv: { fontSize: 14, lineHeight: 1.9, margin: '0 0 6px' },
  srcBox: { background: '#f8fafc', borderLeft: '3px solid #0b5cad', padding: '6px 10px', marginBottom: 6, fontSize: 13, color: '#334155', wordBreak: 'break-word' },
  pre: { background: '#0f172a', color: '#e2e8f0', borderRadius: 8, padding: 12, fontSize: 12, overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginTop: 10 },
  err: { marginTop: 12, background: '#fdecea', border: '1px solid #f5c6bf', color: '#8c1d18', borderRadius: 8, padding: '10px 14px', fontSize: 14 },
  closeBtn: { background: 'transparent', border: '1.5px solid #94a3b8', color: '#334155', borderRadius: 8, padding: '8px 14px', fontSize: 13, fontWeight: 700, cursor: 'pointer' },
};

function srcText(s) {
  if (typeof s === 'string') return s;
  return (s && (s.excerpt || s.text || s.content)) || JSON.stringify(s);
}

function normList(data) {
  if (Array.isArray(data)) return data;
  if (!data) return [];
  return data.audit_log || data.items || data.entries || [];
}

export default function AuditorView() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [q, setQ] = useState('');
  const [action, setAction] = useState('all');
  const [trace, setTrace] = useState(null);
  const [traceErr, setTraceErr] = useState('');
  const [traceLoading, setTraceLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getJson('/api/audit');
      setRows(normList(data));
    } catch (e) {
      setError('Could not load the audit log: ' + String((e && e.message) || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    if (isLiteMode()) return undefined;
    const t = window.setInterval(load, 30000);
    return () => window.clearInterval(t);
  }, [load]);

  const actions = useMemo(() => {
    const set = new Set();
    rows.forEach((r) => { if (r.action) set.add(String(r.action)); });
    return Array.from(set).sort();
  }, [rows]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return rows.filter((r) => {
      if (action !== 'all' && String(r.action) !== action) return false;
      if (!needle) return true;
      const hay = [r.actor, r.role, r.action, r.target, r.summary, r.id]
        .map((x) => String(x == null ? '' : x).toLowerCase()).join(' ');
      return hay.indexOf(needle) !== -1;
    });
  }, [rows, q, action]);

  const openTrace = async (row) => {
    setTraceLoading(true);
    setTraceErr('');
    setTrace(null);
    try {
      const data = await getJson('/api/decisions/' + row.decision_id + '/trace');
      setTrace(data || {});
    } catch (e) {
      setTraceErr('Could not load trace: ' + String((e && e.message) || e));
    } finally {
      setTraceLoading(false);
    }
  };

  return (
    <div style={S.page}>
      <div style={S.inner}>
        <div style={S.titleRow}>
          <div>
            <div style={S.title}>Audit Log</div>
            <div style={S.sub}>
              Every mutation in the system, immutable, newest last as received.
              {isLiteMode() ? ' Lite mode: polling off.' : ' Auto-refresh every 30s.'}
            </div>
          </div>
          <button type="button" style={S.refreshBtn} onClick={load}>{loading ? 'Refreshing…' : 'Refresh'}</button>
        </div>

        <div style={S.filters}>
          <input style={S.input} value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Filter by actor, action, target…" />
          <select style={S.select} value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="all">All actions</option>
            {actions.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>

        {error && <div style={S.err}>{error}</div>}

        <div style={S.tableWrap}>
          <table style={S.table}>
            <thead>
              <tr>
                <th style={S.th}>#</th>
                <th style={S.th}>Time</th>
                <th style={S.th}>Actor</th>
                <th style={S.th}>Role</th>
                <th style={S.th}>Action</th>
                <th style={S.th}>Target</th>
                <th style={S.th}>Trace</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.id ?? (r.at + String(r.actor))}>
                  <td style={S.td}>{r.id ?? '-'}</td>
                  <td style={S.td}>{r.at || r.timestamp || '-'}</td>
                  <td style={S.td}>{r.actor || '-'}</td>
                  <td style={S.td}>{r.role || '-'}</td>
                  <td style={S.td}>{r.action || '-'}</td>
                  <td style={S.td}>{r.target || r.summary || '-'}</td>
                  <td style={S.td}>
                    {r.decision_id ? (
                      <button type="button" style={S.traceBtn} onClick={() => openTrace(r)}>
                        View trace
                      </button>
                    ) : (
                      <button type="button" style={S.traceBtnOff} disabled title="No decision linked to this entry">
                        n/a
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && !error && (
                <tr><td style={S.td} colSpan={7}>No audit entries match the filter.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {(traceLoading || trace || traceErr) && (
          <div style={S.panel}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <div style={S.h3}>Decision trace</div>
              <button type="button" style={S.closeBtn}
                onClick={() => { setTrace(null); setTraceErr(''); setTraceLoading(false); }}>
                Close
              </button>
            </div>
            {traceLoading && <div style={S.sub}>Loading trace…</div>}
            {traceErr && <div style={S.err}>{traceErr}</div>}
            {trace && (
              <>
                <p style={S.kv}>
                  <b>Label:</b> {trace.label ?? '-'} &nbsp;|&nbsp;
                  <b>Confidence:</b> {trace.confidence !== undefined ? Math.round(Number(trace.confidence) * 100) + '%' : '-'} &nbsp;|&nbsp;
                  <b>Route:</b> {trace.route ?? '-'} &nbsp;|&nbsp;
                  <b>Rule version:</b> {trace.rule_version ?? '-'} &nbsp;|&nbsp;
                  <b>Model:</b> {trace.model ?? '-'} &nbsp;|&nbsp;
                  <b>Latency:</b> {trace.latency_ms !== undefined ? trace.latency_ms + ' ms' : '-'}
                </p>
                <p style={S.kv}>
                  <b>Matched keywords:</b>{' '}
                  {Array.isArray(trace.matched_keywords) ? trace.matched_keywords.join(', ') : (trace.matched_keywords || 'none')}
                </p>
                {Array.isArray(trace.sources) && trace.sources.length > 0 && (
                  <div>
                    <p style={S.kv}><b>Sources (excerpts):</b></p>
                    {trace.sources.map((s, i) => <div key={i} style={S.srcBox}>{srcText(s)}</div>)}
                  </div>
                )}
                <pre style={S.pre}>{JSON.stringify(trace, null, 2)}</pre>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
