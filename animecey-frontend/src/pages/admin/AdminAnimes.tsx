import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Edit, Trash2, Loader2, Star } from "lucide-react";
import { ToggleGroup2 } from "@/components/ui/ToggleGroup2";
import { adminListAnimes, adminCreateAnime, adminDeleteAnime, tmdbSearch, tmdbDetails, anilistSearch, anilistDetails } from "@/api/admin";
import { getApiError } from "@/api/axios";
import { toast } from "sonner";

interface SearchResult {
  id: number;
  title: string;
  title_jp?: string;
  poster_url?: string;
  year?: number;
  type?: string;
  genres?: string[];
  synopsis?: string;
  score?: number;
  banner_url?: string;
  trailer_url?: string;
  status?: string;
}

export default function AdminAnimes() {
  const qc = useQueryClient();
  const [source, setSource] = useState<"tmdb" | "anilist">("tmdb");
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selected, setSelected] = useState<SearchResult | null>(null);
  const [searching, setSearching] = useState(false);
  const [page, setPage] = useState(1);

  const { data: animesData, isLoading } = useQuery({
    queryKey: ["admin-animes", page],
    queryFn: () => adminListAnimes(page, 24),
  });

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => adminCreateAnime(data),
    onSuccess: () => {
      toast.success("Anime créé avec succès !");
      qc.invalidateQueries({ queryKey: ["admin-animes"] });
      qc.invalidateQueries({ queryKey: ["admin-stats"] });
      setSelected(null);
      setSearchResults([]);
      setQuery("");
    },
    onError: (err: unknown) => toast.error(getApiError(err, "Erreur lors de la création")),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => adminDeleteAnime(id),
    onSuccess: () => {
      toast.success("Anime supprimé");
      qc.invalidateQueries({ queryKey: ["admin-animes"] });
      qc.invalidateQueries({ queryKey: ["admin-stats"] });
    },
    onError: (err: unknown) => toast.error(getApiError(err, "Erreur lors de la suppression")),
  });

  const doSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      if (source === "tmdb") {
        const results = await tmdbSearch(query);
        setSearchResults(
          (results ?? []).map((r: Record<string, unknown>) => ({
            id: r.id as number,
            title: (r.name ?? r.title ?? "") as string,
            poster_url: r.poster_path ? `https://image.tmdb.org/t/p/w500${r.poster_path}` : undefined,
            banner_url: r.backdrop_path ? `https://image.tmdb.org/t/p/original${r.backdrop_path}` : undefined,
            year: r.first_air_date ? parseInt(String(r.first_air_date).slice(0, 4)) : r.release_date ? parseInt(String(r.release_date).slice(0, 4)) : undefined,
            type: r.media_type === "movie" ? "film" : "serie",
            synopsis: r.overview as string,
            score: r.vote_average ? Math.round(Number(r.vote_average) * 10) / 10 : undefined,
          })),
        );
      } else {
        const results = await anilistSearch(query);
        setSearchResults(
          (results ?? []).map((r: Record<string, unknown>) => {
            const title = r.title as Record<string, string> | undefined;
            return {
              id: r.id as number,
              title: title?.english ?? title?.romaji ?? "",
              title_jp: title?.native,
              poster_url: (r.coverImage as Record<string, string>)?.extraLarge ?? (r.coverImage as Record<string, string>)?.large,
              banner_url: r.bannerImage as string,
              year: (r.seasonYear ?? (r.startDate && (r.startDate as Record<string, number>).year)) as number,
              type: r.format === "MOVIE" ? "film" : "serie",
              genres: r.genres as string[],
              synopsis: r.description ? String(r.description).replace(/<[^>]+>/g, "") : undefined,
              score: r.averageScore ? Number(r.averageScore) / 10 : undefined,
              status: r.status === "RELEASING" ? "ongoing" : r.status === "FINISHED" ? "completed" : "upcoming",
            };
          }),
        );
      }
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 401 || status === 403) {
        toast.error("Accès refusé — connecte-toi en tant qu'admin");
      } else {
        toast.error(getApiError(err, "Erreur lors de la recherche"));
      }
    }
    setSearching(false);
  };

  const handleSelectAndLoadDetails = async (item: SearchResult) => {
    setSelected(item);
    try {
      if (source === "tmdb") {
        const details = await tmdbDetails(item.id, item.type === "film" ? "movie" : "tv");
        if (details) {
          setSelected((prev) => ({
            ...prev!,
            genres: details.genres?.map((g: Record<string, string>) => g.name) ?? prev!.genres,
            synopsis: details.overview ?? prev!.synopsis,
            trailer_url: details.trailer_url ?? prev!.trailer_url,
            status: details.status === "Returning Series" ? "ongoing" : details.status === "Ended" ? "completed" : prev!.status,
          }));
        }
      } else {
        const details = await anilistDetails(item.id);
        if (details) {
          const title = details.title as Record<string, string> | undefined;
          setSelected((prev) => ({
            ...prev!,
            title_jp: title?.native ?? prev!.title_jp,
            genres: details.genres ?? prev!.genres,
            synopsis: details.description ? String(details.description).replace(/<[^>]+>/g, "") : prev!.synopsis,
          }));
        }
      }
    } catch {
      /* keep basic info */
    }
  };

  const handleCreate = () => {
    if (!selected) return;
    createMutation.mutate({
      title: selected.title,
      title_jp: selected.title_jp ?? null,
      type: selected.type ?? "serie",
      status: selected.status ?? "ongoing",
      synopsis: selected.synopsis ?? null,
      poster_url: selected.poster_url ?? null,
      banner_url: selected.banner_url ?? null,
      genres: selected.genres ?? [],
      score: selected.score ?? 0,
      year: selected.year ?? new Date().getFullYear(),
      trailer_url: selected.trailer_url ?? null,
      is_featured: false,
      ...(source === "tmdb" ? { tmdb_id: selected.id } : { anilist_id: selected.id }),
    });
  };

  const animes = animesData?.items ?? [];

  return (
    <div>
      <h1 className="font-display font-extrabold text-3xl mb-1">Animés</h1>
      <p className="text-muted-foreground font-body mb-6">
        Recherche, importe et gère les fiches d'animés.
      </p>

      <section className="bg-surface border border-border rounded-xl p-5 mb-8">
        <h2 className="font-display font-bold text-lg mb-4">Importer depuis une source</h2>
        <div className="flex flex-col md:flex-row gap-3 mb-4">
          <ToggleGroup2
            value={source}
            onChange={(v) => { setSource(v as "tmdb" | "anilist"); setSearchResults([]); setSelected(null); }}
            options={[
              { value: "tmdb", label: "TMDB" },
              { value: "anilist", label: "AniList" },
            ]}
          />
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && doSearch()}
              placeholder={`Rechercher sur ${source.toUpperCase()}... (Entrée pour chercher)`}
              className="w-full bg-surface-2 border border-border rounded-lg pl-9 pr-3 py-2 text-sm font-body focus:outline-none focus:border-primary transition-colors"
            />
          </div>
          <button
            onClick={doSearch}
            disabled={searching || !query.trim()}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-body font-semibold disabled:opacity-40"
          >
            {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : "Chercher"}
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-[500px] overflow-y-auto">
            {searchResults.length === 0 && !searching && (
              <p className="col-span-full text-sm text-muted-foreground font-body py-4 text-center">
                Tape un titre et clique sur Chercher.
              </p>
            )}
            {searching && (
              <div className="col-span-full flex justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-primary" />
              </div>
            )}
            {searchResults.map((a) => (
              <button
                key={a.id}
                onClick={() => handleSelectAndLoadDetails(a)}
                className={`text-left bg-surface-2 border rounded-lg overflow-hidden hover:border-primary/40 transition-colors ${selected?.id === a.id ? "border-primary ring-1 ring-primary" : "border-border"}`}
              >
                {a.poster_url ? (
                  <img src={a.poster_url} alt={a.title} className="w-full aspect-[2/3] object-cover" />
                ) : (
                  <div className="w-full aspect-[2/3] bg-surface flex items-center justify-center text-muted-foreground text-xs">
                    Pas d'image
                  </div>
                )}
                <div className="p-2">
                  <p className="text-xs font-body font-semibold truncate">{a.title}</p>
                  <p className="text-[11px] text-muted-foreground font-body">{a.year ?? "?"}</p>
                </div>
              </button>
            ))}
          </div>

          <div className="bg-surface-2 border border-border rounded-lg p-4">
            <h3 className="font-display font-bold mb-3">Détails</h3>
            {!selected && (
              <p className="text-sm text-muted-foreground font-body">
                Sélectionne un résultat pour pré-remplir le formulaire.
              </p>
            )}
            {selected && (
              <div className="space-y-2 text-sm font-body">
                <Field label="Titre FR" value={selected.title} />
                <Field label="Titre JP" value={selected.title_jp ?? ""} />
                <Field label="Année" value={String(selected.year ?? "")} />
                <Field label="Type" value={selected.type === "film" ? "Film" : "Série"} />
                <Field label="Score" value={selected.score ? String(selected.score) : ""} />
                <Field label="Genres" value={selected.genres?.join(", ") ?? ""} />
                {selected.synopsis && (
                  <div>
                    <label className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Synopsis</label>
                    <p className="mt-0.5 text-xs text-foreground/80 line-clamp-4">{selected.synopsis}</p>
                  </div>
                )}
                <button
                  onClick={handleCreate}
                  disabled={createMutation.isPending}
                  className="mt-3 w-full px-4 py-2.5 rounded-lg bg-primary text-primary-foreground font-body font-semibold disabled:opacity-50"
                >
                  {createMutation.isPending ? "Création..." : "Créer l'anime et le dossier"}
                </button>
              </div>
            )}
          </div>
        </div>
      </section>

      <section>
        <h2 className="font-display font-bold text-lg mb-3">
          Animés existants ({animesData?.total ?? 0})
        </h2>
        {isLoading ? (
          <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
        ) : (
          <div className="bg-surface border border-border rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-surface-2 border-b border-border">
                <tr className="text-left font-body font-semibold text-muted-foreground">
                  <th className="px-4 py-3"></th>
                  <th className="px-4 py-3">Titre</th>
                  <th className="px-4 py-3 hidden md:table-cell">Type</th>
                  <th className="px-4 py-3 hidden md:table-cell">Statut</th>
                  <th className="px-4 py-3 hidden md:table-cell">Score</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {animes.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground font-body">
                      Aucun anime. Importe-en un ci-dessus.
                    </td>
                  </tr>
                )}
                {animes.map((a: Record<string, unknown>) => (
                  <tr key={String(a.id)} className="border-b border-border-subtle last:border-b-0 hover:bg-surface-2 transition-colors">
                    <td className="px-4 py-2">
                      {a.poster_url ? (
                        <img src={String(a.poster_url)} alt="" className="w-10 h-14 object-cover rounded" />
                      ) : (
                        <div className="w-10 h-14 bg-surface-2 rounded" />
                      )}
                    </td>
                    <td className="px-4 py-2 font-body font-semibold">{String(a.title)}</td>
                    <td className="px-4 py-2 hidden md:table-cell text-muted-foreground capitalize">{String(a.type)}</td>
                    <td className="px-4 py-2 hidden md:table-cell text-muted-foreground capitalize">{String(a.status)}</td>
                    <td className="px-4 py-2 hidden md:table-cell">
                      <span className="inline-flex items-center gap-1 text-muted-foreground">
                        <Star className="w-3 h-3 fill-primary text-primary" />
                        {String(a.score ?? 0)}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">
                      <div className="inline-flex gap-1">
                        <button
                          onClick={() => {
                            if (confirm("Supprimer cet anime ?")) deleteMutation.mutate(Number(a.id));
                          }}
                          aria-label="Supprimer"
                          className="w-8 h-8 rounded-md hover:bg-destructive/10 flex items-center justify-center text-destructive transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {(animesData?.pages ?? 1) > 1 && (
              <div className="flex justify-center gap-2 p-4 border-t border-border">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="px-3 py-1.5 rounded-lg text-xs font-body font-semibold bg-surface-2 border border-border disabled:opacity-40"
                >
                  Précédent
                </button>
                <span className="px-3 py-1.5 text-xs font-body text-muted-foreground">
                  Page {page} / {animesData?.pages ?? 1}
                </span>
                <button
                  disabled={page >= (animesData?.pages ?? 1)}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1.5 rounded-lg text-xs font-body font-semibold bg-surface-2 border border-border disabled:opacity-40"
                >
                  Suivant
                </button>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <label className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">{label}</label>
      <input defaultValue={value} readOnly className="mt-0.5 w-full bg-surface border border-border rounded-md px-2 py-1.5 text-sm font-body focus:outline-none focus:border-primary transition-colors" />
    </div>
  );
}
