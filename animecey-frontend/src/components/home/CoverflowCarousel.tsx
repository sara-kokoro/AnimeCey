import { useEffect, useRef, useState } from "react";
import { Link } from "@/lib/router";
import { ChevronLeft, ChevronRight, Play, Star } from "lucide-react";
import type { Anime } from "@/types";

export interface CoverflowTab {
  key: string;
  label: string;
  items?: Anime[];
  isLoading?: boolean;
}

function safeUrl(url?: string) {
  if (!url) return "/placeholder.svg";
  return url.startsWith("http://") ? url.replace("http://", "https://") : url;
}

/** Carrousel « coverflow » façon Aniflix : la carte du milieu est la plus grande, les autres rétrécissent sur les côtés. */
export function CoverflowCarousel({ tabs }: { tabs: CoverflowTab[] }) {
  const [tabKey, setTabKey] = useState(tabs[0]?.key);
  const tab = tabs.find((t) => t.key === tabKey) ?? tabs[0];
  const items = (tab?.items ?? []).slice(0, 15);
  const [active, setActive] = useState(0);
  const [step, setStep] = useState(130);
  const startX = useRef<number | null>(null);

  useEffect(() => setActive(Math.min(2, Math.max(0, items.length - 1))), [tabKey, items.length]);
  useEffect(() => {
    const update = () => {
      const w = window.innerWidth;
      setStep(w >= 1024 ? 230 : w >= 640 ? 180 : 120);
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  const go = (d: number) => setActive((i) => Math.min(items.length - 1, Math.max(0, i + d)));
  const current = items[active];

  return (
    <div>
      <div className="flex gap-2 overflow-x-auto no-scrollbar -mx-3 px-3 md:mx-0 md:px-0 md:justify-center">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTabKey(t.key)}
            className={
              "shrink-0 px-4 py-2 rounded-full text-sm font-semibold transition-colors " +
              (t.key === tab?.key
                ? "bg-primary text-primary-foreground"
                : "bg-surface border border-border-subtle text-muted-foreground hover:text-foreground")
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      <div
        className="relative mt-6 h-[300px] sm:h-[380px] lg:h-[460px] overflow-hidden select-none touch-pan-y"
        onPointerDown={(e) => (startX.current = e.clientX)}
        onPointerUp={(e) => {
          if (startX.current === null) return;
          const dx = e.clientX - startX.current;
          startX.current = null;
          if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1);
        }}
      >
        {tab?.isLoading && items.length === 0 && (
          <div className="absolute left-1/2 top-0 -translate-x-1/2 w-[170px] sm:w-[220px] lg:w-[280px] aspect-[2/3] rounded-2xl shimmer" />
        )}
        {items.map((a, i) => {
          const off = i - active;
          const abs = Math.abs(off);
          if (abs > 3) return null;
          const scale = 1 - abs * 0.16;
          const isCenter = off === 0;
          const card = (
            <div className="relative w-full aspect-[2/3] overflow-hidden rounded-2xl bg-surface shadow-[var(--shadow-card)]">
              <img src={safeUrl(a.poster_url)} alt={a.title} referrerPolicy="no-referrer" draggable={false} className="absolute inset-0 w-full h-full object-cover" />
              {!isCenter && <div className="absolute inset-0 bg-background/45" />}
              {isCenter && (
                <div className="absolute inset-x-0 bottom-0 p-3 lg:p-4" style={{ background: "var(--gradient-card)" }}>
                  <div className="flex items-center gap-1 text-xs font-semibold text-foreground">
                    <Star className="w-3.5 h-3.5 fill-primary text-primary" /> {a.score}
                    <span className="text-muted-foreground ml-1">{a.year} • {a.type === "film" ? "Film" : "Série"}</span>
                  </div>
                </div>
              )}
            </div>
          );
          return (
            <div
              key={a.id}
              className="absolute left-1/2 top-0 w-[170px] sm:w-[220px] lg:w-[280px] transition-all duration-500 ease-out"
              style={{
                transform: `translateX(calc(-50% + ${off * step}px)) scale(${scale})`,
                transformOrigin: "center top",
                zIndex: 10 - abs,
                opacity: abs === 3 ? 0.4 : 1,
              }}
            >
              {isCenter ? (
                <Link to={`/anime/${a.id}`} draggable={false}>{card}</Link>
              ) : (
                <button className="block w-full" onClick={() => setActive(i)} aria-label={a.title}>{card}</button>
              )}
            </div>
          );
        })}

        {items.length > 1 && (
          <>
            <button onClick={() => go(-1)} disabled={active === 0} aria-label="Précédent" className="hidden sm:flex absolute left-2 top-1/3 z-20 w-11 h-11 rounded-full bg-surface/90 border border-border-subtle items-center justify-center disabled:opacity-30 hover:bg-primary hover:text-primary-foreground transition-colors">
              <ChevronLeft className="w-5 h-5" />
            </button>
            <button onClick={() => go(1)} disabled={active === items.length - 1} aria-label="Suivant" className="hidden sm:flex absolute right-2 top-1/3 z-20 w-11 h-11 rounded-full bg-surface/90 border border-border-subtle items-center justify-center disabled:opacity-30 hover:bg-primary hover:text-primary-foreground transition-colors">
              <ChevronRight className="w-5 h-5" />
            </button>
          </>
        )}
      </div>

      {current && (
        <div className="-mt-10 sm:-mt-14 lg:-mt-16 relative z-20 text-center px-4">
          <h3 className="font-display font-bold text-lg md:text-2xl text-foreground line-clamp-1">{current.title}</h3>
          <Link
            to={`/anime/${current.id}`}
            className="mt-3 inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-primary text-primary-foreground font-semibold text-sm shadow-[var(--shadow-glow)]"
          >
            <Play className="w-4 h-4 fill-current" /> Regarder
          </Link>
          <div className="mt-3 flex justify-center gap-1.5">
            {items.map((_, i) => (
              <span key={i} className={"h-1.5 rounded-full transition-all " + (i === active ? "w-5 bg-primary" : "w-1.5 bg-muted")} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
