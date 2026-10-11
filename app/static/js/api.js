// Centralized Fetch API client with automatic CSRF header handling
let cachedCsrfToken = "";

export async function getCsrfToken() {
  if (cachedCsrfToken) return cachedCsrfToken;
  try {
    const res = await fetch("/api/csrf-token");
    const json = await res.json();
    if (json.ok && json.csrf_token) {
      cachedCsrfToken = json.csrf_token;
      return cachedCsrfToken;
    }
  } catch (e) {
    console.warn("Could not fetch CSRF token:", e);
  }
  return "";
}

export async function apiRequest(url, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = {
    "Accept": "application/json",
    ...(options.headers || {})
  };

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrf = await getCsrfToken();
    if (csrf) {
      headers["X-CSRFToken"] = csrf;
    }
    if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(options.body);
    }
  }

  const response = await fetch(url, {
    ...options,
    headers
  });

  const contentType = response.headers.get("content-type") || "";
  let data;
  if (contentType.includes("application/json")) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const errMessage = (data && data.error && data.error.message) || `Request failed (${response.status})`;
    const error = new Error(errMessage);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}
