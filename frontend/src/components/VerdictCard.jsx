// frontend/src/components/VerdictCard.jsx
import React, { useEffect, useState } from 'react';

const VERDICTS = {
  scam: {
    color: '#d93025', bg: '#fdecea', border: '#f5c6bf',
    title: 'Scam Alert!',
    urduTitle: 'خطرہ — یہ جعلسازی لگتی ہے',
    english:
      'Warning: this message looks like a fake "relief payment" scam. Do not send money, and never share your OTP, PIN or CNIC details with anyone.',
  },
  safe: {
    color: '#188038', bg: '#e6f4ea', border: '#b7dfc2',
    title: 'Looks Safe',
    urduTitle: 'یہ پیغام محفوظ لگتا ہے',
    english: 'This message looks genuine. Still, never share your OTP or PIN with anyone.',
  },
  review: {
    color: '#b06000', bg: '#fef7e0', border: '#f3dfae',
    title: 'Needs Review',
    urduTitle: 'مزید جانچ ضروری ہے',
    english: 'We could not fully verify this message yet, so it needs a closer look.',
  },
};

const S = {
  card: { border: '2px solid', borderRadius: 14, padding: 18, width: '100%', boxSizing: 'border-box' },
  topRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  replayBtn: {
    display: 'flex', alignItems: 'center', gap: 6, background: 'transparent',
    border: '1.5px solid #cbd5e1', borderRadius: 999, padding: '6px 12px',
    fontSize: 13, fontWeight: 700, color: '#334155', cursor: 'pointer',
  },
  headRow: { display: 'flex', alignItems: 'center', gap: 14, marginTop: 14 },
  verdictTitle: { fontSize: 24, fontWeight: 800, lineHeight: 1.2 },
  urduTitle: { fontSize: 17, fontWeight: 700, marginTop: 2 },
  dotsLabel: { fontSize: 13, color: '#475569', marginBottom: 6 },
  dotRow: { display: 'flex', gap: 6, alignItems: 'center' },
  urdu: { marginTop: 16, fontSize: 18, lineHeight: 1.9, color: '#1f2933', fontWeight: 600 },
  english: { marginTop: 10, fontSize: 14, lineHeight: 1.6, color: '#475569' },
  subBox: { marginTop: 16, background: '#ffffff', border: '1px solid', borderRadius: 10, padding: 14 },
  subTitle: { fontSize: 15, fontWeight: 700, color: '#1f2933' },
  answerBtn: {
    marginTop: 10, background: '#0b5cad', color: '#ffffff', border: 'none',
    borderRadius: 8, padding: '10px 18px', fontSize: 15, fontWeight: 700,
  },
  reportBtn: {
    marginTop: 16, width: '100%', background: '#d93025', color: '#ffffff',
    border: 'none', borderRadius: 10, padding: '14px 0', fontSize: 17, fontWeight: 800,
  },
};

function TrafficLight({ verdict }) {
  const on = { scam: '#d93025', review: '#f9ab00', safe: '#188038' };
  return (
    <div
      style={{
        display: 'flex', gap: 8, alignItems: 'center',
        background: '#1f2933', borderRadius: 999, padding: '8px 12px',
      }}
      title="Traffic light"
    >
      {['scam', 'review', 'safe'].map((k) => (
        <span
          key={k}
          style={{
            width: 16, height: 16, borderRadius: '50%',
            background: verdict === k ? on[k] : '#4b5563',
            border: '2px solid #111827',
          }}
        />
      ))}
    </div>
  );
}

function IconBig({ verdict }) {
  const c = VERDICTS[verdict].color;
  const shield = 'M12 3l7 3v5c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6z';
  if (verdict === 'safe') {
    return (
      <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke={c}
        strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d={shield} fill={c} fillOpacity="0.12" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    );
  }
  if (verdict === 'scam') {
    return (
      <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke={c}
        strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d={shield} fill={c} fillOpacity="0.12" />
        <path d="M12 8v5" />
        <path d="M12 16.2h0.01" />
      </svg>
    );
  }
  return (
    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke={c}
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={shield} fill={c} fillOpacity="0.12" />
      <path d="M12 10.5a2 2 0 0 1 2 2c0 1.3-2 1.6-2 3" />
      <path d="M12 18.2h0.01" />
    </svg>
  );
}

const REPLAY_ICON = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 12a9 9 0 1 0 3-6.7" />
    <path d="M3 4v5h5" />
  </svg>
);

function speakUrdu(text) {
  try {
    if (!('speechSynthesis' in window) || !text) return;
    window.speechSynthesis.cancel();
    const u = new window.SpeechSynthesisUtterance(text);
    u.lang = 'ur-PK';
    u.rate = 0.95;
    const voices = window.speechSynthesis.getVoices();
    const ur = voices.find((v) => String(v.lang || '').toLowerCase().indexOf('ur') === 0);
    if (ur) u.voice = ur;
    window.speechSynthesis.speak(u);
  } catch (e) { /* TTS is best-effort, never block the page */ }
}

export default function VerdictCard({ result, onAnswer, onReport, reporting = false }) {
  const label = String((result && result.label) || '').toLowerCase();
  const verdict = label === 'scam' ? 'scam' : label === 'genuine' ? 'safe' : 'review';
  const v = VERDICTS[verdict];
  const route = String((result && result.route) || 'auto').toLowerCase();
  const confidence = Number(result && result.confidence) || 0;
  const dots = Math.max(0, Math.min(5, Math.round(confidence * 5)));
  const urduText = (result && result.explanation_user) || v.urduTitle;
  const englishText =
    (result && (result.explanation_user_en || result.explanation_en)) || v.english;
  const followUp =
    (result && result.follow_up_question) ||
    'براہِ کرم مزید تفصیل بتائیں: یہ پیغام کس نمبر سے آیا؟ اس میں اور کیا کہا گیا تھا؟';
  const [answer, setAnswer] = useState('');

  // Auto text-to-speech in Urdu when the verdict arrives; stop on unmount / new result.
  useEffect(() => {
    speakUrdu(result && result.explanation_user);
    return () => {
      try { window.speechSynthesis.cancel(); } catch (e) { /* ignore */ }
    };
  }, [result]);

  const canSendAnswer = Boolean(answer.trim() && onAnswer);

  return (
    <div style={{ ...S.card, background: v.bg, borderColor: v.border }}>
      <div style={S.topRow}>
        <TrafficLight verdict={verdict} />
        <button
          type="button"
          style={S.replayBtn}
          onClick={() => speakUrdu(result && result.explanation_user)}
        >
          {REPLAY_ICON}
          <span>Play again</span>
        </button>
      </div>

      <div style={S.headRow}>
        <IconBig verdict={verdict} />
        <div>
          <div style={{ ...S.verdictTitle, color: v.color }}>{v.title}</div>
          <div dir="rtl" style={{ ...S.urduTitle, color: v.color }}>{v.urduTitle}</div>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <div style={S.dotsLabel}>How sure we are (each filled dot means more certainty):</div>
        <div style={S.dotRow}>
          {[0, 1, 2, 3, 4].map((i) => (
            <span
              key={i}
              style={{
                width: 18, height: 18, borderRadius: '50%',
                background: i < dots ? v.color : '#ffffff',
                border: '2px solid ' + v.color,
              }}
            />
          ))}
        </div>
      </div>

      <div dir="rtl" style={S.urdu}>{urduText}</div>
      <div style={S.english}>{englishText}</div>

      {route === 'human' && (
        <div style={{ ...S.subBox, borderColor: v.border }}>
          <div style={S.subTitle}>
            A department officer will review this.
            {result && result.case_id !== undefined && result.case_id !== null
              ? ' Your case number is #' + result.case_id + '.'
              : ''}
          </div>
          <div dir="rtl" style={{ marginTop: 6, fontSize: 15, color: '#475569' }}>
            ایک ڈیپارٹمنٹ افسر اس کا جائزہ لے گا۔
            {result && result.case_id !== undefined && result.case_id !== null
              ? ' آپ کا کیس نمبر #' + result.case_id + ' ہے۔'
              : ''}
          </div>
        </div>
      )}

      {route === 'ask_more' && (
        <div style={{ ...S.subBox, borderColor: v.border }}>
          <div style={S.subTitle}>We need a little more information before we can decide:</div>
          <div dir="rtl" style={{ marginTop: 6, fontSize: 16, lineHeight: 1.9, color: '#1f2933' }}>
            {followUp}
          </div>
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            rows={3}
            placeholder="Type your answer here…"
            style={{
              width: '100%', marginTop: 10, padding: 10, fontSize: 15,
              borderRadius: 8, border: '1.5px solid #cbd5e1', boxSizing: 'border-box',
              resize: 'vertical',
            }}
          />
          <button
            type="button"
            style={{ ...S.answerBtn, opacity: canSendAnswer ? 1 : 0.5, cursor: canSendAnswer ? 'pointer' : 'not-allowed' }}
            onClick={() => { if (canSendAnswer) onAnswer(answer.trim()); }}
          >
            Send answer
          </button>
        </div>
      )}

      {label === 'scam' && route !== 'ask_more' && onReport && (
        <button
          type="button"
          onClick={onReport}
          disabled={reporting}
          style={{ ...S.reportBtn, cursor: reporting ? 'wait' : 'pointer' }}
        >
          {reporting ? 'Reporting…' : 'Report this scam'}
        </button>
      )}
    </div>
  );
}
