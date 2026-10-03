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
