import api from "./axios";

export async function fetchWatchlist(status?: string) {
  const res = await api.get("/users/watchlist", { params: status ? { status } : {} });
  return res.data;
}

export async function addToWatchlist(animeId: number, status: string) {
  const res = await api.post("/users/watchlist", { anime_id: animeId, status });
  return res.data;
}

export async function removeFromWatchlist(animeId: number) {
  await api.delete(`/users/watchlist/${animeId}`);
}

export async function fetchFavorites() {
  const res = await api.get("/users/favorites");
  return res.data;
}

export async function addFavorite(animeId: number) {
  const res = await api.post(`/users/favorites/${animeId}`);
  return res.data;
}

export async function removeFavorite(animeId: number) {
  await api.delete(`/users/favorites/${animeId}`);
}

export async function fetchHistory() {
  const res = await api.get("/users/history");
  return res.data;
}

export async function updateHistory(episodeId: number, progressSeconds: number) {
  const res = await api.post("/users/history", { episode_id: episodeId, progress_seconds: progressSeconds });
  return res.data;
}

export async function fetchContinueWatching() {
  const res = await api.get("/users/continue-watching");
  return res.data;
}
