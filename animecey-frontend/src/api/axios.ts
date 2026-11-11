import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL ?? "https://yumeflowerbot.apps.mistral.run/api";

/** Serveur de secours : utilisé automatiquement si le principal ne répond pas (panne, plus de crédit…). */
const FALLBACK_BASE: string = (import.meta.env.VITE_API_FALLBACK_URL as string | undefined) ?? "https://yumeflowerbot.koyeb.app/api";
let fallbackUntil = 0; // tant que Date.now() < fallbackUntil, on parle directement au serveur de secours
const FALLBACK_MS = 2 * 60_000; // puis on réessaie le serveur principal

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  if (FALLBACK_BASE && FALLBACK_BASE !== API_BASE && Date.now() < fallbackUntil) config.baseURL = FALLBACK_BASE;
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    // Principal en panne (pas de réponse, ou 502/503/504/530) : on rejoue la requête de lecture sur le secours.
    const cfg = err.config as (typeof err.config & { _fb?: boolean }) | undefined;
    const status: number | undefined = err.response?.status;
    const down = !err.response || (status !== undefined && [502, 503, 504, 530].includes(status));
    if (cfg && down && !cfg._fb && FALLBACK_BASE && FALLBACK_BASE !== API_BASE && cfg.baseURL !== FALLBACK_BASE) {
      const method = String(cfg.method ?? "get").toLowerCase();
      if (method === "get" || method === "head") {
        cfg._fb = true;
        cfg.baseURL = FALLBACK_BASE;
        try {
          const res = await api.request(cfg);
          fallbackUntil = Date.now() + FALLBACK_MS;
          return res;
        } catch (e) {
          return Promise.reject(e);
        }
      }
    }
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
