// frontend/src/pages/HelperDashboard.jsx  (helper role only)
//
// "One shared phone, 40 families" Helper Mode.
//
// Backend contract assumed (align with your backend team):
//   GET /api/helper/citizens -> array or {citizens|items: [
//        { id, name, phone, consent_status: 'granted'|'partial'|'withdrawn' }]}
//   GET /api/helper/citizens/{id}/consent -> { consent_status, with_officer?, with_helper? }
//        (on switch we re-read consent; if this endpoint 404s we fall back to the list value)
//   POST /api/cases { type: 'scam_report', message_text, citizen_id }  (acting on behalf)
import React, { useCallback, useEffect, useState } from 'react';
import { getJson, callApi, isLiteMode } from '../lib/hifazatApi.js';

const S = {
  page: { minHeight: '100vh', background: '#f4f7fb', color: '#1f2933', fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif', padding: '16px 0 48px' },
  inner: { maxWidth: 720, margin: '0 auto', padding: '0 12px', width: '100%', boxSizing: 'border-box' },
  title: { fontSize: 24, fontWeight: 900, color: '#0b3d6b', margin: '12px 0 4px' },
  sub: { fontSize: 13, color: '#64748b' },
  acting: {
    background: '#0b3d6b', color: '#fff', borderRadius: 12, padding: '14px 16px',
    marginTop: 14, display: 'flex', flexWrap: 'wrap', alignItems: 'center',
    justifyContent: 'space-between', gap: 8,
  },
  actingName: { fontSize: 18, fontWeight: 900 },
  list: { background: '#fff', border: '2px solid #dbe4ec', borderRadius: 12, padding: 12, marginTop: 14 },
  h3: { fontSize: 16, fontWeight: 800, color: '#0b3d6b', margin: '0 0 10px' },
  citRow: {
    display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between',
    gap: 8, padding: '10px 12px', borderRadius: 10, border: '1.5px solid #dbe4ec',
    marginBottom: 8, background: '#fff', width: '100%', textAlign: 'left', cursor: 'pointer',
    boxSizing: 'border-box',
  },
  citRowOn: { borderColor: '#0b5cad', borderWidth: 2, background: '#eef3f8' },
  citName: { fontSize: 15, fontWeight: 700 },
  chip: { padding: '3px 10px', borderRadius: 999, fontSize: 12, fontWeight: 800, color: '#fff', flexShrink: 0 },
  block: { marginTop: 14, background: '#fdecea', border: '2px solid #f5c6bf', borderRadius: 12, padding: 16 },
  blockTitle: { fontSize: 16, fontWeight: 900, color: '#8c1d18' },
  blockText: { fontSize: 14, color: '#8c1d18', marginTop: 6, lineHeight: 1.6 },
  card: { background: '#fff', border: '2px solid #dbe4ec', borderRadius: 12, padding: 16, marginTop: 14 },
  area: { width: '100%', boxSizing: 'border-box', minHeight: 110, padding: 10, fontSize: 15, borderRadius: 8, border: '1.5px solid #cbd5e1', lineHeight: 1.7, resize: 'vertical' },
  primary: { width: '100%', marginTop: 12, background: '#0b5cad', color: '#fff', border: 'none', borderRadius: 10, padding: '14px 0', fontSize: 16, fontWeight: 800, cursor: 'pointer' },
  ok: { marginTop: 10, background: '#e6f4ea', border: '1px solid #b7dfc2', color: '#116932', borderRadius: 8, padding: '10px 14px', fontSize: 14, fontWeight: 700 },
  err: { marginTop: 10, background: '#fdecea', border: '1px solid #f5c6bf', color: '#8c1d18', borderRadius: 8, padding: '10px 14px', fontSize: 14 },
  empty: { textAlign: 'center', padding: '32px 12px', color: '#64748b', fontSize: 15, fontWeight: 700 },
};

function chipStyle(status) {
  const s = String(status || '').toLowerCase();
  if (s === 'granted' || s === 'full') return { background: '#188038' };
  if (s === 'withdrawn' || s === 'revoked') return { background: '#a50e0e' };
  return { background: '#b06000' }; // partial / pending / unknown
}

export default function HelperDashboard() {
  const [citizens, setCitizens] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [acting, setActing] = useState(null); // { citizen, consent }
  const [consentLoading, setConsentLoading] = useState(false);
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [caseNo, setCaseNo] = useState(null);
  const [actionErr, setActionErr] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getJson('/api/helper/citizens');
      const list = Array.isArray(data) ? data : ((data && (data.citizens || data.items)) || []);
      setCitizens(list);
    } catch (e) {
      setError('Could not load your citizen list: ' + String((e && e.message) || e));
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

  // Every switch re-reads that citizen's consent from the server.
  const switchTo = async (citizen) => {
    setConsentLoading(true);
    setActionErr('');
    setCaseNo(null);
    try {
      let consent = citizen.consent_status || 'unknown';
      try {
        const fresh = await getJson('/api/helper/citizens/' + citizen.id + '/consent');
        if (fresh) consent = fresh.consent_status || fresh.status || consent;
      } catch (e) { /* endpoint may not exist yet: keep list value */ }
      setActing({ citizen, consent });
    } finally {
      setConsentLoading(false);
    }
  };

  const blocked = acting && String(acting.consent).toLowerCase() === 'withdrawn';

  const submitFor = async () => {
    if (!acting || blocked) return;
    if (!text.trim()) {
      setActionErr('Write the suspicious message first.');
      return;
    }
    setSubmitting(true);
    setActionErr('');
    try {
      const resp = await callApi('/api/cases', {
        method: 'POST',
        body: {
          type: 'scam_report',
          message_text: text.trim(),
          citizen_id: acting.citizen.id,
        },
      });
      const id = resp && (resp.case_id !== undefined ? resp.case_id : resp.id);
      setCaseNo(id === undefined || id === null ? null : id);
      setText('');
    } catch (e) {
      setActionErr('Could not submit: ' + String((e && e.message) || e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={S.page}>
      <div style={S.inner}>
        <div style={S.title}>Helper Dashboard</div>
        <div style={S.sub}>One shared phone for many families. Always check the name below before you act.</div>

        {acting && (
          <div style={S.acting}>
            <span>
              Acting as: <span style={S.actingName}>{acting.citizen.name}</span>
            </span>
            <span style={{ ...S.chip, ...chipStyle(acting.consent) }}>
              consent: {String(acting.consent)}
            </span>
          </div>
        )}

        {error && <div style={{ ...S.err, marginTop: 14 }}>{error}</div>}

        <div style={S.list}>
          <div style={S.h3}>My citizens ({citizens.length})</div>
          {loading && <div style={S.empty}>Loading citizens…</div>}
          {!loading && citizens.length === 0 && !error && (
            <div style={S.empty}>No citizens assigned to you yet.</div>
          )}
          {citizens.map((c) => (
            <button
              key={c.id}
              type="button"
              style={acting && acting.citizen.id === c.id ? { ...S.citRow, ...S.citRowOn } : S.citRow}
              onClick={() => switchTo(c)}
            >
              <span style={S.citName}>{c.name || ('Citizen #' + c.id)}</span>
              <span style={{ ...S.chip, ...chipStyle(c.consent_status) }}>
                {String(c.consent_status || 'unknown')}
              </span>
            </button>
          ))}
        </div>

        {acting && blocked && (
          <div style={S.block}>
            <div style={S.blockTitle}>Actions blocked</div>
            <div style={S.blockText}>
              {acting.citizen.name} has withdrawn consent. You cannot submit anything on their behalf.
              Ask them to re-enable sharing in their Consent Center, then tap their name above again.
            </div>
          </div>
        )}

        {acting && !blocked && (
          <div style={S.card}>
            <div style={S.h3}>Submit a scam report for {acting.citizen.name}</div>
            <textarea
              style={S.area}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={'Paste the suspicious SMS / message that ' + acting.citizen.name + ' received…'}
            />
            <button
              type="button"
              style={{ ...S.primary, opacity: submitting ? 0.6 : 1 }}
              disabled={submitting || consentLoading}
              onClick={submitFor}
            >
              {submitting ? 'Submitting…' : 'Submit for ' + acting.citizen.name}
            </button>
            {caseNo !== null && (
              <div style={S.ok}>
                Report filed for {acting.citizen.name}. Case number is #{caseNo}.
              </div>
            )}
            {actionErr && <div style={S.err}>{actionErr}</div>}
          </div>
        )}

        {!acting && !loading && citizens.length > 0 && (
          <div style={S.card}>
            <div style={S.h3}>Tap a citizen above to start</div>
            <div style={S.sub}>You cannot act on behalf of anyone until you select them.</div>
          </div>
        )}
      </div>
    </div>
  );
}
