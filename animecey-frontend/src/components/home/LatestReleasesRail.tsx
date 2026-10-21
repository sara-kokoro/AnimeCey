import { useQuery } from "@tanstack/react-query";
import { Link } from "@/lib/router";
import { CalendarClock, Clock, Play } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { fetchCalendar, type CalendarEntry } from "@/api/calendar";
import { HorizontalScroll } from "@/components/ui/HorizontalScroll";

function ReleaseCard({ entry }: { entry: CalendarEntry }) {
  const when = new Date(entry.release_at);
  const body = (
    <div className="group relative w-[280px] md:w-[320px] shrink-0 snap-start overflow-hidden rounded-2xl bg-surface border border-border-subtle hover:border-primary/50 transition-colors p-3 flex gap-3 items-center">
      <span
        aria-hidden
        className="pointer-events-none select-none absolute -right-2 -bottom-6 font-display font-black text-[110px] leading-none text-outline opacity-50"
      >
        {entry.episode}
      </span>
      <div className="relative w-[136px] aspect-video shrink-0 rounded-xl overflow-hidden bg-surface-2">
        {entry.poster_url ? (
          <img src={entry.poster_url} alt="" loading="lazy" className="absolute inset-0 w-full h-full object-cover object-top transition-transform duration-300 group-hover:scale-105" />
        ) : null}
        <div className="absolute inset-0 flex items-center justify-center bg-background/30 opacity-0 group-hover:opacity-100 transition-opacity">
          <span className="w-9 h-9 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
            <Play className="w-4 h-4 fill-current ml-0.5" />
          </span>
        </div>
        <span className="absolute bottom-1 right-1 inline-flex items-center gap-1 rounded bg-background/85 px-1.5 py-0.5 text-[10px] font-semibold">
          <Clock className="w-3 h-3" />
          {formatDistanceToNow(when, { addSuffix: false, locale: fr })}
        </span>
      </div>
      <div className="relative min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold uppercase tracking-wide text-primary">Ép. {entry.episode}</span>
          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-highlight text-highlight-foreground">
            {entry.language}
          </span>
        </div>
        <h3 className="mt-1 font-display font-semibold text-sm leading-tight line-clamp-2 group-hover:text-primary transition-colors">
          {entry.title}
        </h3>
        <p className="mt-0.5 text-[11px] text-muted-foreground truncate">{entry.season}</p>
      </div>
    </div>
  );
  return entry.anime_id ? <Link to={`/anime/${entry.anime_id}`}>{body}</Link> : body;
}

/** Rail « Dernières sorties » : épisodes déjà en ligne cette semaine, du plus récent au plus ancien. */
export function LatestReleasesRail() {
  const { data, isLoading } = useQuery({
    queryKey: ["calendar", 0],
    queryFn: () => fetchCalendar(0),
    staleTime: 60_000,
  });
  const now = Date.now();
  const items = (data?.entries ?? [])
    .filter((e) => e.available || new Date(e.release_at).getTime() <= now)
    .sort((a, b) => new Date(b.release_at).getTime() - new Date(a.release_at).getTime())
    .slice(0, 16);

  if (!isLoading && items.length === 0) return null;

  return (
    <section className="mt-10">
      <div className="flex items-end justify-between mb-4">
        <h2 className="font-display font-bold text-xl md:text-2xl inline-flex items-center gap-2">
          <CalendarClock className="w-5 h-5 text-primary" />
          Dernières sorties
        </h2>
        <Link to="/calendrier" className="text-sm font-semibold text-primary hover:text-primary-dim">
          Calendrier
        </Link>
      </div>
      <HorizontalScroll>
        {isLoading
          ? Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="w-[280px] md:w-[320px] h-[100px] shrink-0 rounded-2xl shimmer" />
            ))
          : items.map((e) => <ReleaseCard key={e.id} entry={e} />)}
      </HorizontalScroll>
    </section>
  );
}
