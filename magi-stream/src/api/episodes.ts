import api from "./axios";
import type { Episode } from "@/types";

export async function fetchEpisodes(
  animeId: number,
  language: string,
  season: number,
): Promise<Episode[]> {
  const res = await api.get("/episodes", { params: { anime_id: animeId, language, season } });
  return res.data;
}

export async function fetchEpisode(id: number): Promise<Episode> {
  const res = await api.get(`/episodes/${id}`);
  return res.data;
}

export async function getStreamUrl(
  episodeId: number,
  server: "servcey1" | "servcey2",
): Promise<{ url: string; type?: string }> {
  const res = await api.get(`/episodes/${episodeId}/stream`, { params: { server } });
  return res.data;
}

export async function fetchLikeStatus(id: number) {
  const res = await api.get(`/episodes/${id}/like`);
  return res.data as { liked: boolean; likes_count: number };
}

export async function likeEpisode(id: number) {
  const res = await api.post(`/episodes/${id}/like`);
  return res.data as { liked: boolean; likes_count: number };
}

export async function unlikeEpisode(id: number) {
  const res = await api.delete(`/episodes/${id}/like`);
  return res.data as { liked: boolean; likes_count: number };
}

export interface DownloadInfo {
  downloadable: boolean;
  daily_limit: number;
  remaining: number | null; // null si l'utilisateur n'est pas connecté
  wait_seconds: number;
}

export async function fetchDownloadInfo(id: number): Promise<DownloadInfo> {
  const res = await api.get(`/episodes/${id}/download-info`);
  return res.data;
}

export async function requestDownloadTicket(
  id: number,
): Promise<{ ticket: string; wait_seconds: number; remaining: number }> {
  const res = await api.post(`/episodes/${id}/download-ticket`);
  return res.data;
}

/** Adresse du fichier : le ticket remplace l'en-tête d'authentification (un simple lien ne peut pas en porter). */
export function downloadFileUrl(id: number, ticket: string): string {
  return `${api.defaults.baseURL}/episodes/${id}/download?ticket=${encodeURIComponent(ticket)}`;
}
