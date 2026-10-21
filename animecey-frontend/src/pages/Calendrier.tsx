import { useMemo, useState } from "react";
import { Link } from "@/lib/router";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { Bell, CalendarX, CheckCircle2, ChevronLeft, ChevronRight, Clock, Info, Loader2, Play } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { cn } from "@/lib/utils";
import { fetchCalendar, type CalendarEntry } from "@/api/calendar";

const DAY_KEY = "yyyy-MM-dd";
type LangFilter = "all" | "VF" | "VOSTFR";

function mondayOf(d: Date): Date {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  return x;
}

function parseDay(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function CalendarRow({ entry }: { entry: CalendarEntry }) {
  const when = new Date(entry.release_at);
  const localTime = format(when, "HH:mm");
  const parisTime = new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Paris",
  }).format(when);
  const released = entry.available || when.getTime() <= Date.now();

  return (
    <li className="relative flex gap-3 md:gap-4">
      {/* Repère chronologique */}
      <div className="flex flex-col items-center w-14 shrink-0 pt-3">
        <span className={cn("font-display font-bold text-sm", released ? "text-foreground" : "text-muted-foreground")}>
          {localTime}
        </span>
        <span className={cn("mt-2 w-2.5 h-2.5 rounded-full", entry.available ? "bg-primary" : released ? "bg-highlight" : "bg-border-subtle")} />
        <span className="flex-1 w-px bg-border mt-1" />
      </div>

      <div className="flex-1 min-w-0 mb-3 rounded-2xl bg-surface border border-border-subtle p-3 flex gap-3 items-center" title={`Heure française : ${parisTime}`}>
        <div className="relative w-16 md:w-20 aspect-[2/3] shrink-0 rounded-xl overflow-hidden bg-surface-2">
          {entry.poster_url ? (
            <img src={entry.poster_url} alt={entry.title} loading="lazy" className="absolute inset-0 w-full h-full object-cover" />
          ) : null}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            {entry.available ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/15 text-primary text-[10px] font-bold">
                <CheckCircle2 className="w-3 h-3" /> En ligne
              </span>
            ) : released ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-highlight/15 text-highlight text-[10px] font-bold">
                <Loader2 className="w-3 h-3 animate-spin" /> Bientôt en ligne
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-foreground/10 text-muted-foreground text-[10px] font-bold">
                <Clock className="w-3 h-3" /> À venir
              </span>
            )}
            <span className="px-2 py-0.5 rounded-full bg-foreground/10 text-[10px] font-semibold">{entry.language}</span>
          </div>
          <h3 className="mt-1 font-display font-semibold text-sm md:text-base leading-tight line-clamp-1">{entry.title}</h3>
          <p className="text-xs text-muted-foreground">
            {entry.season} · Épisode {entry.episode}
          </p>
        </div>
        {entry.anime_id ? (
          <Link
            to={`/anime/${entry.anime_id}`}
            aria-label={entry.available ? `Regarder ${entry.title}` : `Voir ${entry.title}`}
            className={cn(
              "shrink-0 inline-flex items-center gap-1.5 h-9 px-3 md:px-4 rounded-full text-xs font-semibold transition-colors",
              entry.available
                ? "bg-primary text-primary-foreground hover:bg-primary-dim"
                : "bg-surface-2 border border-border-subtle hover:bg-border",
            )}
          >
            {entry.available ? <Play className="w-3.5 h-3.5 fill-current" /> : <Info className="w-3.5 h-3.5" />}
            <span className="hidden sm:inline">{entry.available ? "Regarder" : "Fiche"}</span>
          </Link>
        ) : (
          <span className="shrink-0 inline-flex items-center gap-1.5 h-9 px-3 rounded-full bg-surface-2 text-xs font-semibold text-muted-foreground">
            <Bell className="w-3.5 h-3.5" />
          </span>
        )}
      </div>
    </li>
  );
}

export default function Calendrier() {
  const [week, setWeek] = useState(0);
  const [lang, setLang] = useState<LangFilter>("all");
  const [picked, setPicked] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["calendar", week],
    queryFn: () => fetchCalendar(week),
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });

  const monday = useMemo(() => {
    if (data) return parseDay(data.week_start);
    const m = mondayOf(new Date());
    m.setDate(m.getDate() + week * 7);
    return m;
  }, [data, week]);

  const days = useMemo(
    () =>
      Array.from({ length: 7 }, (_, i) => {
        const d = new Date(monday);
        d.setDate(monday.getDate() + i);
        return d;
      }),
    [monday],
  );

  const byDay = useMemo(() => {
    const map: Record<string, CalendarEntry[]> = {};
    for (const e of data?.entries ?? []) {
      if (lang !== "all" && e.language !== lang) continue;
      const key = format(new Date(e.release_at), DAY_KEY);
      if (!map[key]) map[key] = [];
      map[key].push(e);
    }
    return map;
  }, [data, lang]);

  const todayKey = format(new Date(), DAY_KEY);
  const keys = days.map((d) => format(d, DAY_KEY));
  const selectedKey =
    picked && keys.includes(picked) ? picked : keys.includes(todayKey) ? todayKey : keys[0];
  const entries = [...(byDay[selectedKey] ?? [])].sort(
    (a, b) => new Date(a.release_at).getTime() - new Date(b.release_at).getTime(),
  );
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const goToWeek = (next: number) => {
    setWeek(next);
    setPicked(null);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background"
    >
      <Navbar />
      <main className="pt-20 md:pt-28 pb-20 mx-auto max-w-4xl px-4 md:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display font-black text-3xl md:text-4xl">Calendrier</h1>
            <p className="text-xs text-muted-foreground mt-2">
              Horaires dans ton heure locale ({timeZone}).
            </p>
          </div>

          <div className="flex items-center gap-1 p-1 rounded-full bg-surface border border-border-subtle">
            <button
              type="button"
              onClick={() => goToWeek(week - 1)}
              aria-label="Semaine précédente"
              className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-surface-2"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => goToWeek(0)}
              className={cn(
                "px-3 h-8 rounded-full text-xs font-semibold transition-colors",
                week === 0 ? "text-muted-foreground" : "hover:bg-surface-2",
              )}
            >
              Cette semaine
            </button>
            <button
              type="button"
              onClick={() => goToWeek(week + 1)}
              aria-label="Semaine suivante"
              className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-surface-2"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="mt-5 flex gap-2 overflow-x-auto no-scrollbar -mx-4 px-4 md:mx-0 md:px-0 py-1">
          {days.map((d) => {
            const key = format(d, DAY_KEY);
            const active = key === selectedKey;
            const isToday = key === todayKey;
            const count = (byDay[key] ?? []).length;
            return (
              <button
                key={key}
                type="button"
                onClick={() => setPicked(key)}
                className={cn(
                  "shrink-0 min-w-[64px] rounded-full px-4 py-2 text-center border transition-colors",
                  active
                    ? "bg-primary text-primary-foreground border-primary shadow-glow"
                    : "bg-surface border-border-subtle hover:bg-surface-2",
                )}
              >
                <span className="block text-[11px] font-bold uppercase">
                  {format(d, "EEE", { locale: fr }).replace(".", "")}
                </span>
                <span className="block text-sm font-display font-bold leading-tight">{format(d, "dd")}</span>
                <span
                  className={cn(
                    "mx-auto mt-0.5 block w-1.5 h-1.5 rounded-full",
                    count === 0 ? "bg-transparent" : active ? "bg-primary-foreground" : isToday ? "bg-highlight" : "bg-primary",
                  )}
                />
              </button>
            );
          })}
        </div>

        <div className="mt-4 flex gap-2">
          {(["all", "VF", "VOSTFR"] as LangFilter[]).map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => setLang(l)}
              className={cn(
                "px-3 h-8 rounded-full text-xs font-semibold border transition-colors",
                lang === l
                  ? "bg-foreground text-background border-foreground"
                  : "border-border-subtle text-muted-foreground hover:text-foreground",
              )}
            >
              {l === "all" ? "Toutes langues" : l}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-primary" />
          </div>
        ) : isError ? (
          <p className="py-16 text-center text-sm text-muted-foreground">Impossible de charger le calendrier pour le moment.</p>
        ) : entries.length === 0 ? (
          <div className="py-16 flex flex-col items-center text-center">
            <CalendarX className="w-10 h-10 text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground">Aucune sortie prévue ce jour-là.</p>
          </div>
        ) : (
          <ol className="mt-6">
            {entries.map((e) => (
              <CalendarRow key={e.id} entry={e} />
            ))}
          </ol>
        )}
      </main>
      <Footer />
    </motion.div>
  );
}
