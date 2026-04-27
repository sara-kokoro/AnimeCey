import { useState } from "react";
import { Search, Edit, Trash2 } from "lucide-react";
import { animes } from "@/data/mock";
import { ToggleGroup2 } from "@/components/ui/ToggleGroup2";

export default function AdminAnimes() {
  const [source, setSource] = useState<"tmdb" | "anilist">("tmdb");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<(typeof animes)[number] | null>(null);
  const results = animes.filter((a) => a.title.toLowerCase().includes(query.toLowerCase())).slice(0, 6);

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
            onChange={(v) => setSource(v as "tmdb" | "anilist")}
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
              placeholder={`Rechercher sur ${source.toUpperCase()}...`}
              className="w-full bg-surface-2 border border-border rounded-lg pl-9 pr-3 py-2 text-sm font-body focus:outline-none focus:border-primary transition-colors"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {results.map((a) => (
              <button
                key={a.id}
                onClick={() => setSelected(a)}
                className="text-left bg-surface-2 border border-border rounded-lg overflow-hidden hover:border-primary/40 transition-colors"
              >
                <img src={a.poster_url} alt={a.title} className="w-full aspect-[2/3] object-cover" />
                <div className="p-2">
                  <p className="text-xs font-body font-semibold truncate">{a.title}</p>
                  <p className="text-[11px] text-muted-foreground font-body">{a.year}</p>
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
                <Field label="Année" value={String(selected.year)} />
                <Field label="Type" value={selected.type === "film" ? "Film" : "Série"} />
                <Field label="Genres" value={selected.genres.join(", ")} />
                <button className="mt-3 w-full px-4 py-2.5 rounded-lg bg-primary text-primary-foreground font-body font-semibold">
                  Créer l'anime et le dossier
                </button>
              </div>
            )}
          </div>
        </div>
      </section>

      <section>
        <h2 className="font-display font-bold text-lg mb-3">Animés existants</h2>
        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-2 border-b border-border">
              <tr className="text-left font-body font-semibold text-muted-foreground">
                <th className="px-4 py-3"></th>
                <th className="px-4 py-3">Titre</th>
                <th className="px-4 py-3 hidden md:table-cell">Type</th>
                <th className="px-4 py-3 hidden md:table-cell">Statut</th>
                <th className="px-4 py-3 hidden md:table-cell">Épisodes</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {animes.map((a) => (
                <tr key={a.id} className="border-b border-border-subtle last:border-b-0 hover:bg-surface-2 transition-colors">
                  <td className="px-4 py-2">
                    <img src={a.poster_url} alt="" className="w-10 h-14 object-cover rounded" />
                  </td>
                  <td className="px-4 py-2 font-body font-semibold">{a.title}</td>
                  <td className="px-4 py-2 hidden md:table-cell text-muted-foreground capitalize">{a.type}</td>
                  <td className="px-4 py-2 hidden md:table-cell text-muted-foreground capitalize">{a.status}</td>
                  <td className="px-4 py-2 hidden md:table-cell text-muted-foreground">{a.episodes_count}</td>
                  <td className="px-4 py-2 text-right">
                    <div className="inline-flex gap-1">
                      <button aria-label="Éditer" className="w-8 h-8 rounded-md hover:bg-surface flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors">
                        <Edit className="w-4 h-4" />
                      </button>
                      <button aria-label="Supprimer" className="w-8 h-8 rounded-md hover:bg-destructive/10 flex items-center justify-center text-destructive transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <label className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">{label}</label>
      <input defaultValue={value} className="mt-0.5 w-full bg-surface border border-border rounded-md px-2 py-1.5 text-sm font-body focus:outline-none focus:border-primary transition-colors" />
    </div>
  );
}