import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Search as SearchIcon, X, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { CatalogGrid } from "@/components/anime/CatalogGrid";
import { getApiError } from "@/api/axios";
import { openCatalogTitle, searchCatalog, type CatalogItem } from "@/api/catalog";

const PAGE_SIZE = 24;

export default function Search() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const initialQ = params.get("q") ?? "";
  const [input, setInput] = useState(initialQ);
  const [debounced, setDebounced] = useState(initialQ);
  const [page, setPage] = useState(1);
  const [openingId, setOpeningId] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(input.trim()), 300);
    return () => clearTimeout(t);
  }, [input]);

  useEffect(() => {
    setPage(1);
    if (debounced) setParams({ q: debounced }, { replace: true });
    else setParams({}, { replace: true });
  }, [debounced, setParams]);

  const { data, isLoading } = useQuery({
    queryKey: ["search-catalog", debounced, page],
    queryFn: () => searchCatalog(debounced, page, PAGE_SIZE),
    enabled: !!debounced,
  });

  const results = data?.items ?? [];

  async function handleOpen(item: CatalogItem) {
    if (openingId) return;
    setOpeningId(item.id);
    try {
      const res = await openCatalogTitle(item.id);
      if (res.preparing) {
        toast.info("Les épisodes sont en cours de préparation, cela peut prendre quelques minutes.");
      }
      navigate(`/anime/${res.anime_id}`);
    } catch (err) {
      toast.error(getApiError(err, "Impossible d'ouvrir ce titre pour le moment."));
    } finally {
      setOpeningId(null);
    }
  }

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
            <>
              <CatalogGrid
                items={results}
                onOpen={handleOpen}
                openingId={openingId}
                emptyMessage={`Aucun résultat pour "${debounced}"`}
                emptyHint="Essaie un autre titre ou une partie du nom."
              />
              {(data?.pages ?? 1) > 1 && (
                <div className="mt-8 flex items-center justify-center gap-4 font-body text-sm">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className="px-4 py-2 rounded-lg bg-surface border border-border-subtle text-foreground disabled:opacity-40"
                  >
                    Précédent
                  </button>
                  <span className="text-muted-foreground">
                    Page {page} sur {data?.pages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(data?.pages ?? 1, p + 1))}
                    disabled={page >= (data?.pages ?? 1)}
                    className="px-4 py-2 rounded-lg bg-surface border border-border-subtle text-foreground disabled:opacity-40"
                  >
                    Suivant
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>
      <Footer />
    </motion.div>
  );
}
