import { useEffect, useRef, useState } from "react";
import { Link } from "@/lib/router";
import { ChevronLeft, ChevronRight, Play, Star } from "lucide-react";
import type { Anime } from "@/types";

function safeUrl(url?: string) {
  if (!url) return "/placeholder.svg";
  return url.startsWith("http://") ? url.replace("http://", "https://") : url;
}

/** Slider paginé horizontal : grandes cartes paysage, flèches, points de page animés. */
export function PagedSlider({ items, isLoading }: { items?: Anime[]; isLoading: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState(0);
  const [pages, setPages] = useState(1);
  const list = (items ?? []).slice(0, 15);

  const measure = () => {
    const el = ref.current;
    if (!el) return;
    const p = Math.max(1, Math.ceil(el.scrollWidth / el.clientWidth - 0.05));
    setPages(p);
    setPage(Math.min(p - 1, Math.round(el.scrollLeft / el.clientWidth)));
  };
  useEffect(() => {
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [list.length]);

  const goTo = (p: number) => {
    const el = ref.current;
    if (!el) return;
    el.scrollTo({ left: Math.max(0, Math.min(pages - 1, p)) * el.clientWidth, behavior: "smooth" });
  };

  return (
    <div className="relative group/slider">
      <div
        ref={ref}
        onScroll={measure}
        className="flex gap-3 md:gap-4 overflow-x-auto no-scrollbar snap-x snap-mandatory scroll-smooth -mx-3 px-3 md:mx-0 md:px-0"
      >
        {isLoading && list.length === 0
          ? Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="w-[85%] sm:w-[48%] lg:w-[32%] shrink-0 aspect-video rounded-2xl shimmer" />
            ))
          : list.map((a, i) => (
              <Link
                key={a.id}
                to={`/anime/${a.id}`}
                className="group relative w-[85%] sm:w-[48%] lg:w-[32%] shrink-0 snap-start aspect-video overflow-hidden rounded-2xl bg-surface border border-border-subtle hover:border-primary/60 transition-all duration-500 animate-in fade-in slide-in-from-right-4"
                style={{ animationDelay: `${Math.min(i, 6) * 60}ms` }}
              >
                <img
                  src={safeUrl(a.banner_url ?? a.poster_url)}
                  alt={a.title}
                  loading="lazy"
                  referrerPolicy="no-referrer"
                  className="absolute inset-0 w-full h-full object-cover object-top transition-transform duration-700 group-hover:scale-110"
                />
                <div className="absolute inset-0" style={{ background: "var(--gradient-card)" }} />
                <span className="absolute top-2 left-2 text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-primary text-primary-foreground">
                  Nouveau
                </span>
                <div className="absolute inset-x-0 bottom-0 p-3 flex items-end gap-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="font-display font-bold text-base md:text-lg text-foreground line-clamp-1 group-hover:text-primary transition-colors">
                      {a.title}
                    </h3>
                    <div className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
                      <Star className="w-3.5 h-3.5 fill-primary text-primary" />
                      <span className="text-foreground font-semibold">{a.score}</span>
                      <span>• {a.year} • {a.type === "film" ? "Film" : "Série"}</span>
                    </div>
                  </div>
                  <span className="w-10 h-10 shrink-0 rounded-full bg-primary text-primary-foreground flex items-center justify-center scale-90 group-hover:scale-100 transition-transform">
                    <Play className="w-4 h-4 fill-current ml-0.5" />
                  </span>
                </div>
              </Link>
            ))}
      </div>

      {pages > 1 && (
        <>
          <button onClick={() => goTo(page - 1)} disabled={page === 0} aria-label="Précédent" className="hidden sm:flex absolute -left-3 top-[40%] z-10 w-10 h-10 rounded-full bg-surface/90 border border-border-subtle items-center justify-center disabled:opacity-0 hover:bg-primary hover:text-primary-foreground transition-all">
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button onClick={() => goTo(page + 1)} disabled={page >= pages - 1} aria-label="Suivant" className="hidden sm:flex absolute -right-3 top-[40%] z-10 w-10 h-10 rounded-full bg-surface/90 border border-border-subtle items-center justify-center disabled:opacity-0 hover:bg-primary hover:text-primary-foreground transition-all">
            <ChevronRight className="w-5 h-5" />
          </button>
          <div className="mt-4 flex items-center justify-center gap-2">
            {Array.from({ length: pages }).map((_, i) => (
              <button
                key={i}
                onClick={() => goTo(i)}
                aria-label={`Page ${i + 1}`}
                className={"h-1.5 rounded-full transition-all duration-500 " + (i === page ? "w-8 bg-primary" : "w-1.5 bg-muted hover:bg-muted-foreground")}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
