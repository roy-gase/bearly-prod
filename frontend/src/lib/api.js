/**
 * API client.
 *
 * Holds the access token in memory and the refresh token in localStorage, and
 * transparently refreshes an expired session once before giving up. No API
 * credentials for the model provider ever reach this layer — the browser only
 * ever talks to Bearly's own backend.
 */
const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
const PREFIX = `${BASE}/api/v1`;
const REFRESH_KEY = "bearly.refresh";

let accessToken = null;
let onUnauthorized = () => {};
let refreshInFlight = null;

export function setAccessToken(token) {
  accessToken = token;
}

/** The current access token, for transports that cannot use `request()` (the SSE chat stream). */
export function getAccessToken() {
  return accessToken;
}

/** Force a refresh and return the new token, or null. Used on a 401 mid-stream. */
export async function refreshAccessToken() {
  return (await refreshSession()) ? accessToken : null;
}

export function getRefreshToken() {
  try {
    return localStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}

export function setRefreshToken(token) {
  try {
    if (token) localStorage.setItem(REFRESH_KEY, token);
    else localStorage.removeItem(REFRESH_KEY);
  } catch {
    /* private browsing — the session simply will not survive a reload */
  }
}

export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

export class ApiError extends Error {
  constructor(message, status, fieldErrors = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

async function parseError(response) {
  let detail = `Request failed (${response.status})`;
  let fieldErrors = [];
  try {
    const body = await response.json();
    if (typeof body.detail === "string") detail = body.detail;
    if (Array.isArray(body.errors)) {
      fieldErrors = body.errors;
      if (body.errors.length) detail = body.detail ?? "Some fields need attention";
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(detail, response.status, fieldErrors);
}

async function refreshSession() {
  const token = getRefreshToken();
  if (!token) return false;

  // Collapse concurrent 401s into a single refresh.
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${PREFIX}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: token }),
        });
        if (!response.ok) return false;
        const body = await response.json();
        accessToken = body.access_token;
        setRefreshToken(body.refresh_token);
        return true;
      } catch {
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

async function request(method, path, { body, params, retry = true } = {}) {
  const url = new URL(`${PREFIX}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    });
  }

  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (response.status === 401 && retry && getRefreshToken()) {
    if (await refreshSession()) {
      return request(method, path, { body, params, retry: false });
    }
    setRefreshToken(null);
    accessToken = null;
    onUnauthorized();
  }

  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  get: (path, params) => request("GET", path, { params }),
  post: (path, body) => request("POST", path, { body }),
  put: (path, body) => request("PUT", path, { body }),
  patch: (path, body) => request("PATCH", path, { body }),
  delete: (path) => request("DELETE", path),
};
