import { Check, ChevronDown, RotateCcw } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import type { CatalogFilters } from "@/types";

const ALL_GENRES = [
  "Action", "Aventure", "Comédie", "Drame", "Fantasy", "Horreur",
  "Mystère", "Romance", "Sci-Fi", "Shonen", "Seinen", "Slice of Life",
  "Sports", "Surnaturel", "Thriller", "Mecha", "Isekai", "Musique",
  "Psychologique", "Ecchi",
];
const ALL_YEARS = [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015];

type Opt<T> = { value: T; label: string };

function Pill<T extends string | number>({
  label,
  value,
  options,
  onChange,
  defaultValue,
}: {
  label: string;
  value: T;
  options: Opt<T>[];
  onChange: (v: T) => void;
  defaultValue: T;
}) {
  const active = value !== defaultValue;
  const current = options.find((o) => o.value === value);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          className={cn(
            "shrink-0 inline-flex items-center gap-1.5 h-9 px-4 rounded-full text-sm font-semibold border transition-colors",
            active
              ? "bg-primary text-primary-foreground border-primary"
              : "bg-surface border-border-subtle text-foreground hover:bg-surface-2",
          )}
        >
          {active ? current?.label : label}
          <ChevronDown className="w-3.5 h-3.5 opacity-70" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-56 p-1.5 bg-popover border-border-subtle rounded-2xl max-h-80 overflow-y-auto">
        {options.map((o) => (
          <button
            key={String(o.value)}
            onClick={() => onChange(o.value)}
            className={cn(
              "w-full flex items-center justify-between px-3 py-2 rounded-xl text-sm text-left transition-colors",
              o.value === value ? "bg-primary/15 text-primary font-semibold" : "hover:bg-surface-2",
            )}
          >
            {o.label}
            {o.value === value && <Check className="w-4 h-4" />}
          </button>
        ))}
      </PopoverContent>
    </Popover>
  );
}

interface Props {
  filters: CatalogFilters;
  onChange: (next: CatalogFilters) => void;
  onReset: () => void;
  hideType?: boolean;
  hideCategory?: boolean;
}

/** Rangée de pastilles de filtres déroulantes (style Aniflix). */
export function FilterPills({ filters, onChange, onReset, hideType, hideCategory }: Props) {
  const set = <K extends keyof CatalogFilters>(k: K, v: CatalogFilters[K]) => onChange({ ...filters, [k]: v });
  const genre = filters.genres?.[0] ?? "all";
  const hasActive =
    genre !== "all" ||
    (filters.type && filters.type !== "all" && !hideType) ||
    (filters.language && filters.language !== "all") ||
    (filters.status && filters.status !== "all") ||
    (filters.year && filters.year !== "all");

  return (
    <div className="flex gap-2 overflow-x-auto no-scrollbar -mx-4 px-4 md:mx-0 md:px-0 py-1">
      <Pill
        label="Trier"
        value={filters.sort ?? "az"}
        defaultValue={"__none" as never}
        onChange={(v) => set("sort", v)}
        options={[
          { value: "az", label: "A-Z" },
          { value: "za", label: "Z-A" },
          { value: "score", label: "Mieux notés" },
          { value: "recent", label: "Récents" },
        ]}
      />
      {!hideCategory && (
        <Pill
          label="Catégorie"
          value={filters.category ?? "all"}
          defaultValue="all"
          onChange={(v) => set("category", v)}
          options={[
            { value: "all", label: "Tout" },
            { value: "anime", label: "Animés" },
            { value: "live", label: "Films & séries" },
          ]}
        />
      )}
      <Pill
        label="Genre"
        value={genre}
        defaultValue="all"
        onChange={(v) => set("genres", v === "all" ? [] : [v])}
        options={[{ value: "all", label: "Tous les genres" }, ...ALL_GENRES.map((g) => ({ value: g, label: g }))]}
      />
      {!hideType && (
        <Pill
          label="Type"
          value={filters.type ?? "all"}
          defaultValue="all"
          onChange={(v) => set("type", v)}
          options={[
            { value: "all", label: "Tous" },
            { value: "serie", label: "Série" },
            { value: "film", label: "Film" },
          ]}
        />
      )}
      <Pill
        label="Langue"
        value={filters.language ?? "all"}
        defaultValue="all"
        onChange={(v) => set("language", v)}
        options={[
          { value: "all", label: "Toutes" },
          { value: "VF", label: "VF" },
          { value: "VOSTFR", label: "VOSTFR" },
          { value: "BOTH", label: "VF & VOSTFR" },
        ]}
      />
      <Pill
        label="Statut"
        value={filters.status ?? "all"}
        defaultValue="all"
        onChange={(v) => set("status", v)}
        options={[
          { value: "all", label: "Tous" },
          { value: "ongoing", label: "En cours" },
          { value: "completed", label: "Terminé" },
          { value: "upcoming", label: "À venir" },
        ]}
      />
      <Pill
        label="Année"
        value={(filters.year ?? "all") as string | number}
        defaultValue="all"
        onChange={(v) => set("year", v === "all" ? "all" : Number(v))}
        options={[{ value: "all", label: "Toutes" }, ...ALL_YEARS.map((y) => ({ value: y, label: String(y) }))]}
      />
      {hasActive && (
        <button
          onClick={onReset}
          className="shrink-0 inline-flex items-center gap-1.5 h-9 px-4 rounded-full text-sm font-semibold text-highlight hover:bg-highlight/10 transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          Réinitialiser
        </button>
      )}
    </div>
  );
}
