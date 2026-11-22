// frontend/src/pages/OfficerQueue.jsx  (officer role only)
//
// Backend contract assumed (align with your backend team):
//   GET  /api/cases/queue -> array (or {cases:[...]}) of
//        { id, citizen_name, type, status, priority, confidence, created_at }
//   GET  /api/cases/{id}  -> { case, messages: [{sender, text, created_at}],
//                              decision: { label, confidence, route,
//                                          matched_keywords, rule_version, sources } }
//        (flat shapes also accepted: fields are normalized below)
//   POST /api/cases/{id}/action { action: 'escalate'|'approve'|'reject', reason }
import React, { useCallback, useEffect, useState } from 'react';
import { getJson, callApi, isLiteMode } from '../lib/hifazatApi.js';

const S = {
  page: {
    minHeight: '100vh', background: '#f4f7fb', color: '#1f2933',
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif', padding: '16px 0 48px',
  },
  inner: { maxWidth: 960, margin: '0 auto', padding: '0 12px', width: '100%', boxSizing: 'border-box' },
  titleRow: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  title: { fontSize: 24, fontWeight: 900, color: '#0b3d6b', margin: '12px 0 4px' },
  sub: { fontSize: 13, color: '#64748b' },
  refreshBtn: {
    background: '#0b5cad', color: '#fff', border: 'none', borderRadius: 8,
    padding: '9px 16px', fontSize: 14, fontWeight: 700, cursor: 'pointer',
  },
  tableWrap: { width: '100%', overflowX: 'auto', background: '#fff', border: '2px solid #dbe4ec', borderRadius: 12, marginTop: 12 },
  table: { width: '100%', borderCollapse: 'collapse', minWidth: 640, fontSize: 14 },
  th: { textAlign: 'left', padding: '10px 12px', background: '#eef3f8', color: '#334155', borderBottom: '2px solid #dbe4ec', whiteSpace: 'nowrap' },
  td: { padding: '10px 12px', borderBottom: '1px solid #e8eef4', whiteSpace: 'nowrap' },
  rowBtn: { cursor: 'pointer' },
  badge: { display: 'inline-block', padding: '3px 10px', borderRadius: 999, color: '#fff', fontWeight: 700, fontSize: 13 },
  prio: { display: 'inline-block', padding: '3px 8px', borderRadius: 6, fontWeight: 700, fontSize: 13 },
  detail: { background: '#fff', border: '2px solid #0b5cad', borderRadius: 12, padding: 16, marginTop: 14 },
  h3: { fontSize: 16, fontWeight: 800, color: '#0b3d6b', margin: '14px 0 8px' },
  kv: { fontSize: 14, lineHeight: 1.9, margin: 0 },
  msgBox: { background: '#f1f5f9', borderRadius: 8, padding: '8px 12px', marginBottom: 8, fontSize: 14 },
  srcBox: { background: '#f8fafc', borderLeft: '3px solid #0b5cad', padding: '6px 10px', marginBottom: 6, fontSize: 13, color: '#334155' },
  reason: { width: '100%', boxSizing: 'border-box', minHeight: 70, padding: 10, fontSize: 14, borderRadius: 8, border: '1.5px solid #cbd5e1', marginTop: 6, resize: 'vertical' },
  actionRow: { display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 },
  actBtn: { border: 'none', borderRadius: 8, padding: '11px 18px', fontSize: 14, fontWeight: 800, color: '#fff', cursor: 'pointer' },
  empty: { textAlign: 'center', padding: '48px 12px', color: '#188038', fontSize: 18, fontWeight: 800 },
  err: { marginTop: 12, background: '#fdecea', border: '1px solid #f5c6bf', color: '#8c1d18', borderRadius: 8, padding: '10px 14px', fontSize: 14 },
  toast: { marginTop: 12, background: '#e6f4ea', border: '1px solid #b7dfc2', color: '#116932', borderRadius: 8, padding: '10px 14px', fontSize: 14, fontWeight: 700 },
  closeBtn: { background: 'transparent', border: '1.5px solid #94a3b8', color: '#334155', borderRadius: 8, padding: '8px 14px', fontSize: 13, fontWeight: 700, cursor: 'pointer' },
};

function bandColor(c) {
  const v = Number(c) || 0;
  if (v >= 0.85) return '#188038';
  if (v >= 0.6) return '#b06000';
  return '#d93025';
}

function prioStyle(p) {
  const v = Number(p) || 0;
  if (v >= 3) return { background: '#fdecea', color: '#8c1d18' };
  if (v === 2) return { background: '#fef7e0', color: '#7a5d00' };
  return { background: '#e8eef4', color: '#334155' };
}

function ageFrom(iso) {
  if (!iso) return '-';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '-';
  const mins = Math.max(0, Math.floor((Date.now() - then) / 60000));
  if (mins < 60) return mins + 'm';
  const hours = Math.floor(mins / 60);
  if (hours < 24) return hours + 'h ' + (mins % 60) + 'm';
  const days = Math.floor(hours / 24);
  return days + 'd ' + (hours % 24) + 'h';
}

function normList(data) {
  if (Array.isArray(data)) return data;
  if (!data) return [];
  return data.cases || data.items || data.queue || [];
}

function srcText(s) {
  if (typeof s === 'string') return s;
  return (s && (s.excerpt || s.text || s.content)) || JSON.stringify(s);
}

export default function OfficerQueue() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [selected, setSelected] = useState(null);   // queue row
  const [detail, setDetail] = useState(null);       // { case, messages, decision }
  const [detailErr, setDetailErr] = useState('');
  const [reason, setReason] = useState('');
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getJson('/api/cases/queue');
      const list = normList(data).slice();
      // priority DESC, then confidence ASC (lowest confidence first = needs attention)
      list.sort((a, b) =>
        (Number(b.priority) || 0) - (Number(a.priority) || 0) ||
        (Number(a.confidence) || 0) - (Number(b.confidence) || 0)
      );
      setRows(list);
    } catch (e) {
      setError('Could not load the queue: ' + String((e && e.message) || e));
    } finally {
      setLoading(false);
    }
  }, []);

  // 15s polling; disabled in Lite mode (manual Refresh only).
  useEffect(() => {
    load();
    if (isLiteMode()) return undefined;
    const t = window.setInterval(load, 15000);
    return () => window.clearInterval(t);
  }, [load]);

  const openDetail = async (row) => {
    setSelected(row);
    setDetail(null);
    setDetailErr('');
    setReason('');
    try {
      const data = await getJson('/api/cases/' + row.id);
      const d = data || {};
      const c = d.case || d;
      setDetail({
        caseInfo: c,
        messages: d.messages || c.messages || [],
        decision: d.decision || c.decision || c.latest_decision || null,
      });
    } catch (e) {
      setDetailErr('Could not load case detail: ' + String((e && e.message) || e));
    }
  };

  const act = async (action) => {
    if (!selected) return;
    if (!reason.trim()) {
      setDetailErr('A reason is required before you can ' + action + '.');
      return;
    }
    setActing(true);
    setDetailErr('');
    try {
      await callApi('/api/cases/' + selected.id + '/action', {
        method: 'POST',
        body: { action, reason: reason.trim() },
      });
      setToast('Case #' + selected.id + ': ' + action + ' saved.');
      setSelected(null);
      setDetail(null);
      setReason('');
      load();
    } catch (e) {
      setDetailErr('Action failed: ' + String((e && e.message) || e));
    } finally {
      setActing(false);
    }
  };

  return (
    <div style={S.page}>
      <div style={S.inner}>
        <div style={S.titleRow}>
          <div>
            <div style={S.title}>Officer Queue</div>
            <div style={S.sub}>
              Sorted by priority (high first), then lowest confidence.
              {isLiteMode() ? ' Lite mode: polling off, use Refresh.' : ' Auto-refresh every 15s.'}
            </div>
          </div>
          <button type="button" style={S.refreshBtn} onClick={load}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>

        {error && <div style={S.err}>{error}</div>}
        {toast && <div style={S.toast}>{toast}</div>}

        {rows.length === 0 && !loading && !error ? (
          <div style={{ ...S.tableWrap, ...S.empty }}>Queue clear</div>
        ) : (
          <div style={S.tableWrap}>
            <table style={S.table}>
              <thead>
                <tr>
                  <th style={S.th}>Case</th>
                  <th style={S.th}>Citizen</th>
                  <th style={S.th}>Type</th>
                  <th style={S.th}>Status</th>
                  <th style={S.th}>Priority</th>
                  <th style={S.th}>Confidence</th>
                  <th style={S.th}>Age</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const conf = Number(r.confidence) || 0;
                  return (
                    <tr
                      key={r.id}
                      style={S.rowBtn}
                      onClick={() => openDetail(r)}
                      title="Open detail"
                    >
                      <td style={S.td}>#{r.id}</td>
                      <td style={S.td}>{r.citizen_name || r.citizen || '-'}</td>
                      <td style={S.td}>{r.type || '-'}</td>
                      <td style={S.td}>{r.status || '-'}</td>
                      <td style={S.td}>
                        <span style={{ ...S.prio, ...prioStyle(r.priority) }}>{String(r.priority ?? '-')}</span>
                      </td>
                      <td style={S.td}>
                        <span style={{ ...S.badge, background: bandColor(conf) }}>
                          {Math.round(conf * 100) + '%'}
                        </span>
                      </td>
                      <td style={S.td}>{ageFrom(r.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {selected && (
          <div style={S.detail}>
            <div style={S.titleRow}>
              <div style={S.h3}>Case #{selected.id} — {selected.citizen_name || selected.citizen || 'citizen'}</div>
              <button type="button" style={S.closeBtn} onClick={() => { setSelected(null); setDetail(null); }}>
                Close
              </button>
            </div>

            {detailErr && <div style={S.err}>{detailErr}</div>}

            {!detail && !detailErr && <div style={S.sub}>Loading case detail…</div>}

            {detail && (
              <>
                <div style={S.h3}>Messages</div>
                {detail.messages.length === 0 && <div style={S.sub}>No messages recorded.</div>}
                {detail.messages.map((m, i) => (
                  <div key={i} style={S.msgBox}>
                    <b>{m.sender || 'citizen'}:</b> {m.text || m.content || m.message_text || ''}
                  </div>
                ))}

                <div style={S.h3}>AI decision trace</div>
                {detail.decision ? (
                  <div>
                    <p style={S.kv}>
                      <b>Label:</b> {detail.decision.label} &nbsp;|&nbsp;
                      <b>Confidence:</b> {Math.round((Number(detail.decision.confidence) || 0) * 100) + '%'} &nbsp;|&nbsp;
                      <b>Route:</b> {detail.decision.route || '-'} &nbsp;|&nbsp;
                      <b>Rule version:</b> {detail.decision.rule_version || '-'}
                    </p>
                    <p style={S.kv}>
                      <b>Matched keywords:</b>{' '}
                      {Array.isArray(detail.decision.matched_keywords)
                        ? detail.decision.matched_keywords.join(', ')
                        : (detail.decision.matched_keywords || 'none')}
                    </p>
                    {Array.isArray(detail.decision.sources) && detail.decision.sources.length > 0 && (
                      <div>
                        <p style={S.kv}><b>Sources (excerpts):</b></p>
                        {detail.decision.sources.map((s, i) => (
                          <div key={i} style={S.srcBox}>{srcText(s)}</div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={S.sub}>No decision trace stored for this case.</div>
                )}

                <div style={S.h3}>Take action</div>
                <textarea
                  style={S.reason}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Required reason (stored in the audit log)…"
                />
                <div style={S.actionRow}>
                  <button type="button" disabled={acting}
                    style={{ ...S.actBtn, background: '#b06000', opacity: acting ? 0.6 : 1 }}
                    onClick={() => act('escalate')}>
                    Escalate
                  </button>
                  <button type="button" disabled={acting}
                    style={{ ...S.actBtn, background: '#188038', opacity: acting ? 0.6 : 1 }}
                    onClick={() => act('approve')}>
                    Approve
                  </button>
                  <button type="button" disabled={acting}
                    style={{ ...S.actBtn, background: '#d93025', opacity: acting ? 0.6 : 1 }}
                    onClick={() => act('reject')}>
                    Reject
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
