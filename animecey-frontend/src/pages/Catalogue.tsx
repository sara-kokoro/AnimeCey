import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "@/lib/router";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Search as SearchIcon, X } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { AnimeGrid } from "@/components/anime/AnimeGrid";
import { FilterPills } from "@/components/catalog/FilterPills";
import { fetchAnimes, type AnimeFilters } from "@/api/animes";
import type { CatalogFilters } from "@/types";

interface Props {
  presetType?: "serie" | "film";
  /** Impose la catégorie (« anime » = animation japonaise) et masque le sélecteur Tout / Animés / Films & séries. */
  presetCategory?: "anime" | "live";
  title?: string;
  subtitle?: string;
}

export default function Catalogue({ presetType, presetCategory, title, subtitle }: Props = {}) {
  const params = useParams();
  const genreParam = params.slug ? decodeURIComponent(params.slug) : undefined;
  const [searchParams] = useSearchParams();
  const catParam = searchParams.get("category");
  const sortParam = searchParams.get("sort");
  const initialCategory: "all" | "anime" | "live" = catParam === "live" || catParam === "anime" ? catParam : "all";
  const initialSort: CatalogFilters["sort"] =
    sortParam === "score" || sortParam === "recent" || sortParam === "za" ? sortParam : "az";

  const [filters, setFilters] = useState<CatalogFilters>({
    type: presetType ?? "all",
    genres: genreParam ? [genreParam] : [],
    sort: initialSort,
    category: presetCategory ?? initialCategory,
  });
  const [page, setPage] = useState(1);
  // Recherche en direct : on attend 300 ms après la dernière frappe.
  const [queryInput, setQueryInput] = useState("");
  useEffect(() => {
    const t = setTimeout(() => {
      setPage(1);
      setFilters((f) => ({ ...f, query: queryInput.trim() || undefined }));
    }, 300);
    return () => clearTimeout(t);
  }, [queryInput]);

  const apiFilters: AnimeFilters = {
    page,
    limit: 24,
    sort: filters.sort,
    type: filters.type !== "all" ? filters.type : undefined,
    status: filters.status !== "all" ? filters.status : undefined,
    genre: filters.genres?.[0],
    language: filters.language !== "all" ? filters.language : undefined,
    year: filters.year && filters.year !== "all" ? (filters.year as number) : undefined,
    q: filters.query,
    category: filters.category !== "all" ? filters.category : undefined,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["animes", apiFilters],
    queryFn: () => fetchAnimes(apiFilters),
    placeholderData: keepPreviousData,
  });

  const reset = () =>
    setFilters({
      type: presetType ?? "all",
      genres: genreParam ? [genreParam] : [],
      sort: filters.sort,
      category: filters.category,
      query: filters.query,
    });

  const headerTitle = title ?? (genreParam ? `Animés · ${genreParam}` : "Catalogue");

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background"
    >
      <Navbar />
      <main className="pt-20 md:pt-28 pb-20 mx-auto max-w-7xl px-4 md:px-6">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="font-display font-black text-3xl md:text-4xl">{headerTitle}</h1>
            {subtitle && <p className="text-sm text-muted-foreground mt-2 max-w-2xl">{subtitle}</p>}
          </div>
          <p className="shrink-0 text-xs font-semibold text-muted-foreground px-3 py-1.5 rounded-full bg-surface border border-border-subtle">
            {data?.total ?? 0} titre{(data?.total ?? 0) > 1 ? "s" : ""}
          </p>
        </div>

        <div className="relative mt-5">
          <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <input
            value={queryInput}
            onChange={(e) => setQueryInput(e.target.value)}
            placeholder="Rechercher dans le catalogue..."
            className="w-full h-12 bg-surface border border-border-subtle rounded-full pl-12 pr-12 text-foreground placeholder:text-muted-foreground/70 focus:outline-none focus:border-primary transition-colors"
          />
          {queryInput && (
            <button
              onClick={() => setQueryInput("")}
              aria-label="Effacer"
              className="absolute right-3 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface-2"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="mt-4">
          <FilterPills
            filters={filters}
            onChange={(f) => { setPage(1); setFilters(f); }}
            onReset={() => { setPage(1); reset(); }}
            hideType={!!presetType}
            hideCategory={!!presetCategory}
          />
        </div>

        <div className="mt-6 min-w-0">
          {isLoading ? (
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3 md:gap-5">
              {Array.from({ length: 12 }).map((_, i) => <div key={i} className="aspect-[2/3] rounded-xl shimmer" />)}
            </div>
          ) : (
            <AnimeGrid
              animes={data?.items ?? []}
              emptyMessage="Aucun résultat"
              emptyHint="Modifie ou réinitialise les filtres pour voir plus de titres."
            />
          )}
          {data && data.pages > 1 && (
            <div className="flex flex-wrap justify-center gap-2 mt-10">
              {Array.from({ length: data.pages }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  onClick={() => { setPage(p); window.scrollTo({ top: 0, behavior: "smooth" }); }}
                  className={`min-w-9 h-9 px-3 rounded-full text-sm font-semibold ${p === page ? "bg-primary text-primary-foreground" : "bg-surface border border-border-subtle hover:bg-surface-2"}`}
                >
                  {p}
                </button>
              ))}
            </div>
          )}
        </div>
      </main>
      <Footer />
    </motion.div>
  );
}
