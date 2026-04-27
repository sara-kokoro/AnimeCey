import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL ?? "https://modern-anteater-vianney-98712cbe.koyeb.app/api";

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
    }
    return Promise.reject(err);
  },
);

export default api;

/** Extract a displayable error message from an Axios error (handles FastAPI detail string | array). */
export function getApiError(err: unknown, fallback = "Erreur inconnue"): string {
  const axErr = err as { response?: { data?: { detail?: unknown } } };
  const detail = axErr?.response?.data?.detail;
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((d: Record<string, unknown>) => String(d.msg ?? d.message ?? "")).filter(Boolean);
    return msgs.length > 0 ? msgs.join(", ") : fallback;
  }
  return fallback;
}
