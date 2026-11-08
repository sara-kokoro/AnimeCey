/**
 * Habillage de la page « Hors connexion » : copie fidèle de la barre du haut, du pied de page et de la
 * navigation du bas du site (Navbar, Footer, BottomNav), avec le même HTML et les mêmes classes.
 * Seule différence : les liens ne passent plus par le routeur du site (absent de cette page) ; ils
 * ouvrent le site, ou préviennent qu'il n'y a pas de connexion.
 */
import { useEffect, useState, type AnchorHTMLAttributes, type FormEvent, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, CalendarDays, CloudDownload, Home, LayoutGrid, Megaphone, Menu, Search, User, X } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export const SITE = "https://www.magi-stream.online/";

/** Ouvre une page du site, ou prévient si le téléphone n'a pas de connexion. */
export function goSite(path = "") {
  if (navigator.onLine) {
    location.href = SITE + path.replace(/^\//, "");
  } else {
    toast.info("Pas de connexion : reconnecte-toi pour ouvrir cette page.");
  }
}

/** Équivalent du <Link> du site. */
export function SiteLink({
  to,
  onClick,
  children,
  ...rest
}: Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { to: string; children?: ReactNode }) {
  return (
    <a
      href={SITE + to.replace(/^\//, "")}
      onClick={(e) => {
        e.preventDefault();
        onClick?.(e);
        goSite(to);
      }}
      {...rest}
    >
      {children}
    </a>
  );
}

const links = [
  { to: "/catalogue", label: "Catalogue" },
  { to: "/films", label: "Films" },
  { to: "/films-japanime", label: "Films Japanime" },
  { to: "/series", label: "Séries" },
  { to: "/genres", label: "Genres" },
  { to: "/calendrier", label: "Calendrier" },
];

/** Navbar du site (version visiteur non connecté : la session du site n'existe pas dans l'application hors connexion). */
export function OfflineNavbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchValue, setSearchValue] = useState("");

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 80);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!searchOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSearchOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [searchOpen]);

  const submitSearch = (e: FormEvent) => {
    e.preventDefault();
    const q = searchValue.trim();
    setSearchOpen(false);
    setSearchValue("");
    goSite(q ? `/search?q=${encodeURIComponent(q)}` : "/search");
  };

  return (
    <header
      className={cn(
        "fixed top-0 inset-x-0 z-50 transition-all duration-300",
        scrolled
          ? "bg-background/85 backdrop-blur-xl border-b border-border"
          : "bg-gradient-to-b from-background/80 to-transparent",
      )}
    >
      <div className="mx-auto max-w-7xl px-4 md:px-6 h-16 flex items-center justify-between">
        <SiteLink to="/" className="font-display font-extrabold text-2xl tracking-tight">
          Magi-<span className="text-primary">Stream</span>
        </SiteLink>

        <nav className="hidden md:flex items-center gap-8">
          {links.map((l) => (
            <SiteLink
              key={l.to}
              to={l.to}
              className="text-sm font-body font-medium transition-colors text-muted-foreground hover:text-foreground"
            >
              {l.label}
            </SiteLink>
          ))}
        </nav>

        <div className="flex items-center gap-1">
          <button
            onClick={() => setSearchOpen(true)}
            aria-label="Rechercher"
            className="w-10 h-10 rounded-full flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface transition-colors"
          >
            <Search className="w-5 h-5" />
          </button>
          <div className="relative">
            <button
              onClick={() => goSite("/notifications")}
              aria-label="Notifications"
              className="w-10 h-10 rounded-full flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface transition-colors relative"
            >
              <span className="inline-flex">
                <Bell className="w-5 h-5" />
              </span>
            </button>
          </div>
          <SiteLink
            to="/profile"
            aria-label="Profil"
            className="hidden md:inline-flex w-10 h-10 rounded-full items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface transition-colors"
          >
            <User className="w-5 h-5" />
          </SiteLink>
          <SiteLink
            to="/auth"
            className="hidden md:inline-flex ml-1 items-center gap-2 px-4 py-2 rounded-lg bg-surface border border-border text-sm font-body font-semibold text-foreground hover:border-primary/40 transition-colors"
          >
            Connexion
          </SiteLink>
          <button
            aria-label="Menu"
            onClick={() => setOpen((v) => !v)}
            className="md:hidden w-10 h-10 rounded-full flex items-center justify-center text-foreground"
          >
            {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden border-t border-border bg-background/95 backdrop-blur-xl overflow-hidden"
          >
            <nav className="px-4 py-4 flex flex-col gap-1">
              {links.map((l) => (
                <SiteLink
                  key={l.to}
                  to={l.to}
                  onClick={() => setOpen(false)}
                  className="px-3 py-3 rounded-lg font-body font-medium text-muted-foreground hover:bg-surface hover:text-foreground"
                >
                  {l.label}
                </SiteLink>
              ))}
              <SiteLink
                to="/auth"
                onClick={() => setOpen(false)}
                className="mt-2 inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-primary text-primary-foreground font-body font-semibold"
              >
                <User className="w-4 h-4" />
                Connexion
              </SiteLink>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Search overlay */}
      <AnimatePresence>
        {searchOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-[60] bg-background/80 backdrop-blur-md"
            onClick={() => setSearchOpen(false)}
          >
            <motion.div
              initial={{ y: -20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: -20, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="mx-auto max-w-2xl mt-24 px-4"
            >
              <form onSubmit={submitSearch} className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <input
                  autoFocus
                  value={searchValue}
                  onChange={(e) => setSearchValue(e.target.value)}
                  placeholder="Rechercher un anime, un film..."
                  className="w-full bg-surface border border-border-subtle rounded-xl pl-12 pr-12 py-4 text-foreground placeholder:text-muted-foreground/70 font-body focus:outline-none focus:border-primary transition-colors text-base"
                />
                <button
                  type="button"
                  onClick={() => setSearchOpen(false)}
                  aria-label="Fermer"
                  className="absolute right-3 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </form>
              <p className="text-xs text-muted-foreground font-body mt-3 text-center">
                Appuie sur Entrée pour lancer la recherche · Échap pour fermer
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

/** Footer du site (le bouton « Télécharger notre application » y est caché dans l'application, comme sur le site). */
export function OfflineFooter() {
  return (
    <footer className="mt-24 border-t border-border bg-background">
      <div className="mx-auto max-w-7xl px-4 md:px-6 py-12 flex flex-col md:flex-row gap-6 md:items-center md:justify-between">
        <div>
          <p className="font-display font-extrabold text-xl">
            Magi-<span className="text-primary">Stream</span>
          </p>
          <p className="text-sm text-muted-foreground font-body mt-1">Streaming d'animés en VF & VOSTFR.</p>
        </div>
        <nav className="flex flex-wrap gap-x-6 gap-y-2 text-sm font-body text-muted-foreground">
          <SiteLink to="/catalogue" className="hover:text-foreground transition-colors">Catalogue</SiteLink>
          <SiteLink to="/genres" className="hover:text-foreground transition-colors">Genres</SiteLink>
          <SiteLink to="/legal" className="hover:text-foreground transition-colors">Mentions légales</SiteLink>
          <SiteLink to="/don" className="hover:text-foreground transition-colors">Faire un don</SiteLink>
          <SiteLink to="/contact" className="hover:text-foreground transition-colors">Contact</SiteLink>
        </nav>
        <p className="text-xs font-body text-muted-dim">© {new Date().getFullYear()} Magi-Stream</p>
      </div>
    </footer>
  );
}

const items = [
  { to: "/", label: "Accueil", icon: Home, active: false },
  { to: "/calendrier", label: "Calendrier", icon: CalendarDays, active: false },
  { to: "/catalogue", label: "Catalogue", icon: LayoutGrid, center: true, active: false },
  { to: "/telechargements", label: "Télécharg.", icon: CloudDownload, active: true },
  { to: "/profile", label: "Profil", icon: User, active: false },
] as const;

/** Navigation fixe du bas sur mobile (« Télécharg. » est l'onglet actif, comme sur la page du site). */
export function OfflineBottomNav() {
  return (
    <nav
      aria-label="Navigation principale"
      className="md:hidden fixed bottom-0 inset-x-0 z-50 border-t border-border bg-background/95 backdrop-blur-xl pb-[env(safe-area-inset-bottom)]"
    >
      <ul className="grid grid-cols-5 h-16">
        {items.map((it) => {
          const Icon = it.icon;
          if ("center" in it && it.center) {
            return (
              <li key={it.label} className="flex justify-center">
                <SiteLink to={it.to} aria-label={it.label} className="-mt-6 flex flex-col items-center gap-1">
                  <span className="w-14 h-14 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-glow ring-4 ring-background transition-transform active:scale-95">
                    <Icon className="w-6 h-6" />
                  </span>
                  <span className="text-[10px] font-semibold text-muted-foreground">{it.label}</span>
                </SiteLink>
              </li>
            );
          }
          return (
            <li key={it.label}>
              <SiteLink
                to={it.to}
                className={cn(
                  "h-full flex flex-col items-center justify-center gap-1 text-[10px] font-semibold transition-colors",
                  it.active ? "text-primary" : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="w-5 h-5" />
                {it.label}
              </SiteLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Emplacement de pub : même rendu que l'AdSlot du site. Hors connexion, on affiche la dernière pub
 * enregistrée par l'application ; à défaut, l'invitation « Affiche ta pub ici ».
 */
export function OfflineAdSlot({ className }: { className?: string }) {
  let data: any = null;
  try {
    data = JSON.parse((window as any).MagiNative?.getOfflineAd?.() || "null");
  } catch {
    /* pas de pub enregistrée */
  }
  const ad = data?.ad ?? null;
  const open = (u?: string) => u && (window as any).MagiNative?.openExternal?.(u);

  if (!ad?.image) {
    return (
      <div className={cn("mx-auto max-w-3xl", className)}>
        <SiteLink
          to="/pub"
          className="flex items-center gap-3 rounded-2xl border border-dashed border-border bg-surface/40 px-4 py-3 hover:border-primary/50 hover:bg-surface/70 transition-colors"
        >
          <span className="shrink-0 w-10 h-10 rounded-xl bg-primary/15 text-primary flex items-center justify-center">
            <Megaphone className="w-5 h-5" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-display font-bold text-sm">Affiche ta pub ici</span>
            <span className="block text-xs text-muted-foreground">
              Augmente ta visibilité avec Magi-Stream : contacte-nous pour réserver cet emplacement.
            </span>
          </span>
          <span className="shrink-0 text-xs font-bold text-primary">Voir</span>
        </SiteLink>
      </div>
    );
  }

  return (
    <div className={cn("mx-auto max-w-3xl", className)}>
      <div className="overflow-hidden rounded-2xl border border-border-subtle bg-surface">
        <a
          href={ad.link}
          onClick={(e) => {
            e.preventDefault();
            open(ad.link);
          }}
          className="relative block bg-black/30"
        >
          <img src={ad.image} alt="Publicité" className="w-full max-h-[320px] object-contain" />
          <span className="absolute top-2 left-2 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold text-white">
            Publicité
          </span>
        </a>
        {(ad.text || (ad.button_text && ad.button_link)) && (
          <div className="p-3">
            {ad.text && (
              <blockquote className="border-l-4 border-primary pl-3 text-sm text-foreground/90 whitespace-pre-line">
                {ad.text}
              </blockquote>
            )}
            {ad.button_text && ad.button_link && (
              <a
                href={ad.button_link}
                onClick={(e) => {
                  e.preventDefault();
                  open(ad.button_link);
                }}
                className="mt-3 flex h-11 items-center justify-center rounded-full bg-primary text-primary-foreground font-bold hover:bg-primary-dim transition-colors"
              >
                {ad.button_text}
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
