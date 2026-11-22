// frontend/src/components/VoiceButton.jsx
import React, { useEffect, useRef, useState } from 'react';

const S = {
  wrap: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, width: '100%' },
  micBtn: {
    display: 'flex', alignItems: 'center', gap: 10,
    background: '#0b5cad', color: '#ffffff', border: 'none', cursor: 'pointer',
    padding: '16px 28px', fontSize: 18, fontWeight: 700, borderRadius: 999,
    boxShadow: '0 4px 12px rgba(11, 92, 173, 0.35)',
  },
  micBtnActive: { background: '#d93025', boxShadow: '0 4px 12px rgba(217, 48, 37, 0.35)' },
  micBtnDisabled: { background: '#9db4c9', cursor: 'not-allowed', boxShadow: 'none' },
  liveBox: {
    width: '100%', minHeight: 56, background: '#f1f5f9', border: '2px dashed #94a3b8',
    borderRadius: 10, padding: '10px 14px', fontSize: 17, lineHeight: 1.7,
    textAlign: 'center', boxSizing: 'border-box',
  },
  hint: { fontSize: 13, color: '#475569' },
  toast: {
    width: '100%', background: '#fdecea', color: '#8c1d18', border: '1px solid #f5c6bf',
    borderRadius: 8, padding: '10px 14px', fontSize: 14, boxSizing: 'border-box',
  },
};

const MIC_ICON = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="9" y="2" width="6" height="12" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0" />
    <path d="M12 18v4" />
    <path d="M8 22h8" />
  </svg>
);

export default function VoiceButton({ onTranscript, disabled = false }) {
  const [supported] = useState(() =>
    Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)
  );
  const [listening, setListening] = useState(false);
  const [lang, setLang] = useState('ur-PK');
  const [transcript, setTranscript] = useState('');
  const [toast, setToast] = useState('');
  const recRef = useRef(null);
  const finalRef = useRef('');
  const sessionRef = useRef(0);
  const onTranscriptRef = useRef(onTranscript);

  useEffect(() => { onTranscriptRef.current = onTranscript; }, [onTranscript]);

  // Stop the microphone if the component unmounts while listening.
  useEffect(() => () => {
    try { if (recRef.current) recRef.current.stop(); } catch (e) { /* ignore */ }
  }, []);

  const showToast = (msg) => {
    setToast(msg);
    window.setTimeout(() => setToast(''), 5000);
  };

  const startWithLang = (langCode) => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    const rec = new SR();
    rec.lang = langCode;
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    const session = sessionRef.current + 1;
    sessionRef.current = session;

    rec.onresult = (event) => {
      if (session !== sessionRef.current) return;
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const r = event.results[i];
        if (r.isFinal) finalRef.current += r[0].transcript + ' ';
        else interim += r[0].transcript;
      }
      setTranscript((finalRef.current + interim).trim());
    };

    rec.onerror = (event) => {
      if (session !== sessionRef.current) return;
      const err = event.error || 'unknown';
      if (err === 'aborted') return;
      // ur-PK not available on this machine -> fall back to English once.
      if (err === 'language-not-supported' && langCode !== 'en-US') {
        setLang('en-US');
        try { rec.abort(); } catch (e) { /* ignore */ }
        window.setTimeout(() => startWithLang('en-US'), 250);
        return;
      }
      if (err === 'not-allowed' || err === 'service-not-allowed') {
        showToast('Microphone permission is blocked. Allow mic access in the browser and try again.');
      } else if (err === 'no-speech') {
        showToast('No speech was heard. Tap the mic and speak again.');
      } else {
        showToast('Voice input problem: ' + err);
      }
      setListening(false);
    };

    rec.onend = () => {
      if (session !== sessionRef.current) return;
      setListening(false);
      const finalText = finalRef.current.trim();
      if (finalText && onTranscriptRef.current) onTranscriptRef.current(finalText);
    };

    recRef.current = rec;
    try {
      rec.start();
      setListening(true);
    } catch (e) {
      showToast('Could not start the microphone. Please try again.');
    }
  };

  const start = () => {
    setToast('');
    setTranscript('');
    finalRef.current = '';
    startWithLang(lang);
  };

  const stop = () => {
    try { if (recRef.current) recRef.current.stop(); } catch (e) { /* ignore */ }
    setListening(false);
  };

  if (!supported) {
    return (
      <div style={S.wrap}>
        <button type="button" style={{ ...S.micBtn, ...S.micBtnDisabled }} disabled>
          {MIC_ICON}
          <span>Speak</span>
        </button>
        <div style={S.toast}>
          Sorry, this browser does not support voice input. Please use the
          &quot;Paste text&quot; option and type your message instead.
        </div>
      </div>
    );
  }

  return (
    <div style={S.wrap}>
      <button
        type="button"
        disabled={disabled}
        style={listening
          ? { ...S.micBtn, ...S.micBtnActive }
          : { ...S.micBtn, ...(disabled ? S.micBtnDisabled : null) }}
        onClick={listening ? stop : start}
      >
        {MIC_ICON}
        <span>{listening ? 'Stop listening' : 'Tap to speak'}</span>
      </button>

      {listening && (
        <div style={S.hint}>
          Listening now, speak clearly ({lang})…
        </div>
      )}

      {(listening || transcript) && (
        <div style={S.liveBox} dir="auto">
          {transcript || '…'}
        </div>
      )}

      {toast && <div style={S.toast}>{toast}</div>}
    </div>
  );
}
