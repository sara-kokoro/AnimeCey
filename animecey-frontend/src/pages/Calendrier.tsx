import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { CheckCircle2, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
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

function CalendarCard({ entry }: { entry: CalendarEntry }) {
  const when = new Date(entry.release_at);
  const localTime = format(when, "HH:mm");
  const parisTime = new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Paris",
  }).format(when);

  const body = (
    <>
      <div className="relative aspect-[2/3] overflow-hidden rounded-xl bg-surface shadow-[var(--shadow-card)] transition-all duration-200 group-hover:scale-[1.03]">
        {entry.poster_url ? (
          <img
            src={entry.poster_url}
            alt={entry.title}
            loading="lazy"
            className="absolute inset-0 w-full h-full object-cover"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center p-3 text-center text-xs font-display font-semibold text-muted-foreground">
            {entry.title}
          </div>
        )}
        <div className="absolute inset-0" style={{ background: "var(--gradient-card)" }} />

        <span className="absolute top-2 left-2 rounded-md bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold font-body text-white">
          E{entry.episode}
        </span>
        <span className="absolute top-2 right-2 rounded-md bg-primary px-2 py-0.5 text-[10px] font-semibold font-body text-primary-foreground">
          {entry.language}
        </span>

        {entry.available && (
          <span className="absolute bottom-2 right-2 flex items-center gap-1 rounded-md bg-emerald-600/90 px-1.5 py-0.5 text-[10px] font-semibold font-body text-white">
            <CheckCircle2 className="w-3 h-3" /> En ligne
          </span>
        )}

        <div className="absolute inset-x-0 bottom-7 text-center">
          <span className="font-display font-extrabold text-2xl text-white drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)]">
            {localTime}
          </span>
        </div>
      </div>
      <h3 className="mt-2 text-[13px] font-display font-semibold text-foreground line-clamp-2 leading-tight">
        {entry.title}
      </h3>
      <p className="text-[11px] text-muted-foreground font-body">{entry.season}</p>
    </>
  );

  const className = "group block rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-primary";
  const hint = `Heure française : ${parisTime}`;
  return entry.anime_id ? (
    <Link to={`/anime/${entry.anime_id}`} className={className} title={hint}>
      {body}
    </Link>
  ) : (
    <div className={className} title={hint}>
      {body}
    </div>
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
  const entries = byDay[selectedKey] ?? [];
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
      <main className="pt-24 md:pt-28 pb-20 mx-auto max-w-7xl px-4 md:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display font-extrabold text-3xl md:text-4xl">Calendrier</h1>
            <p className="text-sm text-muted-foreground font-body mt-2">
              Horaires affichés dans ton heure locale ({timeZone}). Survole une carte pour voir l'heure française.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => goToWeek(week - 1)}
              aria-label="Semaine précédente"
              className="p-2 rounded-lg border border-border hover:bg-card transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => goToWeek(0)}
              className={cn(
                "px-3 py-2 rounded-lg border border-border text-sm font-body transition-colors",
                week === 0 ? "bg-card text-muted-foreground" : "hover:bg-card",
              )}
            >
              Cette semaine
            </button>
            <button
              type="button"
              onClick={() => goToWeek(week + 1)}
              aria-label="Semaine suivante"
              className="p-2 rounded-lg border border-border hover:bg-card transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="mt-6 flex gap-2">
          {(["all", "VF", "VOSTFR"] as LangFilter[]).map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => setLang(l)}
              className={cn(
                "px-3 py-1.5 rounded-full text-xs font-semibold font-body border transition-colors",
                lang === l
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {l === "all" ? "Tous" : l}
            </button>
          ))}
        </div>

        <div className="mt-4 grid grid-cols-7 gap-1.5 md:gap-2">
          {days.map((d) => {
            const key = format(d, DAY_KEY);
            const active = key === selectedKey;
            return (
              <button
                key={key}
                type="button"
                onClick={() => setPicked(key)}
                className={cn(
                  "rounded-lg border px-1 py-2 text-center transition-colors",
                  active
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border hover:bg-card",
                )}
              >
                <span className="block text-[10px] md:text-xs font-semibold uppercase font-body">
                  {format(d, "EEE", { locale: fr })}
                </span>
                <span className="block text-xs md:text-sm font-display font-bold">{format(d, "dd/MM")}</span>
                <span className={cn("block text-[10px] font-body", active ? "opacity-80" : "text-muted-foreground")}>
                  {(byDay[key] ?? []).length || "–"}
                </span>
              </button>
            );
          })}
        </div>

        {isLoading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-primary" />
          </div>
        ) : isError ? (
          <p className="py-16 text-center text-sm text-muted-foreground font-body">
            Impossible de charger le calendrier pour le moment.
          </p>
        ) : entries.length === 0 ? (
          <p className="py-16 text-center text-sm text-muted-foreground font-body">
            Aucune sortie prévue ce jour-là.
          </p>
        ) : (
          <div className="mt-6 grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3 md:gap-4">
            {entries.map((e) => (
              <CalendarCard key={e.id} entry={e} />
            ))}
          </div>
        )}
      </main>
      <Footer />
    </motion.div>
  );
}
