// frontend/src/pages/CitizenHome.jsx
import React, { useEffect, useRef, useState } from 'react';
import VoiceButton from '../components/VoiceButton.jsx';
import VerdictCard from '../components/VerdictCard.jsx';
import { analyzeMessage, reportScam } from '../lib/hifazatApi.js';

const PROGRESS_STEPS = [
  'Checking official documents…',
  'Matching known scam patterns…',
  'Applying safety rules…',
  'Preparing your result in Urdu…',
];

const S = {
  page: {
    minHeight: '100vh', background: '#f4f7fb', color: '#1f2933',
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, "Noto Nastaliq Urdu", sans-serif',
    padding: '0 0 48px',
  },
  inner: { maxWidth: 640, margin: '0 auto', padding: '16px' },
  header: { display: 'flex', alignItems: 'center', gap: 12, padding: '18px 0 10px' },
  title: { fontSize: 30, fontWeight: 900, color: '#0b3d6b', lineHeight: 1.1 },
  subtitle: { fontSize: 15, color: '#475569' },
  banner: {
    background: '#fff8e1', border: '1.5px dashed #c9a400', color: '#7a5d00',
    borderRadius: 8, padding: '8px 12px', fontSize: 13, fontWeight: 700, textAlign: 'center',
  },
  toast: {
    marginTop: 12, background: '#fdecea', border: '1px solid #f5c6bf', color: '#8c1d18',
    borderRadius: 8, padding: '10px 14px', fontSize: 14,
  },
  question: { fontSize: 17, fontWeight: 700, margin: '20px 0 12px' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 },
  bigBtn: {
    background: '#ffffff', border: '2px solid #dbe4ec', borderRadius: 14,
    padding: '18px 8px', cursor: 'pointer', display: 'flex',
    flexDirection: 'column', alignItems: 'center', gap: 8,
    fontSize: 14, fontWeight: 700, color: '#1f2933',
  },
  bigBtnSub: { fontSize: 13, color: '#64748b', fontWeight: 600 },
  panel: {
    background: '#ffffff', border: '2px solid #dbe4ec', borderRadius: 14,
    padding: 16, marginTop: 14,
  },
  panelUrdu: { fontSize: 14, color: '#475569', marginBottom: 10 },
  textarea: {
    width: '100%', minHeight: 130, padding: 12, fontSize: 16, borderRadius: 10,
    border: '1.5px solid #cbd5e1', boxSizing: 'border-box', lineHeight: 1.7,
    resize: 'vertical',
  },
  primaryBtn: {
    width: '100%', marginTop: 12, background: '#0b5cad', color: '#ffffff',
    border: 'none', borderRadius: 10, padding: '14px 0', fontSize: 17, fontWeight: 800,
    cursor: 'pointer',
  },
  ghostBtn: {
    marginTop: 14, background: 'transparent', color: '#0b5cad', border: '1.5px solid #0b5cad',
    borderRadius: 10, padding: '10px 16px', fontSize: 14, fontWeight: 700, cursor: 'pointer',
  },
  loadingBox: {
    background: '#ffffff', border: '2px solid #dbe4ec', borderRadius: 14,
    padding: 28, marginTop: 14, textAlign: 'center',
  },
  progressText: { marginTop: 12, fontSize: 16, fontWeight: 700, color: '#0b3d6b' },
  progressSub: { marginTop: 6, fontSize: 13, color: '#64748b' },
  resultWrap: { marginTop: 14 },
  successBox: {
    background: '#ffffff', border: '2px solid #b7dfc2', borderRadius: 14,
    padding: 28, marginTop: 14, textAlign: 'center',
  },
  successTitle: { fontSize: 22, fontWeight: 900, color: '#188038', marginTop: 10 },
  successUrdu: { fontSize: 17, color: '#188038', marginTop: 4, fontWeight: 700 },
  caseNumber: { fontSize: 17, color: '#1f2933', marginTop: 10 },
  caseUrdu: { fontSize: 14, color: '#64748b', marginTop: 4 },
  note: { fontSize: 14, color: '#475569', lineHeight: 1.6 },
};

const LOGO = (
  <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#0b5cad"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M12 3l7 3v5c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6z" fill="#0b5cad" fillOpacity="0.12" />
    <path d="M9 12l2 2 4-4" />
  </svg>
);

function IconPaste() {
  return (
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#0b5cad"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M8 8h8" />
      <path d="M8 12h8" />
      <path d="M8 16h5" />
    </svg>
  );
}

function IconMic() {
  return (
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#0b5cad"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0" />
      <path d="M12 18v4" />
      <path d="M8 22h8" />
    </svg>
  );
}

function IconDoc() {
  return (
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#0b5cad"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 2h9l4 4v16H6z" />
      <path d="M14 2v5h5" />
      <path d="M9 13h6" />
      <path d="M9 17h6" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#188038"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" fill="#188038" fillOpacity="0.12" />
      <path d="M8 12.5l2.5 2.5L16 9.5" />
    </svg>
  );
}

function Spinner() {
  return (
    <svg width="44" height="44" viewBox="0 0 44 44" aria-hidden="true">
      <circle cx="22" cy="22" r="18" fill="none" stroke="#dbe4ec" strokeWidth="6" />
      <circle
        cx="22" cy="22" r="18" fill="none" stroke="#0b5cad" strokeWidth="6"
        strokeLinecap="round" strokeDasharray="80 200"
      >
        <animateTransform
          attributeName="transform" type="rotate"
          from="0 22 22" to="360 22 22" dur="1s" repeatCount="indefinite"
        />
      </circle>
    </svg>
  );
}

export default function CitizenHome() {
  const [mode, setMode] = useState(null); // null | 'paste' | 'speak' | 'upload'
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [stepIdx, setStepIdx] = useState(0);
  const [result, setResult] = useState(null);
  const [reporting, setReporting] = useState(false);
  const [caseResult, setCaseResult] = useState(null);
  const [toast, setToast] = useState('');
  const toastTimerRef = useRef(null);
  const fileInputRef = useRef(null);

  // Rotate honest progress messages while checking (max ~10s enforced by the API helper).
  useEffect(() => {
    if (!loading) return undefined;
    setStepIdx(0);
    const t = window.setInterval(() => {
      setStepIdx((i) => (i + 1) % PROGRESS_STEPS.length);
    }, 2200);
    return () => window.clearInterval(t);
  }, [loading]);

  const showToast = (msg) => {
    setToast(msg);
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToast(''), 5000);
  };

  const runCheck = async (inputText) => {
    const msg = String(inputText !== undefined ? inputText : text).trim();
    if (!msg) {
      showToast('Please paste, speak or upload a message first.');
      return;
    }
    setLoading(true);
    setResult(null);
    setCaseResult(null);
    try {
      const data = await analyzeMessage(msg);
      if (!data || !data.label) throw new Error('The server returned an empty result.');
      setResult({ ...data, message_text: msg });
    } catch (e) {
      const aborted = Boolean(e && (e.name === 'AbortError' || /abort/i.test(String(e.message || ''))));
      showToast(aborted
        ? 'The check took too long (about 10 seconds). Please try again.'
        : 'Could not check the message: ' + String((e && e.message) || e));
    } finally {
      setLoading(false);
    }
  };

  const handleVoiceTranscript = (t) => {
    setText(t);
    runCheck(t);
  };

  const handleUploadChange = (event) => {
    const file = event.target.files && event.target.files[0];
    event.target.value = '';
    if (!file) return;
    const isText = /\.(txt|text|md)$/i.test(file.name) ||
      (file.type && String(file.type).indexOf('text/') === 0);
    if (!isText) {
      showToast('In this PROTOTYPE only plain .txt documents are supported. Please paste the text instead.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const content = String(reader.result || '').trim();
      if (!content) {
        showToast('The file is empty.');
        return;
      }
      setText(content);
      setMode('paste');
      showToast('Document loaded. Press "Check message" to analyze it.');
    };
    reader.onerror = () => showToast('Could not read the file.');
    reader.readAsText(file);
  };

  const handleReport = async () => {
    if (!result) return;
    setReporting(true);
    try {
      const data = await reportScam(result.message_text);
      const id = data && (data.case_id !== undefined ? data.case_id : data.id);
      setCaseResult({ caseId: id === undefined || id === null ? null : id });
    } catch (e) {
      showToast('Could not file the report: ' + String((e && e.message) || e));
    } finally {
      setReporting(false);
    }
  };

  const handleFollowUpAnswer = (answer) => {
    const base = (result && result.message_text) || text;
    runCheck(base + '\n' + answer);
  };

  const resetAll = () => {
    setMode(null);
    setText('');
    setResult(null);
    setCaseResult(null);
  };

  return (
    <div style={S.page}>
      <div style={S.inner}>
        <header style={S.header}>
          {LOGO}
          <div>
            <div style={S.title}>Hifazat</div>
            <div dir="rtl" style={S.subtitle}>حفاظت — جعلی امدادی ادائیگیوں سے بچاؤ</div>
          </div>
        </header>

        <div style={S.banner}>
          PROTOTYPE — all data is mock · یہ نمائشی پروٹوٹائپ ہے، تمام ڈیٹا فرضی ہے
        </div>

        {toast && <div style={S.toast}>{toast}</div>}

        {caseResult ? (
          <div style={S.successBox}>
            <IconCheck />
            <div style={S.successTitle}>Report filed. Shukriya!</div>
            <div dir="rtl" style={S.successUrdu}>شکریہ! آپ کی رپورٹ درج ہو گئی ہے۔</div>
            <div style={S.caseNumber}>
              {caseResult.caseId !== null
                ? 'Your case number is #' + caseResult.caseId + '.'
                : 'Your report has been recorded.'}
            </div>
            <div dir="rtl" style={S.caseUrdu}>
              {caseResult.caseId !== null
                ? 'آپ کا کیس نمبر #' + caseResult.caseId + ' ہے۔'
                : 'آپ کی رپورٹ محفوظ کر لی گئی ہے۔'}
            </div>
            <button type="button" style={S.ghostBtn} onClick={resetAll}>Start over</button>
          </div>
        ) : loading ? (
          <div style={S.loadingBox}>
            <Spinner />
            <div style={S.progressText}>{PROGRESS_STEPS[stepIdx]}</div>
            <div style={S.progressSub}>This usually takes a few seconds (maximum about 10).</div>
          </div>
        ) : result ? (
          <>
            <div style={S.resultWrap}>
              <VerdictCard
                result={result}
                onAnswer={handleFollowUpAnswer}
                onReport={handleReport}
                reporting={reporting}
              />
            </div>
            <button type="button" style={S.ghostBtn} onClick={resetAll}>
              Check another message
            </button>
          </>
        ) : (
          <>
            <div style={S.question}>
              What do you want to check? <span dir="rtl">آپ کیا جانچنا چاہتے ہیں؟</span>
            </div>
            <div style={S.grid}>
              <button type="button" style={S.bigBtn} onClick={() => setMode('paste')}>
                <IconPaste />
                <span>Paste text</span>
                <span dir="rtl" style={S.bigBtnSub}>متن لکھیں</span>
              </button>
              <button type="button" style={S.bigBtn} onClick={() => setMode('speak')}>
                <IconMic />
                <span>Speak</span>
                <span dir="rtl" style={S.bigBtnSub}>بولیں</span>
              </button>
              <button
                type="button"
                style={S.bigBtn}
                onClick={() => {
                  setMode('upload');
                  if (fileInputRef.current) fileInputRef.current.click();
                }}
              >
                <IconDoc />
                <span>Upload document</span>
                <span dir="rtl" style={S.bigBtnSub}>دستاویز</span>
              </button>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.text,.md,text/plain"
              style={{ display: 'none' }}
              onChange={handleUploadChange}
            />

            {mode === 'paste' && (
              <div style={S.panel}>
                <div dir="rtl" style={S.panelUrdu}>
                  اپنا مشکوک پیغام یہاں لکھیں یا پیسٹ کریں۔
                </div>
                <textarea
                  style={S.textarea}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Paste the suspicious SMS / WhatsApp message here…"
                />
                <button type="button" style={S.primaryBtn} onClick={() => runCheck()}>
                  Check message
                </button>
              </div>
            )}

            {mode === 'speak' && (
              <div style={S.panel}>
                <VoiceButton onTranscript={handleVoiceTranscript} disabled={loading} />
              </div>
            )}

            {mode === 'upload' && (
              <div style={S.panel}>
                <div style={S.note}>
                  Only plain <b>.txt</b> documents are supported in this PROTOTYPE.
                  Images and PDFs need server-side OCR (pytesseract) and are not wired
                  to this page yet.
                </div>
                <button
                  type="button"
                  style={S.primaryBtn}
                  onClick={() => { if (fileInputRef.current) fileInputRef.current.click(); }}
                >
                  Choose a .txt file
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
