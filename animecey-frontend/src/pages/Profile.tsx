import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Settings, BookOpen, Heart, History as HistoryIcon, LogOut, Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { Avatar } from "@/components/comments/Avatar";
import { AnimeGrid } from "@/components/anime/AnimeGrid";
import { useAuthStore } from "@/stores/auth";
import { fetchWatchlist, fetchFavorites, fetchHistory } from "@/api/users";
import { cn } from "@/lib/utils";

const tabs = [
  { id: "watchlist", label: "Watchlist", icon: BookOpen },
  { id: "favorites", label: "Favoris", icon: Heart },
  { id: "history", label: "Historique", icon: HistoryIcon },
  { id: "settings", label: "Paramètres", icon: Settings },
] as const;

const subWatch = [
  { id: "watching", label: "En cours" },
  { id: "planned", label: "Planifié" },
  { id: "completed", label: "Terminé" },
  { id: "dropped", label: "Abandonné" },
] as const;

export default function Profile() {
  const navigate = useNavigate();
  const { user, isAuthenticated, logout } = useAuthStore();
  const [tab, setTab] = useState<(typeof tabs)[number]["id"]>("watchlist");
  const [subTab, setSubTab] = useState<(typeof subWatch)[number]["id"]>("watching");

  const { data: watchlist = [], isLoading: loadingWl } = useQuery({
    queryKey: ["watchlist", subTab],
    queryFn: () => fetchWatchlist(subTab),
    enabled: isAuthenticated && tab === "watchlist",
  });

  const { data: favorites = [], isLoading: loadingFav } = useQuery({
    queryKey: ["favorites"],
    queryFn: fetchFavorites,
    enabled: isAuthenticated && tab === "favorites",
  });

  const { data: history = [], isLoading: loadingHist } = useQuery({
    queryKey: ["history"],
    queryFn: fetchHistory,
    enabled: isAuthenticated && tab === "history",
  });

  if (!isAuthenticated || !user) {
    navigate("/auth");
    return null;
  }

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background"
    >
      <Navbar />

      <header className="pt-24 pb-8 bg-gradient-to-b from-surface to-background">
        <div className="mx-auto max-w-6xl px-4 md:px-6 flex items-center gap-5">
          <Avatar name={user.username} size={80} />
          <div className="flex-1 min-w-0">
            <h1 className="font-display font-extrabold text-2xl md:text-3xl">{user.username}</h1>
            <p className="text-sm text-muted-foreground font-body">{user.email}</p>
            {user.created_at && (
              <p className="text-xs text-muted-foreground/70 font-body mt-1">
                Membre depuis {new Date(user.created_at).toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}
              </p>
            )}
          </div>
          <button
            onClick={handleLogout}
            className="hidden md:inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-surface border border-border text-sm font-body font-semibold hover:border-destructive/40 text-destructive transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Déconnexion
          </button>
        </div>
      </header>

      <nav className="border-b border-border sticky top-16 bg-background/85 backdrop-blur-xl z-30">
        <div className="mx-auto max-w-6xl px-4 md:px-6 flex gap-1 overflow-x-auto">
          {tabs.map((t) => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={cn(
                  "relative inline-flex items-center gap-2 px-4 py-3 text-sm font-body font-semibold whitespace-nowrap transition-colors",
                  active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="w-4 h-4" />
                {t.label}
                {active && (
                  <motion.span
                    layoutId="profile-tab"
                    className="absolute inset-x-0 -bottom-px h-0.5 bg-primary"
                  />
                )}
              </button>
            );
          })}
        </div>
      </nav>

      <main className="mx-auto max-w-6xl px-4 md:px-6 py-8 pb-20">
        {tab === "watchlist" && (
          <div>
            <div className="flex gap-2 mb-6 overflow-x-auto">
              {subWatch.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setSubTab(s.id)}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs font-body font-semibold border transition-all",
                    subTab === s.id
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-surface border-border text-muted-foreground hover:border-primary/40",
                  )}
                >
                  {s.label}
                </button>
              ))}
            </div>
            {loadingWl ? (
              <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
            ) : (
              <AnimeGrid
                animes={Array.isArray(watchlist) ? watchlist : watchlist.items ?? []}
                emptyMessage="Watchlist vide"
                emptyHint="Ajoute des animes à ta watchlist pour les retrouver ici."
              />
            )}
          </div>
        )}

        {tab === "favorites" && (
          loadingFav ? (
            <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
          ) : (
            <AnimeGrid
              animes={Array.isArray(favorites) ? favorites : favorites.items ?? []}
              emptyMessage="Aucun favori"
              emptyHint="Marque des animés comme favoris pour les retrouver ici."
            />
          )
        )}

        {tab === "history" && (
          loadingHist ? (
            <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
          ) : (
            <div className="space-y-3">
              {(Array.isArray(history) ? history : history.items ?? []).length === 0 && (
                <p className="text-center text-muted-foreground font-body py-8">Aucun historique de visionnage.</p>
              )}
              {(Array.isArray(history) ? history : history.items ?? []).map((a: Record<string, unknown>, i: number) => (
                <div
                  key={String(a.id ?? i)}
                  className="flex gap-3 p-3 bg-surface rounded-xl border border-border"
                >
                  <div className="relative w-32 aspect-video rounded-lg overflow-hidden shrink-0">
                    {a.banner_url ? (
                      <img src={String(a.banner_url)} alt="" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full bg-surface-2" />
                    )}
                    <div className="absolute bottom-0 inset-x-0 h-1 bg-border-subtle">
                      <div
                        className="h-full bg-primary rounded-full"
                        style={{ width: `${Math.min(100, (Number(a.progress ?? 0) / Math.max(1, Number(a.duration ?? 1))) * 100)}%` }}
                      />
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-body font-semibold text-sm truncate">{String(a.anime_title ?? a.title ?? "Anime")}</p>
                    <p className="text-xs text-muted-foreground font-body">
                      {a.episode_number ? `Épisode ${a.episode_number}` : ""}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )
        )}

        {tab === "settings" && (
          <div className="max-w-lg space-y-6">
            <div className="bg-surface border border-border rounded-xl p-5">
              <h3 className="font-display font-bold mb-3">Informations du profil</h3>
              <div className="space-y-3 text-sm font-body">
                <div>
                  <label className="text-muted-foreground text-xs">Nom d'utilisateur</label>
                  <p className="font-semibold">{user.username}</p>
                </div>
                <div>
                  <label className="text-muted-foreground text-xs">Email</label>
                  <p className="font-semibold">{user.email}</p>
                </div>
                <div>
                  <label className="text-muted-foreground text-xs">Rôle</label>
                  <p className="font-semibold capitalize">{user.role}</p>
                </div>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm font-body font-semibold hover:bg-destructive/20 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Se déconnecter
            </button>
          </div>
        )}
      </main>

      <Footer />
    </motion.div>
  );
}
