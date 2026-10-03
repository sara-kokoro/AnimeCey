import api from "./axios";

export interface CatalogItem {
  id: string;
  title: string;
  title_jp: string | null;
  type: string;
  year: number | null;
  poster_url: string | null;
  is_ongoing: boolean;
}

export interface CatalogPage {
  items: CatalogItem[];
  total: number;
  page: number;
  pages: number;
}

export interface OpenedTitle {
  anime_id: number;
  preparing: boolean;
}

export async function searchCatalog(q: string, page = 1, limit = 24): Promise<CatalogPage> {
  const { data } = await api.get<CatalogPage>("/catalog/search", { params: { q, page, limit } });
  return data;
}

/** Crée l'animé si besoin (détection des saisons côté serveur) et renvoie son id. */
export async function openCatalogTitle(id: string): Promise<OpenedTitle> {
  const { data } = await api.post<OpenedTitle>(`/catalog/${id}/open`, null, { timeout: 90_000 });
  return data;
}

export interface EpisodeServerItem {
  id: number;
  label: string;
  url: string;
  type: string;
}

/** Tous les serveurs de lecture disponibles pour un épisode. */
export async function fetchEpisodeServers(episodeId: number): Promise<EpisodeServerItem[]> {
  const { data } = await api.get<EpisodeServerItem[]>(`/catalog/episodes/${episodeId}/servers`);
  return data;
}

export interface SeasonLabel {
  number: number;
  label: string;
}

/** Noms des saisons / sagas d'un animé (vide pour les animés créés à la main). */
export async function fetchSeasonLabels(animeId: number): Promise<SeasonLabel[]> {
  const { data } = await api.get<SeasonLabel[]>(`/catalog/anime/${animeId}/seasons`);
  return data;
}

/** Demande la préparation d'une saison qui n'a pas encore été récupérée. */
export async function ensureSeason(
  animeId: number,
  language: string,
  season: number,
): Promise<{ preparing: boolean }> {
  const { data } = await api.post<{ preparing: boolean }>(`/catalog/anime/${animeId}/ensure`, null, {
    params: { language, season },
  });
  return data;
}

/** Ancien lien de lecture de l'épisode (sans serveur précis). */
export async function fetchAutoStream(episodeId: number): Promise<{ url: string }> {
  const { data } = await api.get<{ url: string }>(`/episodes/${episodeId}/stream`);
  return data;
}
