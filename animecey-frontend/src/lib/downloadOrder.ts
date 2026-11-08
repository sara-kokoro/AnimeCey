/** Ordre des téléchargements : par animé, puis saison, puis numéro d'épisode. */
export function seasonNumberOf(label: string): number {
  const m = /(\d+)/.exec(label || "");
  return m ? Number(m[1]) : 0;
}

export function compareEpisodes(
  a: { animeId: number; seasonLabel: string; episodeNumber: number },
  b: { animeId: number; seasonLabel: string; episodeNumber: number },
): number {
  return (
    a.animeId - b.animeId ||
    seasonNumberOf(a.seasonLabel) - seasonNumberOf(b.seasonLabel) ||
    a.episodeNumber - b.episodeNumber
  );
}
