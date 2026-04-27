import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { SlidersHorizontal, X } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { AnimeGrid } from "@/components/anime/AnimeGrid";
import { FilterPanel } from "@/components/catalog/FilterPanel";
import { ToggleGroup2 } from "@/components/ui/ToggleGroup2";
import { fetchAnimes, type AnimeFilters } from "@/api/animes";
import type { CatalogFilters } from "@/types";

interface Props {
  presetType?: "serie" | "film";
  title?: string;
  subtitle?: string;
}

export default function Catalogue({ presetType, title, subtitle }: Props = {}) {
  const params = useParams();
  const genreParam = params.slug ? decodeURIComponent(params.slug) : undefined;

  const [filters, setFilters] = useState<CatalogFilters>({
    type: presetType ?? "all",
    genres: genreParam ? [genreParam] : [],
    sort: "az",
  });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [page, setPage] = useState(1);

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
  };

  const { data, isLoading } = useQuery({
    queryKey: ["animes", apiFilters],
    queryFn: () => fetchAnimes(apiFilters),
  });

  const reset = () =>
    setFilters({
      type: presetType ?? "all",
      genres: genreParam ? [genreParam] : [],
      sort: filters.sort,
    });

  const headerTitle = title ?? (genreParam ? `Animés • ${genreParam}` : "Catalogue");

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background"
    >
      <Navbar />
      <main className="pt-24 md:pt-28 pb-20 mx-auto max-w-7xl px-4 md:px-6">
        <div className="flex items-end justify-between gap-4 mb-2">
          <div>
            <h1 className="font-display font-extrabold text-3xl md:text-4xl">
              {headerTitle}
            </h1>
            {subtitle && (
              <p className="text-sm text-muted-foreground font-body mt-2 max-w-2xl">
                {subtitle}
              </p>
            )}
            <p className="text-sm text-muted-foreground font-body mt-2">
              {data?.total ?? 0} titre{(data?.total ?? 0) > 1 ? "s" : ""}
            </p>
          </div>
          <button
            onClick={() => setDrawerOpen(true)}
            className="lg:hidden inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-surface border border-border-subtle text-sm font-body font-semibold"
          >
            <SlidersHorizontal className="w-4 h-4" />
            Filtres
          </button>
        </div>

        <div className="mt-6 grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-6 lg:gap-10">
          <aside className="hidden lg:block">
            <div className="sticky top-24">
              <FilterPanel
                filters={filters}
                onChange={setFilters}
                onReset={reset}
                layout="sidebar"
              />
            </div>
          </aside>

          {drawerOpen && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 bg-black/70 lg:hidden"
              onClick={() => setDrawerOpen(false)}
            >
              <motion.div
                initial={{ x: "-100%" }}
                animate={{ x: 0 }}
                exit={{ x: "-100%" }}
                transition={{ type: "spring", damping: 24 }}
                onClick={(e) => e.stopPropagation()}
                className="absolute left-0 top-0 bottom-0 w-[85%] max-w-sm bg-background border-r border-border-subtle p-5 overflow-y-auto"
              >
                <div className="flex items-center justify-between mb-5">
                  <h2 className="font-display font-bold text-lg">Filtres</h2>
                  <button
                    onClick={() => setDrawerOpen(false)}
                    className="w-9 h-9 rounded-full flex items-center justify-center hover:bg-surface"
                    aria-label="Fermer"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
                <FilterPanel
                  filters={filters}
                  onChange={setFilters}
                  onReset={reset}
                  layout="sidebar"
                />
              </motion.div>
            </motion.div>
          )}

          <div className="min-w-0">
            <div className="mb-5 flex items-center justify-between gap-3">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-body font-semibold">
                Trier par
              </p>
              <ToggleGroup2
                size="sm"
                value={filters.sort ?? "az"}
                onChange={(v) => setFilters({ ...filters, sort: v as CatalogFilters["sort"] })}
                options={[
                  { value: "az", label: "A-Z" },
                  { value: "za", label: "Z-A" },
                  { value: "score", label: "Mieux notés" },
                  { value: "recent", label: "Récents" },
                ]}
              />
            </div>
            {isLoading ? (
              <div className="py-20 text-center text-muted-foreground animate-pulse">Chargement...</div>
            ) : (
              <AnimeGrid
                animes={data?.items ?? []}
                emptyMessage="Aucun résultat"
                emptyHint="Modifie ou réinitialise les filtres pour voir plus de titres."
              />
            )}
            {data && data.pages > 1 && (
              <div className="flex justify-center gap-2 mt-8">
                {Array.from({ length: data.pages }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={`px-3 py-1.5 rounded-md text-sm font-body ${p === page ? "bg-primary text-primary-foreground" : "bg-surface hover:bg-surface/80"}`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>
      <Footer />
    </motion.div>
  );
}
