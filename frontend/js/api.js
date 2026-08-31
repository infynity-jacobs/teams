const API_BASE = "/api";

const Auth = {
  getToken() { return localStorage.getItem("token"); },
  getUser() {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  },
  setSession(token, user) {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  },
  isLoggedIn() { return !!this.getToken(); },
  hasAnyRole(roles) {
    const u = this.getUser();
    return u && roles.includes(u.role);
  },
};

class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function apiFetch(path, { method = "GET", body = null, isForm = false, rawResponse = false } = {}) {
  const headers = {};
  const token = Auth.getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let payload = body;
  if (body && !isForm) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const resp = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });

  if (resp.status === 401) {
    Auth.clear();
    location.hash = "#/login";
    throw new ApiError(401, "Session expired, please log in again");
  }

  if (rawResponse) return resp;

  const contentType = resp.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await resp.json().catch(() => ({})) : await resp.text();

  if (!resp.ok) {
    throw new ApiError(resp.status, (data && data.detail) || data || "Request failed");
  }
  return data;
}

async function apiLogin(username, password) {
  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);
  const resp = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new ApiError(resp.status, data.detail || "Login failed");
  return data;
}

async function apiDownload(path, filename) {
  const resp = await apiFetch(path, { rawResponse: true });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new ApiError(resp.status, data.detail || "Export failed");
  }
  const blob = await resp.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
