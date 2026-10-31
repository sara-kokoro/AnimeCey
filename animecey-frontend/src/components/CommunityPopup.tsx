import { useEffect, useState } from "react";
import { HeartHandshake, Send, Smartphone, X } from "lucide-react";
import { Link, useLocation } from "@/lib/router";
import { APP } from "@/config/app";
import { SOCIAL } from "@/config/social";
import { useIsApp } from "@/hooks/useIsApp";

const KEY = "magi:communitySeen";
const EVERY_DAYS = 3;
const DELAY_MS = 7000;
// pages où l'on ne dérange pas l'utilisateur
const SKIP = ["/watch", "/admin", "/auth", "/don", "/telechargements"];

/**
 * Fenêtre « Communauté Magi-Stream » (site et application) : Telegram, don et, sur le site, l'application Android.
 * Elle s'affiche quelques secondes après l'arrivée, puis au plus une fois tous les 3 jours.
 */
export function CommunityPopup() {
  const isApp = useIsApp();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (SKIP.some((p) => pathname.startsWith(p))) return;
    try {
      const last = Number(localStorage.getItem(KEY) ?? 0);
      if (Date.now() - last < EVERY_DAYS * 86_400_000) return;
    } catch {
      /* stockage indisponible : on affiche quand même */
    }
    const id = window.setTimeout(() => setOpen(true), DELAY_MS);
    return () => window.clearTimeout(id);
  }, [pathname]);

  const close = () => {
    setOpen(false);
    try {
      localStorage.setItem(KEY, String(Date.now()));
    } catch {
      /* ignoré */
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm px-5"
      onClick={close}
    >
      <div
        role="dialog"
        aria-label="Communauté Magi-Stream"
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-sm rounded-3xl bg-surface border border-border-subtle p-6 text-center shadow-2xl"
      >
        <button onClick={close} aria-label="Fermer" className="absolute top-3 right-3 text-muted-foreground p-1">
          <X className="w-5 h-5" />
        </button>
        <h2 className="font-display font-extrabold text-xl">Communauté Magi-Stream</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Rejoins-nous pour les nouveautés, les corrections et les sorties du moment.
        </p>

        {SOCIAL.telegram && (
          <a
            href={SOCIAL.telegram}
            target="_blank"
            rel="noopener noreferrer"
            onClick={close}
            className="mt-5 flex items-center justify-center gap-2 h-12 rounded-2xl bg-primary text-primary-foreground font-bold hover:bg-primary-dim transition-colors"
          >
            <Send className="w-5 h-5" /> Nous suivre sur Telegram
          </a>
        )}

        <div className="mt-5 border-t border-border-subtle pt-4">
          <p className="text-[11px] tracking-widest uppercase text-muted-foreground font-semibold">Aller plus loin</p>
          <div className={`mt-3 grid gap-2 ${isApp ? "grid-cols-1" : "grid-cols-2"}`}>
            {!isApp && APP.apkUrl.trim() && (
              <a
                href={APP.apkUrl}
                download
                onClick={close}
                className="rounded-2xl border border-border bg-background p-3 hover:border-primary/50 transition-colors"
              >
                <Smartphone className="w-6 h-6 mx-auto text-primary" />
                <span className="mt-1 block text-sm font-bold">Télécharger l'application</span>
                <span className="block text-[11px] text-muted-foreground">Toujours la dernière version</span>
              </a>
            )}
            <Link
              to="/don"
              onClick={close}
              className="rounded-2xl border border-border bg-background p-3 hover:border-primary/50 transition-colors"
            >
              <HeartHandshake className="w-6 h-6 mx-auto text-primary" />
              <span className="mt-1 block text-sm font-bold">Faire un don</span>
              <span className="block text-[11px] text-muted-foreground">Garder Magi-Stream gratuit</span>
            </Link>
          </div>
        </div>

        <button onClick={close} className="mt-4 text-xs text-muted-foreground">
          Plus tard
        </button>
      </div>
    </div>
  );
}
