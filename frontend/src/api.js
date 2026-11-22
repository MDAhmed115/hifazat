// frontend/src/api.js
// Single shared fetch helper for the whole app.
//
// Usage:
//   import { api } from "./api.js";
//   const res = await api("/api/auth/login", "POST", { phone, password });
//   if (res.error === "network") { ... }
//   if (res.status === 200) { res.data.token ... }
//
// Return shape (always an object):
//   { status, ok, data }  on any HTTP response (data = parsed JSON or null)
//   { error: "network" }  only when the request could not reach the server,
//                         even after 1 automatic retry (2s delay).

// CHANGE THIS ONE CONSTANT to point at a different backend.
export const BASE_URL = "http://localhost:8000";

// Sent with every request; backend must accept this header value.
const API_KEY = "hifazat-prototype-key";

// localStorage keys
export const TOKEN_KEY = "hifazat_token";
export const ROLE_KEY = "hifazat_role";
export const NAME_KEY = "hifazat_name";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRole() {
  return localStorage.getItem(ROLE_KEY);
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(NAME_KEY);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function requestOnce(path, method, body) {
  const headers = { "X-API-Key": API_KEY };
  const token = getToken();
  if (token) {
    headers["Authorization"] = "Bearer " + token;
  }
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(BASE_URL + path, {
    method: method,
    headers: headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null; // empty body or non-JSON response
  }
  return { status: res.status, ok: res.ok, data };
}

export async function api(path, method = "GET", body = undefined, isRetry = false) {
  let res;
  try {
    res = await requestOnce(path, method, body);
  } catch {
    // Network error: retry once after 2 seconds, then give up.
    if (!isRetry) {
      await sleep(2000);
      return api(path, method, body, true);
    }
    return { error: "network" };
  }

  // 401 means the token is missing, expired or invalid: drop it so the
  // RoleGuard sends the user back to /login on the next navigation.
  if (res.status === 401 && getToken()) {
    clearAuth();
  }

  return res;
}
