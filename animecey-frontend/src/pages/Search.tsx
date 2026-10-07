import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Search as SearchIcon, X, Loader2, Plus } from "lucide-react";
import { toast } from "sonner";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { AnimeGrid } from "@/components/anime/AnimeGrid";
import { CatalogGrid } from "@/components/anime/CatalogGrid";
import { getApiError } from "@/api/axios";
import { fetchAnimes } from "@/api/animes";
import { openCatalogTitle, searchCatalog, type CatalogItem } from "@/api/catalog";
import { useAuthStore } from "@/stores/auth";

const PAGE_SIZE = 24;
// Seul ce compte peut ajouter un animé (le serveur le vérifie aussi).
const ADD_ANIME_EMAIL = "admin@animecey.app";

function Pager({
  page,
  pages,
  onChange,
}: {
  page: number;
  pages: number;
  onChange: (p: number) => void;
}) {
  if (pages <= 1) return null;
  return (
    <div className="mt-8 flex items-center justify-center gap-4 font-body text-sm">
      <button
        onClick={() => onChange(Math.max(1, page - 1))}
        disabled={page <= 1}
        className="px-4 py-2 rounded-lg bg-surface border border-border-subtle text-foreground disabled:opacity-40"
      >
        Précédent
      </button>
      <span className="text-muted-foreground">
        Page {page} sur {pages}
      </span>
      <button
        onClick={() => onChange(Math.min(pages, page + 1))}
        disabled={page >= pages}
        className="px-4 py-2 rounded-lg bg-surface border border-border-subtle text-foreground disabled:opacity-40"
      >
        Suivant
      </button>
    </div>
  );
}

export default function Search() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const canAdd = user?.email?.toLowerCase() === ADD_ANIME_EMAIL;

  const [params, setParams] = useSearchParams();
  const initialQ = params.get("q") ?? "";
  const [input, setInput] = useState(initialQ);
  const [debounced, setDebounced] = useState(initialQ);
  const [page, setPage] = useState(1);
  const [catPage, setCatPage] = useState(1);
  const [openingId, setOpeningId] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(input.trim()), 300);
    return () => clearTimeout(t);
  }, [input]);

  useEffect(() => {
    setPage(1);
    setCatPage(1);
    if (debounced) setParams({ q: debounced }, { replace: true });
    else setParams({}, { replace: true });
  }, [debounced, setParams]);

  // Animés de Magi-Stream (recherche floue : accents, fautes, autres noms)
  const animes = useQuery({
    queryKey: ["search-animes", debounced, page],
    queryFn: () => fetchAnimes({ q: debounced, page, limit: PAGE_SIZE }),
    enabled: !!debounced,
  });

  // Catalogue Anime-Sama : uniquement pour l'administrateur, afin d'ajouter un animé
  const catalog = useQuery({
    queryKey: ["search-catalog", debounced, catPage],
    queryFn: () => searchCatalog(debounced, catPage, PAGE_SIZE),
    enabled: !!debounced && canAdd,
  });

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
      toast.error(getApiError(err, "Impossible d'ajouter ce titre pour le moment."));
    } finally {
      setOpeningId(null);
    }
  }

  const total = animes.data?.total ?? 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background"
    >
      <Navbar />
      <main className="pt-24 md:pt-28 pb-20 mx-auto max-w-7xl px-4 md:px-6">
        <h1 className="font-display font-extrabold text-3xl md:text-4xl mb-6">Recherche</h1>

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
            {animes.isLoading && debounced ? (
              <span className="inline-flex items-center gap-1.5">
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Recherche...
              </span>
            ) : (
              <>
                {total} résultat{total > 1 ? "s" : ""}
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

          {debounced && !animes.isLoading && (
            <>
              <AnimeGrid
                animes={animes.data?.items ?? []}
                emptyMessage={`Aucun résultat pour "${debounced}"`}
                emptyHint="Essaie un autre nom ou une partie du titre."
              />
              <Pager page={page} pages={animes.data?.pages ?? 1} onChange={setPage} />
            </>
          )}

          {canAdd && debounced && (
            <section className="mt-14">
              <h2 className="font-display font-bold text-xl mb-1 inline-flex items-center gap-2">
                <Plus className="w-5 h-5 text-primary" /> Ajouter à Magi-Stream
              </h2>
              <p className="text-sm text-muted-foreground font-body mb-5">
                Titres du catalogue qui ne sont pas encore dans Magi-Stream. Clique sur un titre pour l'ajouter.
              </p>
              {catalog.isLoading ? (
                <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Recherche dans le catalogue...
                </span>
              ) : (
                <>
                  <CatalogGrid
                    items={catalog.data?.items ?? []}
                    onOpen={handleOpen}
                    openingId={openingId}
                    emptyMessage="Rien à ajouter pour cette recherche"
                    emptyHint="Tous les titres correspondants sont déjà dans Magi-Stream."
                  />
                  <Pager page={catPage} pages={catalog.data?.pages ?? 1} onChange={setCatPage} />
                </>
              )}
            </section>
          )}
        </div>
      </main>
      <Footer />
    </motion.div>
  );
}
