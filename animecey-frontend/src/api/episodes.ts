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
): Promise<{ url: string }> {
  const res = await api.get(`/episodes/${episodeId}/stream`, { params: { server } });
  return res.data;
}

export async function likeEpisode(id: number) {
  const res = await api.post(`/episodes/${id}/like`);
  return res.data as { liked: boolean; likes_count: number };
}

export async function unlikeEpisode(id: number) {
  const res = await api.delete(`/episodes/${id}/like`);
  return res.data as { liked: boolean; likes_count: number };
}
