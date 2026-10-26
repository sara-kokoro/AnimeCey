import { motion } from "framer-motion";
import { Loader2, Play, SearchX } from "lucide-react";
import type { CatalogItem } from "@/api/catalog";

interface Props {
  items: CatalogItem[];
  onOpen: (item: CatalogItem) => void;
  openingId?: string | null;
  emptyMessage?: string;
  emptyHint?: string;
}

export function CatalogGrid({
  items,
  onOpen,
  openingId = null,
  emptyMessage = "Aucun résultat",
  emptyHint,
}: Props) {
  if (items.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex flex-col items-center justify-center py-20 text-center"
      >
        <div className="w-16 h-16 rounded-full bg-surface flex items-center justify-center mb-4">
          <SearchX className="w-7 h-7 text-muted-foreground" />
        </div>
        <p className="font-display font-semibold text-lg text-foreground">{emptyMessage}</p>
        {emptyHint && (
          <p className="text-sm text-muted-foreground font-body mt-1 max-w-sm">{emptyHint}</p>
        )}
      </motion.div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 md:gap-5">
      {items.map((item, i) => {
        const opening = openingId === item.id;
        return (
          <motion.div
            key={item.id}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.4, delay: Math.min(i * 0.05, 0.4) }}
            className="w-full"
          >
            <button
              type="button"
              onClick={() => onOpen(item)}
              disabled={openingId !== null}
              className="group block w-full text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-xl disabled:cursor-wait"
            >
              <div className="relative aspect-[2/3] overflow-hidden rounded-xl bg-surface shadow-[var(--shadow-card)] transition-all duration-200 group-hover:scale-[1.03] group-hover:shadow-[var(--shadow-glow)]">
                {item.poster_url ? (
                  <img
                    src={item.poster_url}
                    alt={item.title}
                    loading="lazy"
                    className="absolute inset-0 w-full h-full object-cover"
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center p-3 text-center text-sm text-muted-foreground font-body">
                    {item.title}
                  </div>
                )}

                <div className="absolute inset-0" style={{ background: "var(--gradient-card)" }} />

                <div
                  className={`absolute inset-0 bg-black/55 flex items-center justify-center transition-opacity duration-200 ${
                    opening ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                  }`}
                >
                  <div className="w-14 h-14 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-[var(--shadow-glow)]">
                    {opening ? (
                      <Loader2 className="w-6 h-6 animate-spin" />
                    ) : (
                      <Play className="w-6 h-6 fill-current ml-0.5" />
                    )}
                  </div>
                </div>
              </div>

              <h3 className="mt-2 text-[13px] font-display font-semibold text-foreground line-clamp-2 leading-tight">
                {item.title}
              </h3>
            </button>
          </motion.div>
        );
      })}
    </div>
  );
}
