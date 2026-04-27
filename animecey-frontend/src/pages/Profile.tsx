import { useState } from "react";
import { motion } from "framer-motion";
import { Settings, BookOpen, Heart, History as HistoryIcon, LogOut, Trash2 } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { Avatar } from "@/components/comments/Avatar";
import { AnimeGrid } from "@/components/anime/AnimeGrid";
import { animes } from "@/data/mock";
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
  const [tab, setTab] = useState<(typeof tabs)[number]["id"]>("watchlist");
  const [subTab, setSubTab] = useState<(typeof subWatch)[number]["id"]>("watching");

  const username = "AnimeFan";
  const watchlist = animes.slice(0, 6);
  const favorites = animes.slice(2, 8);
  const history = animes.slice(0, 5);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background"
    >
      <Navbar />

      {/* Profile header */}
      <header className="pt-24 pb-8 bg-gradient-to-b from-surface to-background">
        <div className="mx-auto max-w-6xl px-4 md:px-6 flex items-center gap-5">
          <Avatar name={username} size={80} />
          <div className="flex-1 min-w-0">
            <h1 className="font-display font-extrabold text-2xl md:text-3xl">{username}</h1>
            <p className="text-sm text-muted-foreground font-body">animefan@animecey.app</p>
            <p className="text-xs text-muted-foreground/70 font-body mt-1">Membre depuis avril 2024</p>
          </div>
          <button className="hidden md:inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-surface border border-border text-sm font-body font-semibold hover:border-primary/40 transition-colors">
            <Settings className="w-4 h-4" />
            Modifier
          </button>
        </div>
      </header>

      {/* Tabs */}
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
            <AnimeGrid animes={watchlist} />
          </div>
        )}

        {tab === "favorites" && <AnimeGrid animes={favorites} />}

        {tab === "history" && (
          <div className="space-y-3">
            {history.map((a, i) => (
              <div
                key={a.id}
                className="flex gap-3 p-3 bg-surface rounded-xl border border-border"
              >
                <div className="relative w-32 aspect-video rounded-lg overflow-hidden shrink-0">
                  <img src={a.banner_url} alt={a.title} className="w-full h-full object-cover" />
                  <div className="absolute bottom-0 inset-x-0 h-1 bg-border-subtle">
                    <div
                      className="h-full bg-primary"
                      style={{ width: `${30 + i * 15}%` }}
                    />
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-body font-semibold text-sm">{a.title}</p>
                  <p className="text-xs text-muted-foreground font-body mt-0.5">
                    Saison 1 — Épisode {i + 3}
                  </p>
                  <button className="mt-2 inline-flex items-center gap-1.5 px-3 py-1 rounded-md bg-primary text-primary-foreground text-xs font-body font-semibold">
                    Reprendre
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "settings" && (
          <div className="max-w-xl space-y-8">
            <section>
              <h2 className="font-display font-bold text-lg mb-3">Informations</h2>
              <div className="space-y-3">
                <div>
                  <label className="text-xs uppercase tracking-wider font-body font-semibold text-muted-foreground">
                    Pseudo
                  </label>
                  <input defaultValue={username} className="mt-1 w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm font-body focus:outline-none focus:border-primary transition-colors" />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider font-body font-semibold text-muted-foreground">
                    Email
                  </label>
                  <input defaultValue="animefan@animecey.app" className="mt-1 w-full bg-surface border border-border rounded-lg px-3 py-2 text-sm font-body focus:outline-none focus:border-primary transition-colors" />
                </div>
                <button className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-body font-semibold">
                  Sauvegarder
                </button>
              </div>
            </section>

            <section>
              <h2 className="font-display font-bold text-lg mb-3">Notifications</h2>
              <label className="flex items-center justify-between p-3 bg-surface border border-border rounded-lg">
                <div>
                  <p className="font-body font-semibold text-sm">Notifications push</p>
                  <p className="text-xs text-muted-foreground font-body">
                    Recevoir les alertes des nouveaux épisodes
                  </p>
                </div>
                <input type="checkbox" defaultChecked className="w-5 h-5 accent-primary" />
              </label>
            </section>

            <section>
              <h2 className="font-display font-bold text-lg mb-3">Compte</h2>
              <div className="flex flex-wrap gap-2">
                <button className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-surface border border-border text-sm font-body font-semibold hover:border-primary/40 transition-colors">
                  <LogOut className="w-4 h-4" />
                  Se déconnecter
                </button>
                <button className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-surface border border-destructive/40 text-destructive text-sm font-body font-semibold hover:bg-destructive/10 transition-colors">
                  <Trash2 className="w-4 h-4" />
                  Supprimer mon compte
                </button>
              </div>
            </section>
          </div>
        )}
      </main>

      <Footer />
    </motion.div>
  );
}