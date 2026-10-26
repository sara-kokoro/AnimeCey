import api from "./axios";
import type { Anime } from "@/types";

export interface PaginatedAnimes {
  items: Anime[];
  total: number;
  page: number;
  pages: number;
}

export interface AnimeFilters {
  page?: number;
  limit?: number;
  sort?: string;
  type?: string;
  status?: string;
  genre?: string;
  language?: string;
  year?: number;
  q?: string;
  category?: string;
}

export async function fetchAnimes(filters: AnimeFilters = {}): Promise<PaginatedAnimes> {
  const params = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== undefined && v !== null && v !== "" && v !== "all"),
  );
  const res = await api.get("/animes", { params });
  return res.data;
}

export async function fetchAnime(id: number): Promise<Anime> {
  const res = await api.get(`/animes/${id}`);
  return res.data;
}

export async function fetchFeatured(): Promise<Anime[]> {
  const res = await api.get("/animes/featured");
  return res.data;
}

export async function fetchTopWeek(): Promise<Anime[]> {
  const res = await api.get("/animes/top-week");
  return res.data;
}

export async function fetchTopRated(): Promise<Anime[]> {
  const res = await api.get("/animes/top-rated");
  return res.data;
}

export async function fetchLatest(): Promise<Anime[]> {
  const res = await api.get("/animes/latest");
  return res.data;
}

export interface LiveHomeData {
  featured: Anime[];
  top_week: Anime[];
  new_releases: Anime[];
  top_rated: Anime[];
  latest: Anime[];
  films: Anime[];
  series: Anime[];
  genres: { genre: string; items: Anime[] }[];
}

export async function fetchLiveHome(): Promise<LiveHomeData> {
  const res = await api.get("/animes/live-home");
  return res.data;
}

export async function fetchTrending(): Promise<Anime[]> {
  const res = await api.get("/animes/trending");
  return res.data;
}
