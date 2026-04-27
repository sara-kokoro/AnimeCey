import type { Anime, Episode } from "@/types";
import banner1 from "@/assets/banner-1.jpg";
import banner2 from "@/assets/banner-2.jpg";
import banner3 from "@/assets/banner-3.jpg";
import banner4 from "@/assets/banner-4.jpg";

const banners = [banner1, banner2, banner3, banner4];

const titles = [
  { t: "Lame de l'Aube Écarlate", jp: "Akatsuki no Yaiba", g: ["Action", "Aventure", "Surnaturel"] },
  { t: "Pilote du Ciel d'Acier", jp: "Hagane no Sora", g: ["Mecha", "Sci-Fi", "Drame"] },
  { t: "Les Murmures de la Forêt", jp: "Mori no Sasayaki", g: ["Fantasy", "Magie", "Aventure"] },
  { t: "Lames Jumelles", jp: "Sōken no Hito", g: ["Action", "Mystère", "Thriller"] },
  { t: "Coeur de Tempête", jp: "Arashi no Kokoro", g: ["Romance", "Drame", "Slice of Life"] },
  { t: "Chroniques d'Aetherion", jp: "Aetherion Senki", g: ["Fantasy", "Aventure", "Magie"] },
  { t: "Protocole Onyx", jp: "Onyx Purotokoru", g: ["Sci-Fi", "Action", "Cyberpunk"] },
  { t: "L'Appel du Vide", jp: "Kūkyo no Yobikoe", g: ["Horreur", "Mystère", "Psychologique"] },
  { t: "Académie Lunaire", jp: "Tsuki no Gakuen", g: ["École", "Comédie", "Magie"] },
  { t: "Le Festin des Dragons", jp: "Ryū no Utage", g: ["Fantasy", "Action", "Aventure"] },
  { t: "Néo Tokyo 2099", jp: "Neo Tōkyō 2099", g: ["Cyberpunk", "Action", "Sci-Fi"] },
  { t: "Sentinelle d'Émeraude", jp: "Emerarudo no Mamori", g: ["Action", "Magie", "Drame"] },
];

const synopsis =
  "Dans un monde où l'équilibre vacille, un jeune héros doit affronter les ténèbres qui menacent de tout engloutir. Entre alliances fragiles, secrets enfouis et combats épiques, une légende est sur le point de naître.";

export const animes: Anime[] = titles.map((x, i) => ({
  id: i + 1,
  title: x.t,
  title_jp: x.jp,
  type: i % 5 === 0 ? "film" : "serie",
  status: i % 3 === 0 ? "ongoing" : i % 3 === 1 ? "completed" : "upcoming",
  synopsis,
  poster_url: banners[i % banners.length],
  banner_url: banners[i % banners.length],
  genres: x.g,
  score: +(7 + Math.random() * 2.5).toFixed(1),
  year: 2020 + (i % 6),
  trailer_url: "https://www.youtube.com/embed/dQw4w9WgXcQ",
  languages_available: i % 4 === 0 ? ["VOSTFR"] : i % 4 === 1 ? ["VF"] : ["VF", "VOSTFR"],
  seasons_count: i % 5 === 0 ? 1 : (i % 3) + 1,
  episodes_count: i % 5 === 0 ? 1 : 12 + (i % 14),
}));

export const featuredAnimes = animes.slice(0, 5);

export const allGenres = Array.from(new Set(animes.flatMap((a) => a.genres))).sort();
export const allYears = Array.from(new Set(animes.map((a) => a.year))).sort((a, b) => b - a);

export interface CatalogFilters {
  query?: string;
  genres?: string[];
  type?: "all" | "serie" | "film";
  language?: "all" | "VF" | "VOSTFR" | "BOTH";
  status?: "all" | "ongoing" | "completed" | "upcoming";
  year?: number | "all";
  sort?: "az" | "za" | "score" | "recent";
}

export function filterAnimes(filters: CatalogFilters): Anime[] {
  let res = [...animes];
  if (filters.query) {
    const q = filters.query.toLowerCase();
    res = res.filter(
      (a) => a.title.toLowerCase().includes(q) || a.title_jp?.toLowerCase().includes(q),
    );
  }
  if (filters.genres && filters.genres.length > 0) {
    res = res.filter((a) => filters.genres!.every((g) => a.genres.includes(g)));
  }
  if (filters.type && filters.type !== "all") {
    res = res.filter((a) => a.type === filters.type);
  }
  if (filters.language && filters.language !== "all") {
    if (filters.language === "BOTH") {
      res = res.filter((a) => a.languages_available.length === 2);
    } else {
      res = res.filter((a) => a.languages_available.includes(filters.language as "VF" | "VOSTFR"));
    }
  }
  if (filters.status && filters.status !== "all") {
    res = res.filter((a) => a.status === filters.status);
  }
  if (filters.year && filters.year !== "all") {
    res = res.filter((a) => a.year === filters.year);
  }
  switch (filters.sort) {
    case "za":
      res.sort((a, b) => b.title.localeCompare(a.title));
      break;
    case "score":
      res.sort((a, b) => b.score - a.score);
      break;
    case "recent":
      res.sort((a, b) => b.year - a.year);
      break;
    case "az":
    default:
      res.sort((a, b) => a.title.localeCompare(b.title));
  }
  return res;
}

export function getAnimeById(id: number): Anime | undefined {
  return animes.find((a) => a.id === id);
}

export function getEpisodes(animeId: number, language: "VF" | "VOSTFR", season: number): Episode[] {
  const anime = getAnimeById(animeId);
  if (!anime) return [];
  if (!anime.languages_available.includes(language)) return [];
  const count = anime.type === "film" ? 1 : 12;
  return Array.from({ length: count }).map((_, i) => ({
    id: animeId * 1000 + season * 100 + i + 1,
    anime_id: animeId,
    episode_number: i + 1,
    title: anime.type === "film" ? anime.title : `L'épreuve du ${["feu","vent","sang","silence","destin","crépuscule","oubli","éveil","miroir","vide","serment","retour"][i]}`,
    thumbnail_url: anime.banner_url,
    duration: 24 * 60,
    language,
    season_number: season,
    servcey1_available: true,
    servcey2_available: i % 3 !== 0,
    likes_count: Math.floor(Math.random() * 800) + 50,
    comments_count: Math.floor(Math.random() * 60) + 2,
    air_date: new Date(2024, 0, i + 1).toISOString(),
  }));
}

export function getEpisodeById(id: number) {
  for (const anime of animes) {
    for (const lang of anime.languages_available) {
      for (let s = 1; s <= anime.seasons_count; s++) {
        const eps = getEpisodes(anime.id, lang, s);
        const found = eps.find((e) => e.id === id);
        if (found) return { episode: found, anime, allEpisodes: eps };
      }
    }
  }
  return null;
}

// ===== Mock notifications, comments, broadcasts, users =====

export interface MockNotification {
  id: number;
  title: string;
  content: string;
  image_url?: string;
  caption?: string;
  type: "info" | "new" | "alert" | "maintenance";
  created_at: string;
  is_read: boolean;
}

export const mockNotifications: MockNotification[] = [
  {
    id: 1,
    title: "Nouveaux épisodes disponibles",
    content:
      "Les épisodes 12 à 15 de Lame de l'Aube Écarlate sont désormais disponibles en VOSTFR. Bon visionnage !",
    type: "new",
    image_url: banner1,
    caption: "Saison 2 — bientôt complète",
    created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    is_read: false,
  },
  {
    id: 2,
    title: "Maintenance planifiée",
    content:
      "Le service sera momentanément indisponible cette nuit entre 02h et 04h pour des opérations techniques.",
    type: "maintenance",
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString(),
    is_read: false,
  },
  {
    id: 3,
    title: "Bienvenue sur AnimeCey",
    content:
      "Découvre des centaines d'animés en VF et VOSTFR, gère ta watchlist et reçois des alertes pour les nouveaux épisodes.",
    type: "info",
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
    is_read: true,
  },
  {
    id: 4,
    title: "Une faille a été corrigée",
    content: "Le lecteur ServCey 2 fonctionne à nouveau correctement sur mobile.",
    type: "alert",
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(),
    is_read: true,
  },
];

export interface MockComment {
  id: number;
  episode_id: number;
  user: { id: number; username: string };
  content: string;
  likes_count: number;
  is_liked_by_me: boolean;
  parent_id?: number;
  replies?: MockComment[];
  created_at: string;
}

const usernames = ["Akira", "Yumi", "Ren", "Sora", "Kaito", "Hina", "Taro", "Mei", "Hiro", "Nana"];
const sampleComments = [
  "Cet épisode est juste incroyable, l'animation est sublime !",
  "La bande-son colle parfaitement à l'intensité de la scène finale.",
  "Je n'avais pas vu venir ce twist, chapeau aux scénaristes.",
  "Le character design des nouveaux personnages est vraiment soigné.",
  "Vivement la suite, le cliffhanger est cruel.",
  "Petit hommage discret au manga original que j'ai adoré.",
  "Le doublage VF est de très bonne qualité cette saison.",
  "Les combats prennent vraiment une nouvelle dimension.",
];

export function getComments(episodeId: number): MockComment[] {
  const seed = episodeId % 8;
  const list: MockComment[] = [];
  for (let i = 0; i < 6; i++) {
    const id = episodeId * 100 + i;
    const c: MockComment = {
      id,
      episode_id: episodeId,
      user: { id: i + 1, username: usernames[(seed + i) % usernames.length] },
      content: sampleComments[(seed + i) % sampleComments.length],
      likes_count: Math.floor(Math.random() * 40),
      is_liked_by_me: false,
      created_at: new Date(Date.now() - 1000 * 60 * 60 * (i + 1)).toISOString(),
      replies:
        i % 2 === 0
          ? [
              {
                id: id * 10,
                episode_id: episodeId,
                user: { id: 99, username: usernames[(seed + i + 3) % usernames.length] },
                content: "Tellement d'accord avec toi !",
                likes_count: Math.floor(Math.random() * 12),
                is_liked_by_me: false,
                parent_id: id,
                created_at: new Date(Date.now() - 1000 * 60 * 30 * (i + 1)).toISOString(),
              },
            ]
          : [],
    };
    list.push(c);
  }
  return list;
}

export interface MockUser {
  id: number;
  username: string;
  email: string;
  role: "user" | "admin";
  created_at: string;
}

export const mockUsers: MockUser[] = Array.from({ length: 24 }).map((_, i) => ({
  id: i + 1,
  username: usernames[i % usernames.length] + (i + 1),
  email: `user${i + 1}@animecey.app`,
  role: i === 0 ? "admin" : "user",
  created_at: new Date(2024, i % 12, (i % 27) + 1).toISOString(),
}));

export interface MockBroadcast {
  id: number;
  title: string;
  content: string;
  type: "info" | "new" | "alert" | "maintenance";
  target: "all" | "users";
  created_at: string;
  reads_count: number;
}

export const mockBroadcasts: MockBroadcast[] = mockNotifications.map((n, i) => ({
  id: n.id,
  title: n.title,
  content: n.content,
  type: n.type,
  target: i % 2 === 0 ? "all" : "users",
  created_at: n.created_at,
  reads_count: Math.floor(Math.random() * 1500) + 100,
}));

export interface MockFolder {
  id: number;
  name: string;
  type: "anime" | "language" | "season";
  episodes_count: number;
  children?: MockFolder[];
}

export const mockFolders: MockFolder[] = animes.slice(0, 6).map((a, idx) => ({
  id: 1000 + idx,
  name: a.title,
  type: "anime",
  episodes_count: a.episodes_count,
  children: a.languages_available.map((lang, li) => ({
    id: 2000 + idx * 10 + li,
    name: lang,
    type: "language",
    episodes_count: a.episodes_count,
    children: Array.from({ length: a.seasons_count }).map((_, si) => ({
      id: 3000 + idx * 100 + li * 10 + si,
      name: `Saison ${si + 1}`,
      type: "season",
      episodes_count: a.type === "film" ? 1 : 12,
    })),
  })),
}));

export const mockRecentUploads = animes.slice(0, 8).map((a, i) => ({
  id: i + 1,
  anime_title: a.title,
  episode_label: `Épisode ${(i % 12) + 1}`,
  language: a.languages_available[0],
  thumbnail: a.banner_url,
  uploaded_at: new Date(Date.now() - 1000 * 60 * 60 * (i + 1)).toISOString(),
}));