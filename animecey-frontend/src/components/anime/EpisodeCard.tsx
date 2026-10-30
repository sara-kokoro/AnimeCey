import { Link } from "@/lib/router";
import { Clock, Heart, MessageCircle, Play } from "lucide-react";
import type { Episode } from "@/types";
import { cn } from "@/lib/utils";
import { useIsApp } from "@/hooks/useIsApp";
import { OfflineDownloadButton } from "@/components/player/OfflineDownloadButton";

interface Props {
  episode: Episode;
  blurred?: boolean;
  active?: boolean;
  compact?: boolean;
  /** "grid" : vignette au-dessus du texte (listes en colonnes) ; "row" : vignette à gauche. */
  variant?: "row" | "grid";
  /** Nom de la saison / du film (ex. « Film 0 ») ; sinon « Saison N ». */
  seasonLabel?: string;
  anime?: unknown;
  index?: number;
  /** Dans l'application : affiche le bouton « Télécharger » avec la taille du fichier. */
  animeTitle?: string;
  /** octets si connus, null si inconnus */
  size?: number | null;
}

export function EpisodeCard({
  episode,
  blurred = false,
  active = false,
  compact = false,
  variant = "row",
  seasonLabel,
  animeTitle,
  size,
}: Props) {
  const isApp = useIsApp();
  const where = seasonLabel ?? `Saison ${episode.season_number}`;
  const minutes = episode.duration ? Math.max(1, Math.round(episode.duration / 60)) : null;
  if (variant === "grid") {
    return (
      <Link
        to={`/watch/${episode.id}`}
        className="group block min-w-0 overflow-hidden rounded-xl border border-border bg-surface hover:border-primary/50 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        <div className="relative aspect-video bg-surface-2 overflow-hidden">
          {episode.thumbnail_url ? (
            <img
              src={episode.thumbnail_url}
              alt={`Épisode ${episode.episode_number}`}
              loading="lazy"
              className={cn(
                "absolute inset-0 w-full h-full object-cover transition-transform duration-300 group-hover:scale-105",
                blurred && "blur-md scale-110",
              )}
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center font-display font-extrabold text-3xl text-muted-foreground/40">
              {episode.episode_number}
            </div>
          )}
          <span className="absolute top-1.5 left-1.5 bg-black/75 text-white text-[10px] font-semibold font-body px-1.5 py-0.5 rounded">
            Ép. {episode.episode_number}
          </span>
          <span className="absolute top-1.5 right-1.5 bg-primary text-primary-foreground text-[10px] font-semibold font-body px-1.5 py-0.5 rounded">
            {episode.language}
          </span>
        </div>
        <div className="p-2.5 min-w-0">
          <h4 className="font-display font-semibold text-sm text-foreground truncate group-hover:text-primary transition-colors">
            {episode.title || `Épisode ${episode.episode_number}`}
          </h4>
          <div className="mt-1.5 flex items-center gap-3 text-muted-foreground text-xs">
            <span className="inline-flex items-center gap-1">
              <Heart className="w-3.5 h-3.5" />
              {episode.likes_count}
            </span>
            <span className="inline-flex items-center gap-1">
              <MessageCircle className="w-3.5 h-3.5" />
              {episode.comments_count}
            </span>
          </div>
        </div>
      </Link>
    );
  }

  // Mode Liste : grand numéro en filigrane, vignette 16:9, durée, badge, titre.
  return (
    <Link
      to={`/watch/${episode.id}`}
      className={cn(
        "group relative flex items-center gap-3 p-2 pr-3 rounded-xl overflow-hidden border transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary",
        active ? "bg-primary/10 border-primary/50" : "bg-surface border-transparent hover:bg-surface-2",
      )}
    >
      <span
        aria-hidden
        className="pointer-events-none select-none absolute -right-1 -bottom-5 font-display font-black text-[88px] leading-none text-outline opacity-60"
      >
        {episode.episode_number}
      </span>
      <div
        className={cn(
          "relative shrink-0 overflow-hidden rounded-lg bg-surface-2",
          compact ? "w-[112px] aspect-video" : "w-[136px] md:w-[176px] aspect-video",
        )}
      >
        {episode.thumbnail_url ? (
          <img
            src={episode.thumbnail_url}
            alt={`Épisode ${episode.episode_number}`}
            loading="lazy"
            className={cn(
              "absolute inset-0 w-full h-full object-cover transition-transform duration-300 group-hover:scale-105",
              blurred && "blur-md scale-110",
            )}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center font-display font-extrabold text-2xl text-muted-foreground/40">
            {episode.episode_number}
          </div>
        )}
        <div className="absolute inset-0 flex items-center justify-center bg-background/40 opacity-0 group-hover:opacity-100 transition-opacity">
          <span className="w-9 h-9 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
            <Play className="w-4 h-4 fill-current ml-0.5" />
          </span>
        </div>
        {minutes && (
          <span className="absolute bottom-1 right-1 bg-background/85 text-foreground text-[10px] font-semibold px-1.5 py-0.5 rounded inline-flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {minutes} min
          </span>
        )}
      </div>

      <div className="relative flex-1 min-w-0 py-0.5">
        <div className="flex items-center gap-1.5 mb-1">
          <span className="text-[10px] font-bold uppercase tracking-wide text-primary">Ép. {episode.episode_number}</span>
          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-foreground/10 text-foreground">
            {episode.language}
          </span>
          {active && (
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-highlight text-highlight-foreground">
              En cours
            </span>
          )}
        </div>
        <h4 className="font-display font-semibold text-sm text-foreground line-clamp-2 group-hover:text-primary transition-colors">
          {episode.title || `Épisode ${episode.episode_number}`}
        </h4>
        {!compact && <p className="text-xs text-muted-foreground mt-0.5 truncate">{where}</p>}
        <div className="mt-1 flex items-center gap-3 text-muted-foreground text-xs">
          <span className="inline-flex items-center gap-1">
            <Heart className="w-3.5 h-3.5" />
            {episode.likes_count}
          </span>
          <span className="inline-flex items-center gap-1">
            <MessageCircle className="w-3.5 h-3.5" />
            {episode.comments_count}
          </span>
        </div>
        {isApp && animeTitle && (
          <div
            className="mt-2"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
            }}
          >
            <OfflineDownloadButton
              episode={episode}
              animeTitle={animeTitle}
              seasonLabel={where}
              size={size ?? null}
              compact
            />
          </div>
        )}
      </div>
    </Link>
  );
}