import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Search as SearchIcon, X, Loader2 } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { AnimeGrid } from "@/components/anime/AnimeGrid";
import { fetchAnimes, type AnimeFilters } from "@/api/animes";

export default function Search() {
  const [params, setParams] = useSearchParams();
  const initialQ = params.get("q") ?? "";
  const [input, setInput] = useState(initialQ);
  const [debounced, setDebounced] = useState(initialQ);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(input), 300);
    return () => clearTimeout(t);
  }, [input]);

  useEffect(() => {
    if (debounced) setParams({ q: debounced }, { replace: true });
    else setParams({}, { replace: true });
  }, [debounced, setParams]);

  const apiFilters: AnimeFilters = { q: debounced || undefined, limit: 24 };
  const { data, isLoading } = useQuery({
    queryKey: ["search-animes", debounced],
    queryFn: () => fetchAnimes(apiFilters),
    enabled: !!debounced,
  });

  const results = data?.items ?? [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background"
    >
      <Navbar />
      <main className="pt-24 md:pt-28 pb-20 mx-auto max-w-7xl px-4 md:px-6">
        <h1 className="font-display font-extrabold text-3xl md:text-4xl mb-6">
          Recherche
        </h1>

        <div className="relative max-w-2xl">
          <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <input
            autoFocus
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Rechercher un anime, un film..."
            className="w-full bg-surface border border-border-subtle rounded-lg pl-12 pr-12 py-3.5 text-foreground placeholder:text-muted-foreground/70 font-body focus:outline-none focus:border-primary transition-colors"
          />
          {input && (
            <button
              onClick={() => setInput("")}
              aria-label="Effacer"
              className="absolute right-3 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="mt-8">
          <p className="text-sm text-muted-foreground font-body mb-5">
            {isLoading && debounced ? (
              <span className="inline-flex items-center gap-1.5">
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Recherche...
              </span>
            ) : (
              <>
                {data?.total ?? 0} résultat{(data?.total ?? 0) > 1 ? "s" : ""}
                {debounced && (
                  <>
                    {" "}pour <span className="text-foreground font-semibold">"{debounced}"</span>
                  </>
                )}
              </>
            )}
          </p>
          {!debounced && (
            <p className="text-center text-muted-foreground font-body py-12">
              Tape un titre pour lancer la recherche.
            </p>
          )}
          {debounced && !isLoading && (
            <AnimeGrid
              animes={results}
              emptyMessage={debounced ? `Aucun résultat pour "${debounced}"` : "Aucun résultat"}
              emptyHint="Essaie un autre titre ou modifie les filtres."
            />
          )}
        </div>
      </main>
      <Footer />
    </motion.div>
  );
}
