export type Language = "VF" | "VOSTFR";

export interface Anime {
  id: number;
  title: string;
  title_jp?: string;
  type: "serie" | "film";
  status: "ongoing" | "completed" | "upcoming";
  synopsis: string;
  poster_url: string;
  banner_url?: string;
  genres: string[];
  score: number;
  year: number;
  trailer_url?: string;
  languages_available: Language[];
  seasons_count: number;
  episodes_count: number;
}

export interface Episode {
  id: number;
  anime_id: number;
  episode_number: number;
  title?: string;
  thumbnail_url?: string;
  duration?: number;
  language: Language;
  season_number: number;
  servcey1_available: boolean;
  servcey2_available: boolean;
  likes_count: number;
  comments_count: number;
  air_date?: string;
}