import { motion } from "framer-motion";
import { SearchX } from "lucide-react";
import type { Anime } from "@/types";
import { AnimeCard } from "./AnimeCard";

interface Props {
  animes: Anime[];
  emptyMessage?: string;
  emptyHint?: string;
}

export function AnimeGrid({ animes, emptyMessage = "Aucun résultat", emptyHint }: Props) {
  if (animes.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex flex-col items-center justify-center py-20 text-center"
      >
        <div className="w-16 h-16 rounded-full bg-surface flex items-center justify-center mb-4">
          <SearchX className="w-7 h-7 text-muted-foreground" />
        </div>
        <p className="font-display font-semibold text-lg text-foreground">{emptyMessage}</p>
        {emptyHint && (
          <p className="text-sm text-muted-foreground font-body mt-1 max-w-sm">{emptyHint}</p>
        )}
      </motion.div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 md:gap-5">
      {animes.map((anime, i) => (
        <AnimeCard key={anime.id} anime={anime} index={i} fullWidth />
      ))}
    </div>
  );
}