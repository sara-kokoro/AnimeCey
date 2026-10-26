import api from "./axios";

export interface CalendarEntry {
  id: number;
  title: string;
  /** n° de l'animé sur le site (null si pas dans le catalogue) */
  anime_id: number | null;
  poster_url: string | null;
  /** « Saison 2 », « Saison 3 Partie 1 »... */
  season: string;
  episode: number;
  language: "VF" | "VOSTFR";
  /** heure de sortie en UTC (ISO) : à afficher dans l'heure locale du visiteur */
  release_at: string;
  /** l'épisode est déjà en ligne sur le site */
  available: boolean;
}

export interface CalendarWeek {
  /** lundi de la semaine demandée, « AAAA-MM-JJ » */
  week_start: string;
  entries: CalendarEntry[];
}

/** week : 0 = cette semaine, -1 = précédente, 1 = suivante. */
export async function fetchCalendar(week = 0): Promise<CalendarWeek> {
  const { data } = await api.get<CalendarWeek>("/calendar", { params: { week } });
  return data;
}
