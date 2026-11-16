import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Search, X } from "lucide-react";
import type { DonateCountry } from "@/api/donate";
import { flag } from "./flags";

const norm = (t: string) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Sélecteur de pays : feuille qui monte du bas, avec recherche, drapeaux et indicatifs. */
export function CountrySheet({
  open,
  countries,
  value,
  onSelect,
  onClose,
}: {
  open: boolean;
  countries: DonateCountry[];
  value: string;
  onSelect: (code: string) => void;
  onClose: () => void;
}) {
  const [q, setQ] = useState("");
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQ("");
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  const list = useMemo(() => {
    const n = norm(q.trim());
    if (!n) return countries;
    return countries.filter((c) => norm(c.name).includes(n) || c.dial.includes(n) || c.code.toLowerCase() === n);
  }, [q, countries]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[80] flex items-end md:items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <button type="button" aria-label="Fermer" className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Choisir un pays"
            className="relative w-full md:max-w-md max-h-[82vh] flex flex-col rounded-t-3xl md:rounded-3xl bg-surface border border-border-subtle shadow-2xl"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 320 }}
            onAnimationComplete={() => input.current?.focus({ preventScroll: true })}
          >
            <div className="mx-auto mt-2 h-1.5 w-10 rounded-full bg-border md:hidden" />
            <div className="flex items-center justify-between px-5 pt-3">
              <h3 className="font-display font-extrabold text-lg">Choisis ton pays</h3>
              <button type="button" onClick={onClose} aria-label="Fermer" className="w-9 h-9 rounded-full bg-background border border-border flex items-center justify-center">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="px-5 pt-3">
              <div className="flex items-center gap-2 h-12 rounded-2xl bg-background border border-border px-3 focus-within:border-primary">
                <Search className="w-4 h-4 text-muted-foreground shrink-0" />
                <input
                  ref={input}
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Rechercher un pays ou un indicatif"
                  className="flex-1 bg-transparent outline-none text-sm"
                />
              </div>
            </div>
            <ul className="mt-3 overflow-y-auto px-3 pb-4 flex-1">
              {list.map((c) => {
                const active = c.code === value;
                return (
                  <li key={c.code}>
                    <button
                      type="button"
                      onClick={() => {
                        onSelect(c.code);
                        onClose();
                      }}
                      className={`w-full flex items-center gap-3 px-3 h-14 rounded-2xl text-left transition-colors ${active ? "bg-primary/15" : "hover:bg-background"}`}
                    >
                      <span className="text-2xl leading-none w-8 text-center">{flag(c.code)}</span>
                      <span className="flex-1 min-w-0">
                        <span className="block font-bold text-[15px] leading-tight truncate">{c.name}</span>
                        <span className="block text-xs text-muted-foreground">{c.dial} · {c.currency}</span>
                      </span>
                      {active && <Check className="w-5 h-5 text-primary shrink-0" />}
                    </button>
                  </li>
                );
              })}
              {list.length === 0 && <li className="px-3 py-8 text-center text-sm text-muted-foreground">Aucun pays trouvé.</li>}
            </ul>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
