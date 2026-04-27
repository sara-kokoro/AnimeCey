import { Link } from "react-router-dom";
import { Heart, MessageCircle } from "lucide-react";
import type { Episode } from "@/types";
import { cn } from "@/lib/utils";

interface Props {
  episode: Episode;
  blurred?: boolean;
  active?: boolean;
  compact?: boolean;
}

export function EpisodeCard({ episode, blurred = false, active = false, compact = false }: Props) {
  return (
    <Link
      to={`/watch/${episode.id}`}
      className={cn(
        "group flex gap-3 p-2 rounded-xl transition-colors duration-200 hover:bg-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary",
        active && "bg-surface border-l-[3px] border-primary",
      )}
    >
      <div
        className={cn(
          "relative shrink-0 overflow-hidden rounded-lg bg-surface-2",
          compact ? "w-[88px] aspect-video" : "w-[120px] md:w-[160px] aspect-video",
        )}
      >
        {episode.thumbnail_url && (
          <img
            src={episode.thumbnail_url}
            alt={`Épisode ${episode.episode_number}`}
            loading="lazy"
            className={cn(
              "absolute inset-0 w-full h-full object-cover transition-all duration-300",
              blurred && "blur-md scale-110",
            )}
          />
        )}
        <span className="absolute top-1.5 left-1.5 bg-black/75 text-white text-[10px] font-semibold font-body px-1.5 py-0.5 rounded">
          Ép. {episode.episode_number}
        </span>
        <span className="absolute top-1.5 right-1.5 bg-primary text-primary-foreground text-[10px] font-semibold font-body px-1.5 py-0.5 rounded">
          {episode.language}
        </span>
      </div>

      <div className="flex-1 min-w-0 flex flex-col justify-between py-0.5">
        <div>
          <h4 className="font-display font-semibold text-sm text-foreground line-clamp-2 group-hover:text-primary transition-colors">
            {episode.title || `Épisode ${episode.episode_number}`}
          </h4>
          {!compact && (
            <p className="text-xs text-muted-foreground mt-0.5 font-body">
              Saison {episode.season_number}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3 text-muted-foreground text-xs">
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