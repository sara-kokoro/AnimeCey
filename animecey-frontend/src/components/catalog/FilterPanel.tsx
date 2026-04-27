import { X } from "lucide-react";
import { allGenres, allYears, type CatalogFilters } from "@/data/mock";
import { ToggleGroup2 } from "@/components/ui/ToggleGroup2";
import { cn } from "@/lib/utils";

interface Props {
  filters: CatalogFilters;
  onChange: (next: CatalogFilters) => void;
  onReset: () => void;
  layout?: "sidebar" | "horizontal";
}

export function FilterPanel({ filters, onChange, onReset, layout = "horizontal" }: Props) {
  const set = <K extends keyof CatalogFilters>(k: K, v: CatalogFilters[K]) =>
    onChange({ ...filters, [k]: v });

  const toggleGenre = (g: string) => {
    const cur = filters.genres ?? [];
    set("genres", cur.includes(g) ? cur.filter((x) => x !== g) : [...cur, g]);
  };

  const hasActive =
    !!filters.query ||
    (filters.genres && filters.genres.length > 0) ||
    (filters.type && filters.type !== "all") ||
    (filters.language && filters.language !== "all") ||
    (filters.status && filters.status !== "all") ||
    (filters.year && filters.year !== "all");

  return (
    <div
      className={cn(
        "space-y-5",
        layout === "sidebar" ? "" : "rounded-2xl bg-surface border border-border-subtle p-4 md:p-5",
      )}
    >
      <FilterBlock label="Type">
        <ToggleGroup2
          size="sm"
          value={filters.type ?? "all"}
          onChange={(v) => set("type", v as CatalogFilters["type"])}
          options={[
            { value: "all", label: "Tous" },
            { value: "serie", label: "Série" },
            { value: "film", label: "Film" },
          ]}
        />
      </FilterBlock>

      <FilterBlock label="Langue">
        <ToggleGroup2
          size="sm"
          value={filters.language ?? "all"}
          onChange={(v) => set("language", v as CatalogFilters["language"])}
          options={[
            { value: "all", label: "Toutes" },
            { value: "VF", label: "VF" },
            { value: "VOSTFR", label: "VOSTFR" },
            { value: "BOTH", label: "VF & VOSTFR" },
          ]}
        />
      </FilterBlock>

      <FilterBlock label="Statut">
        <ToggleGroup2
          size="sm"
          value={filters.status ?? "all"}
          onChange={(v) => set("status", v as CatalogFilters["status"])}
          options={[
            { value: "all", label: "Tous" },
            { value: "ongoing", label: "En cours" },
            { value: "completed", label: "Terminé" },
            { value: "upcoming", label: "À venir" },
          ]}
        />
      </FilterBlock>

      <FilterBlock label="Année">
        <ToggleGroup2
          size="sm"
          value={(filters.year ?? "all") as string | number}
          onChange={(v) => set("year", v === "all" ? "all" : Number(v))}
          options={[
            { value: "all", label: "Toutes" },
            ...allYears.map((y) => ({ value: y, label: String(y) })),
          ]}
        />
      </FilterBlock>

      <FilterBlock label="Genres">
        <div className="flex flex-wrap gap-2">
          {allGenres.map((g) => {
            const active = (filters.genres ?? []).includes(g);
            return (
              <button
                key={g}
                onClick={() => toggleGenre(g)}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-body font-semibold border transition-colors",
                  active
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-surface-2 text-muted-foreground border-border hover:text-foreground hover:border-border-subtle",
                )}
              >
                {g}
              </button>
            );
          })}
        </div>
      </FilterBlock>

      {hasActive && (
        <button
          onClick={onReset}
          className="inline-flex items-center gap-1.5 text-xs font-body font-semibold text-primary hover:text-primary-dim transition-colors"
        >
          <X className="w-3.5 h-3.5" />
          Réinitialiser les filtres
        </button>
      )}
    </div>
  );
}

function FilterBlock({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-body font-semibold mb-2">
        {label}
      </p>
      {children}
    </div>
  );
}