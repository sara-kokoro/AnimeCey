import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ExternalLink, Loader2, Lock, X } from "lucide-react";

/**
 * Navigateur intégré : la page de paiement s'affiche DANS Magi-Stream (plein écran), sans ouvrir Chrome.
 * Si la page de paiement refuse de s'afficher ici, « Ouvrir dans le navigateur » reste toujours disponible.
 */
export function PaymentFrame({ url, open, onClose }: { url: string | null; open: boolean; onClose: () => void }) {
  const [loaded, setLoaded] = useState(false);
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoaded(false);
    setSlow(false);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const t = window.setTimeout(() => setSlow(true), 12_000);
    return () => {
      document.body.style.overflow = prev;
      window.clearTimeout(t);
    };
  }, [open, url]);

  return (
    <AnimatePresence>
      {open && url && (
        <motion.div
          className="fixed inset-0 z-[90] flex flex-col bg-background"
          initial={{ y: "100%" }}
          animate={{ y: 0 }}
          exit={{ y: "100%" }}
          transition={{ type: "spring", damping: 32, stiffness: 300 }}
        >
          <header className="flex items-center gap-2 h-14 px-3 border-b border-border bg-surface shrink-0" style={{ paddingTop: "env(safe-area-inset-top)" }}>
            <button type="button" onClick={onClose} aria-label="Fermer" className="w-10 h-10 rounded-full bg-background border border-border flex items-center justify-center">
              <X className="w-5 h-5" />
            </button>
            <div className="flex-1 min-w-0 flex items-center gap-2">
              <Lock className="w-4 h-4 text-primary shrink-0" />
              <span className="font-display font-bold text-sm truncate">Paiement sécurisé</span>
            </div>
            <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 h-10 px-3 rounded-full border border-border text-xs font-bold">
              <ExternalLink className="w-4 h-4" /> Navigateur
            </a>
          </header>
          <div className="relative flex-1 bg-white">
            {!loaded && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-background text-center px-6">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
                <p className="font-bold">Chargement de la page de paiement…</p>
                <p className="text-sm text-muted-foreground">Ça peut prendre quelques secondes sur une connexion lente.</p>
                {slow && (
                  <a href={url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-2 h-11 px-5 rounded-full bg-primary text-primary-foreground text-sm font-bold">
                    <ExternalLink className="w-4 h-4" /> Ouvrir dans le navigateur
                  </a>
                )}
              </div>
            )}
            <iframe
              key={url}
              src={url}
              title="Paiement"
              className="absolute inset-0 w-full h-full border-0"
              allow="payment *; clipboard-write"
              referrerPolicy="no-referrer-when-downgrade"
              onLoad={() => setLoaded(true)}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
