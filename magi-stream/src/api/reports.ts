import api from "./axios";

export type ReportKind =
  | "not_playable"
  | "missing_episode"
  | "wrong_language"
  | "subtitles"
  | "wrong_content"
  | "wrong_info"
  | "quality"
  | "other";

export interface ReportPayload {
  kind: ReportKind;
  anime_id?: number;
  episode_id?: number;
  message?: string;
  contact?: string;
  page_url?: string;
  /** Champ piège anti-robots : doit rester vide. */
  website?: string;
}

/** Signale un problème (ouvert à tous, inscrit ou non). Les admins reçoivent le signalement via le bot. */
export async function sendReport(payload: ReportPayload): Promise<{ ok: boolean; id?: number }> {
  const res = await api.post("/reports", payload);
  return res.data;
}
