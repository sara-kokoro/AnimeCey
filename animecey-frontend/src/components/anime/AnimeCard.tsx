import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Play, Star } from "lucide-react";
import { Badge2 } from "@/components/ui/Badge2";
import type { Anime } from "@/types";

interface Props {
  anime: Anime;
  index?: number;
  fullWidth?: boolean;
}

export function AnimeCard({ anime, index = 0, fullWidth = false }: Props) {
  const langLabel =
    anime.languages_available.length === 2
      ? "VF & VOSTFR"
      : anime.languages_available[0];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.4, delay: Math.min(index * 0.05, 0.4) }}
      className={fullWidth ? "w-full" : "shrink-0 w-[150px] md:w-[180px]"}
    >
      <Link
        to={`/anime/${anime.id}`}
        className="group block focus:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-xl"
      >
        <div className="relative aspect-[2/3] overflow-hidden rounded-xl bg-surface shadow-[var(--shadow-card)] transition-all duration-200 group-hover:scale-[1.03] group-hover:shadow-[var(--shadow-glow)]">
          <img
            src={anime.poster_url}
            alt={anime.title}
            loading="lazy"
            className="absolute inset-0 w-full h-full object-cover"
          />

          {/* Bottom gradient */}
          <div
            className="absolute inset-0"
            style={{ background: "var(--gradient-card)" }}
          />

          {/* Language badge */}
          <div className="absolute top-2 right-2">
            <span className="bg-primary text-primary-foreground text-[10px] font-semibold font-body px-2 py-0.5 rounded-md">
              {langLabel}
            </span>
          </div>

          {/* Hover overlay with play */}
          <div className="absolute inset-0 bg-black/55 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center">
            <motion.div
              initial={{ scale: 0.8 }}
              whileHover={{ scale: 1 }}
              className="w-14 h-14 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-[var(--shadow-glow)]"
            >
              <Play className="w-6 h-6 fill-current ml-0.5" />
            </motion.div>
          </div>

          {/* Score */}
          <div className="absolute bottom-2 left-2 flex items-center gap-1 text-white">
            <Star className="w-3 h-3 fill-primary text-primary" />
            <span className="text-xs font-medium font-body">{anime.score}</span>
          </div>
        </div>

        <h3 className="mt-2 text-[13px] font-display font-semibold text-foreground line-clamp-2 leading-tight">
          {anime.title}
        </h3>
        <p className="text-[11px] text-muted-foreground mt-0.5 font-body">
          {anime.year} • {anime.type === "film" ? "Film" : "Série"}
        </p>
      </Link>
    </motion.div>
  );
}

export default AnimeCard;
