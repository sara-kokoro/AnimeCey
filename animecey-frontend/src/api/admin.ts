import api from "./axios";

/* ── Stats ─────────────────────────────────────────── */

export async function fetchAdminStats() {
  const res = await api.get("/admin/stats");
  return res.data;
}

/* ── Animes ────────────────────────────────────────── */

export async function adminListAnimes(page = 1, limit = 24) {
  const res = await api.get("/admin/animes", { params: { page, limit } });
  return res.data;
}

export async function adminCreateAnime(data: Record<string, unknown>) {
  const res = await api.post("/admin/animes", data);
  return res.data;
}

export async function adminUpdateAnime(id: number, data: Record<string, unknown>) {
  const res = await api.put(`/admin/animes/${id}`, data);
  return res.data;
}

export async function adminDeleteAnime(id: number) {
  await api.delete(`/admin/animes/${id}`);
}

export async function setFeatured(id: number, featured: boolean) {
  const res = await api.put(`/admin/animes/${id}/featured`, { is_featured: featured });
  return res.data;
}

/* ── Episodes ──────────────────────────────────────── */

export async function adminListEpisodes(params: Record<string, unknown> = {}) {
  const res = await api.get("/admin/episodes", { params });
  return res.data;
}

export async function adminCreateEpisode(data: Record<string, unknown>) {
  const res = await api.post("/admin/episodes", data);
  return res.data;
}

export async function adminUpdateEpisode(id: number, data: Record<string, unknown>) {
  const res = await api.put(`/admin/episodes/${id}`, data);
  return res.data;
}

export async function adminDeleteEpisode(id: number) {
  await api.delete(`/admin/episodes/${id}`);
}

export async function adminRecentUploads() {
  const res = await api.get("/admin/recent-uploads");
  return res.data;
}

/* ── Users ─────────────────────────────────────────── */

export async function adminListUsers(page = 1, limit = 24, search?: string, role?: string) {
  const params: Record<string, unknown> = { page, limit };
  if (search) params.search = search;
  if (role) params.role = role;
  const res = await api.get("/admin/users", { params });
  return res.data;
}

export async function adminSetRole(userId: number, role: string) {
  const res = await api.put(`/admin/users/${userId}/role`, { role });
  return res.data;
}

export async function adminDeleteUser(userId: number) {
  await api.delete(`/admin/users/${userId}`);
}

/* ── Comments ──────────────────────────────────────── */

export async function adminListComments(page = 1, limit = 20, search?: string, animeId?: number) {
  const params: Record<string, unknown> = { page, limit };
  if (search) params.search = search;
  if (animeId) params.anime_id = animeId;
  const res = await api.get("/admin/comments", { params });
  return res.data;
}

export async function adminDeleteComment(id: number) {
  await api.delete(`/admin/comments/${id}`);
}

/* ── Folders ───────────────────────────────────────── */

export async function adminListFolders() {
  const res = await api.get("/admin/folders");
  return res.data;
}

export async function adminCreateFolder(data: Record<string, unknown>) {
  const res = await api.post("/admin/folders", data);
  return res.data;
}

export async function adminDeleteFolder(id: number) {
  await api.delete(`/admin/folders/${id}`);
}

/* ── Broadcasts ────────────────────────────────────── */

export async function adminListBroadcasts() {
  const res = await api.get("/admin/broadcasts");
  return res.data;
}

export async function adminCreateBroadcast(data: Record<string, unknown>) {
  const res = await api.post("/admin/broadcasts", data);
  return res.data;
}

export async function adminDeleteBroadcast(id: number) {
  await api.delete(`/admin/broadcasts/${id}`);
}

/* ── TMDB / AniList (admin only) ───────────────────── */

export async function tmdbSearch(q: string) {
  const res = await api.get("/tmdb/search", { params: { q } });
  return res.data;
}

export async function tmdbDetails(tmdbId: number, type = "tv") {
  const res = await api.get(`/tmdb/details/${tmdbId}`, { params: { type } });
  return res.data;
}

export async function anilistSearch(query: string) {
  const res = await api.post("/anilist/search", { query });
  return res.data;
}

export async function anilistDetails(id: number) {
  const res = await api.get(`/anilist/details/${id}`);
  return res.data;
}
