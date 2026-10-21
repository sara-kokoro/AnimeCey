import { useState } from "react";
import { Link } from "@/lib/router";
import { Play, Star } from "lucide-react";
import type { Anime } from "@/types";

interface Props {
  anime: Anime;
  index?: number;
  fullWidth?: boolean;
  /** Mettre true pour les premières cartes visibles (chargement immédiat de l'image). */
  priority?: boolean;
}

/** Force https (les images http sont bloquées sur mobile/HTTPS) et gère les URLs vides. */
function safeUrl(url?: string): string {
  if (!url) return "/placeholder.svg";
  return url.startsWith("http://") ? url.replace("http://", "https://") : url;
}

export function AnimeCard({ anime, index = 0, fullWidth = false, priority = false }: Props) {
  const [failed, setFailed] = useState(false);
  const langs = anime.languages_available ?? [];
  const langLabel = langs.length === 2 ? "VF & VOSTFR" : langs[0];
  const eager = priority || index < 6;

  return (
    <div className={fullWidth ? "w-full min-w-0" : "shrink-0 w-[128px] sm:w-[150px] md:w-[180px] snap-start"}>
      <Link
        to={`/anime/${anime.id}`}
        title={`Regarder ${anime.title} en streaming`}
        className="group block focus:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-xl"
      >
        <div className="relative aspect-[2/3] overflow-hidden rounded-xl bg-surface shadow-[var(--shadow-card)] transition-transform duration-200 md:group-hover:scale-[1.03]">
          <img
            src={failed ? "/placeholder.svg" : safeUrl(anime.poster_url)}
            alt={`Affiche de ${anime.title}`}
            width={300}
            height={450}
            loading={eager ? "eager" : "lazy"}
            decoding="async"
            referrerPolicy="no-referrer"
            onError={() => setFailed(true)}
            className="absolute inset-0 w-full h-full object-cover"
          />

          <div className="absolute inset-0" style={{ background: "var(--gradient-card)" }} />

          {langLabel && (
            <div className="absolute top-2 right-2">
              <span className="bg-primary text-primary-foreground text-[10px] font-semibold font-body px-2 py-0.5 rounded-md">
                {langLabel}
              </span>
            </div>
          )}

          <div className="hidden md:flex absolute inset-0 bg-black/55 opacity-0 group-hover:opacity-100 transition-opacity duration-200 items-center justify-center">
            <div className="w-14 h-14 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-[var(--shadow-glow)]">
              <Play className="w-6 h-6 fill-current ml-0.5" />
            </div>
          </div>

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
    </div>
  );
}

export default AnimeCard;
