window.NEDA_API_BASE = window.NEDA_API_BASE || "http://127.0.0.1:8000";

function getApiBase() {
  return window.NEDA_API_BASE || "http://127.0.0.1:8000";
}

async function apiFetch(path, { method = "GET", body = null, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = localStorage.getItem("neda_token");
    if (token) headers["Authorization"] = "Bearer " + token;
  }
  const res = await fetch(getApiBase() + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

async function apiUpload(path, formData) {
  const token = localStorage.getItem("neda_token");
  const res = await fetch(getApiBase() + path, {
    method: "POST",
    headers: token ? { Authorization: "Bearer " + token } : {},
    body: formData,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Upload failed");
  return data;
}
