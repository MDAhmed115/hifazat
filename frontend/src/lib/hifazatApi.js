// frontend/src/lib/hifazatApi.js
const BASE =
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL) ||
  'http://localhost:8000';

// If your Login page stores the JWT under a different key, add that key here.
const TOKEN_KEYS = ['token', 'hifazat_token', 'auth_token', 'access_token', 'jwt'];
const LITE_KEY = 'hifazat_lite';
const QUEUE_KEY = 'hifazat_offline_queue';
const SLOW_MS = 3000;

function getToken() {
  for (let i = 0; i < TOKEN_KEYS.length; i += 1) {
    try {
      const v = window.localStorage.getItem(TOKEN_KEYS[i]) || window.sessionStorage.getItem(TOKEN_KEYS[i]);
      if (v) return v;
    } catch (e) { /* storage blocked, continue */ }
  }
  return null;
}

// ---------------- Lite mode ----------------
export function isLiteMode() {
  try { return window.localStorage.getItem(LITE_KEY) === '1'; } catch (e) { return false; }
}

export function setLiteMode(on) {
  try { window.localStorage.setItem(LITE_KEY, on ? '1' : '0'); } catch (e) { /* ignore */ }
  try { window.dispatchEvent(new Event('hifazat_lite_change')); } catch (e) { /* ignore */ }
}

// ---------------- Offline queue (exactly-once, uuid idempotency key) ----------------
function uuid() {
  try {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
  } catch (e) { /* ignore */ }
  return 'id-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
}

function readQueue() {
  try {
    const raw = window.localStorage.getItem(QUEUE_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr : [];
  } catch (e) { return []; }
}

function writeQueue(queue) {
  try { window.localStorage.setItem(QUEUE_KEY, JSON.stringify(queue)); } catch (e) { /* ignore */ }
  try { window.dispatchEvent(new Event('hifazat_queue_change')); } catch (e) { /* ignore */ }
}

export function getPendingCount() { return readQueue().length; }

function enqueue(path, body) {
  const item = { id: uuid(), path, body, queued_at: new Date().toISOString() };
  const q = readQueue();
  q.push(item);
  writeQueue(q);
  return item;
}

let flushing = false;

// Sends queue items head-of-line; an item is removed ONLY after a
// successful response => each item is delivered exactly once.
export async function flushQueue() {
  if (flushing || typeof navigator === 'undefined' || navigator.onLine === false) return 0;
  flushing = true;
  let sent = 0;
  try {
    for (;;) {
      const q = readQueue();
      if (!q.length) break;
      const item = q[0];
      try {
        await callApi(item.path, { method: 'POST', body: item.body, idempotencyKey: item.id });
        sent += 1;
        writeQueue(readQueue().filter((x) => x.id !== item.id));
      } catch (e) {
        break; // still offline, or server rejected: stop and retry later
      }
    }
  } finally {
    flushing = false;
  }
  return sent;
}

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => { flushQueue(); });
  window.setInterval(() => { flushQueue(); }, 30000);
}

// ---------------- Core request helper ----------------
export async function callApi(path, { method = 'GET', body = undefined, timeoutMs = 15000, idempotencyKey = undefined } = {}) {
  const startedAt = Date.now();
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    let fullPath = path;
    if (isLiteMode()) fullPath += (fullPath.indexOf('?') === -1 ? '?' : '&') + 'lite=1';
    const headers = { 'Content-Type': 'application/json' };
    const token = getToken();
    if (token) headers.Authorization = 'Bearer ' + token;
    if (idempotencyKey) headers['X-Idempotency-Key'] = idempotencyKey;
    let payload = body;
    if (payload !== undefined && idempotencyKey && typeof payload === 'object' && !Array.isArray(payload)) {
      payload = { ...payload, idempotency_key: idempotencyKey };
    }
    const res = await fetch(BASE + fullPath, {
      method,
      headers,
      body: payload === undefined ? undefined : JSON.stringify(payload),
      signal: controller.signal,
    });
    let data = null;
    try { data = await res.json(); } catch (e) { data = null; }
    if (!res.ok) {
      const d = data && (data.detail !== undefined ? data.detail : data.message);
      throw new Error(typeof d === 'string' ? d : 'Request failed (HTTP ' + res.status + ')');
    }
    return data;
  } finally {
    window.clearTimeout(timer);
    const took = Date.now() - startedAt;
    if (took > SLOW_MS) {
      try { window.dispatchEvent(new CustomEvent('hifazat_slow', { detail: { ms: took, path } })); } catch (e) { /* ignore */ }
    }
  }
}

// POST that falls back to the offline queue when offline or on a network error.
async function postOrQueue(path, body) {
  const offline = typeof navigator !== 'undefined' && navigator.onLine === false;
  if (offline) {
    const item = enqueue(path, body);
    return { queued: true, queue_id: item.id, pending: getPendingCount() };
  }
  try {
    return await callApi(path, { method: 'POST', body });
  } catch (e) {
    const name = String((e && e.name) || '');
    const msg = String((e && e.message) || '');
    const networkish = name === 'TypeError' || /failed to fetch|networkerror|network request|load failed/i.test(msg);
    if (networkish) {
      const item = enqueue(path, body);
      return { queued: true, queue_id: item.id, pending: getPendingCount() };
    }
    throw e;
  }
}

// POST /api/analyze {message_text} -> {label, confidence, route, explanation_user, case_id?}
// When offline, returns {queued: true, pending: N} and the item is sent automatically later.
export function analyzeMessage(messageText) {
  return postOrQueue('/api/analyze', { message_text: messageText });
}

// POST /api/cases {type:"scam_report", message_text} -> also queued when offline.
export function reportScam(messageText) {
  return postOrQueue('/api/cases', { type: 'scam_report', message_text: messageText });
}

// Generic GET used by every dashboard page.
export function getJson(path, timeoutMs = 15000) {
  return callApi(path, { method: 'GET', timeoutMs });
}
