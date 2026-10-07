import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { Search, Menu, X, User, LogOut, Shield } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { NotificationBell } from "@/components/notifications/NotificationBell";
import { useAuthStore } from "@/stores/auth";

const links = [
  { to: "/catalogue", label: "Catalogue" },
  { to: "/films", label: "Films" },
  { to: "/series", label: "Séries" },
  { to: "/genres", label: "Genres" },
];

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchValue, setSearchValue] = useState("");
  const loc = useLocation();
  const navigate = useNavigate();
  const { user, isAuthenticated, isAdmin, logout } = useAuthStore();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 80);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => setOpen(false), [loc.pathname]);

  useEffect(() => {
    if (!searchOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSearchOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [searchOpen]);

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchValue.trim();
    setSearchOpen(false);
    setSearchValue("");
    navigate(q ? `/search?q=${encodeURIComponent(q)}` : "/search");
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
        <Link to="/" className="font-display font-extrabold text-2xl tracking-tight">
          Magi-<span className="text-primary">Stream</span>
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              className={({ isActive }) =>
                cn(
                  "text-sm font-body font-medium transition-colors",
                  isActive ? "text-primary" : "text-muted-foreground hover:text-foreground",
                )
              }
            >
              {l.label}
            </NavLink>
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
          <NotificationBell />
          {isAuthenticated ? (
            <>
              {isAdmin && (
                <Link
                  to="/admin"
                  aria-label="Admin"
                  className="hidden md:inline-flex w-10 h-10 rounded-full items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface transition-colors"
                >
                  <Shield className="w-5 h-5" />
                </Link>
              )}
              <Link
                to="/profile"
                aria-label="Profil"
                className="hidden md:inline-flex w-10 h-10 rounded-full items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface transition-colors"
              >
                {user?.avatar_url ? (
                  <img src={user.avatar_url} alt="" className="w-8 h-8 rounded-full object-cover" />
                ) : (
                  <User className="w-5 h-5" />
                )}
              </Link>
              <button
                onClick={() => { logout(); navigate("/"); }}
                className="hidden md:inline-flex ml-1 items-center gap-2 px-4 py-2 rounded-lg bg-surface border border-border text-sm font-body font-semibold text-foreground hover:border-primary/40 transition-colors"
              >
                <LogOut className="w-4 h-4" />
                Déconnexion
              </button>
            </>
          ) : (
            <>
              <Link
                to="/profile"
                aria-label="Profil"
                className="hidden md:inline-flex w-10 h-10 rounded-full items-center justify-center text-muted-foreground hover:text-foreground hover:bg-surface transition-colors"
              >
                <User className="w-5 h-5" />
              </Link>
              <Link
                to="/auth"
                className="hidden md:inline-flex ml-1 items-center gap-2 px-4 py-2 rounded-lg bg-surface border border-border text-sm font-body font-semibold text-foreground hover:border-primary/40 transition-colors"
              >
                Connexion
              </Link>
            </>
          )}
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
                <NavLink
                  key={l.to}
                  to={l.to}
                  className={({ isActive }) =>
                    cn(
                      "px-3 py-3 rounded-lg font-body font-medium",
                      isActive
                        ? "bg-surface text-primary"
                        : "text-muted-foreground hover:bg-surface hover:text-foreground",
                    )
                  }
                >
                  {l.label}
                </NavLink>
              ))}
              {isAuthenticated ? (
                <>
                  {isAdmin && (
                    <Link
                      to="/admin"
                      className="px-3 py-3 rounded-lg font-body font-medium text-muted-foreground hover:bg-surface hover:text-foreground flex items-center gap-2"
                    >
                      <Shield className="w-4 h-4" /> Admin
                    </Link>
                  )}
                  <Link
                    to="/profile"
                    className="px-3 py-3 rounded-lg font-body font-medium text-muted-foreground hover:bg-surface hover:text-foreground flex items-center gap-2"
                  >
                    <User className="w-4 h-4" /> {user?.username ?? "Profil"}
                  </Link>
                  <button
                    onClick={() => { logout(); navigate("/"); setOpen(false); }}
                    className="mt-2 inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-surface border border-border text-foreground font-body font-semibold"
                  >
                    <LogOut className="w-4 h-4" /> Déconnexion
                  </button>
                </>
              ) : (
                <Link
                  to="/auth"
                  className="mt-2 inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-primary text-primary-foreground font-body font-semibold"
                >
                  <User className="w-4 h-4" />
                  Connexion
                </Link>
              )}
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