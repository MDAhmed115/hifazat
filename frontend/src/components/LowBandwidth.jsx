// frontend/src/components/LowBandwidth.jsx
//
// Mount ONCE in App.jsx, above your routes:
//   import LowBandwidth from './components/LowBandwidth.jsx';
//   <LowBandwidth />
//
// Shows a persistent slim banner when: offline, OR a fetch took >3s,
// OR Lite mode is on. Going offline auto-enables Lite mode.
// Lite mode: hides images, disables page polling (pages check isLiteMode()),
// adds ?lite=1 to every API call (backend may ignore it).
import React, { useEffect, useState } from 'react';
import { isLiteMode, setLiteMode, getPendingCount, flushQueue } from '../lib/hifazatApi.js';

const S = {
  bar: {
    position: 'sticky', top: 0, zIndex: 50,
    display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8,
    padding: '6px 12px', fontSize: 13, fontWeight: 700, color: '#ffffff',
    background: '#b06000', boxSizing: 'border-box',
  },
  barRed: { background: '#a50e0e' },
  toggle: {
    background: 'rgba(255,255,255,0.18)', color: '#ffffff', border: '1px solid rgba(255,255,255,0.6)',
    borderRadius: 999, padding: '3px 10px', fontSize: 12, fontWeight: 700, cursor: 'pointer',
  },
  pending: { fontSize: 12, fontWeight: 700, color: '#fff3c4' },
};

export default function LowBandwidth() {
  const [online, setOnline] = useState(() =>
    typeof navigator === 'undefined' ? true : navigator.onLine !== false
  );
  const [lite, setLiteState] = useState(() => isLiteMode());
  const [slow, setSlow] = useState(false);
  const [pending, setPending] = useState(() => getPendingCount());

  useEffect(() => {
    const onOnline = () => { setOnline(true); flushQueue(); };
    const onOffline = () => {
      setOnline(false);
      if (!isLiteMode()) setLiteMode(true); // weak connection => Lite mode ON
      setLiteState(isLiteMode());
      setPending(getPendingCount());
    };
    const onSlow = () => {
      setSlow(true);
      window.setTimeout(() => setSlow(false), 15000);
    };
    const onQueueChange = () => setPending(getPendingCount());
    const onLiteChange = () => setLiteState(isLiteMode());

    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);
    window.addEventListener('hifazat_slow', onSlow);
    window.addEventListener('hifazat_queue_change', onQueueChange);
    window.addEventListener('hifazat_lite_change', onLiteChange);
    flushQueue();
    const t = window.setInterval(() => {
      setPending(getPendingCount());
      flushQueue();
    }, 20000);

    return () => {
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
      window.removeEventListener('hifazat_slow', onSlow);
      window.removeEventListener('hifazat_queue_change', onQueueChange);
      window.removeEventListener('hifazat_lite_change', onLiteChange);
      window.clearInterval(t);
    };
  }, []);

  // Lite mode: hide all images with one injected CSS rule.
  useEffect(() => {
    const id = 'hifazat-lite-style';
    let tag = document.getElementById(id);
    if (lite) {
      if (!tag) {
        tag = document.createElement('style');
        tag.id = id;
        document.head.appendChild(tag);
      }
      tag.textContent = 'img { display: none !important; }';
    } else if (tag) {
      tag.parentNode.removeChild(tag);
    }
  }, [lite]);

  if (online && !slow && !lite) return null;

  const reason = !online ? 'You are offline' : slow ? 'Slow responses detected' : 'Lite mode is on';

  return (
    <div style={!online ? { ...S.bar, ...S.barRed } : S.bar}>
      <span>{reason} — Lite mode {lite ? 'ON' : 'OFF'}</span>
      <button
        type="button"
        style={S.toggle}
        onClick={() => setLiteMode(!lite)}
      >
        {lite ? 'Turn Lite OFF' : 'Turn Lite ON'}
      </button>
      {pending > 0 && (
        <span style={S.pending}>
          {pending} {pending === 1 ? 'check' : 'checks'} waiting to send — will send automatically
        </span>
      )}
    </div>
  );
}
