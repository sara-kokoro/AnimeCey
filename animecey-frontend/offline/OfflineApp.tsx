/**
 * Page « Hors connexion » de l'application Android : copie de la page « Mes téléchargements » du site
 * (src/pages/Telechargements.tsx), avec la même mise en page, les mêmes textes et les mêmes composants.
 * Seules différences : les épisodes sont lus par le module natif, et les liens ouvrent le site.
 */
import { useCallback, useEffect, useState } from "react";
import { Toaster as Sonner, toast } from "sonner";
import { motion } from "framer-motion";
import { CloudDownload, HeartHandshake, Wifi, WifiOff, X } from "lucide-react";
import { ServCeyPlayer } from "@/components/player/ServCeyPlayer";
import { DownloadsLibrary } from "@/components/downloads/DownloadsLibrary";
import { DonateCard } from "@/components/donate/DonateCard";
import { fromNative, type OfflineVideo } from "@/lib/offlineDb";
import { nativeFileUrl, nativePlugin, type NativeItem } from "@/lib/nativeDownloads";
import { OfflineAdSlot, OfflineBottomNav, OfflineFooter, OfflineNavbar, SITE, SiteLink } from "./OfflineChrome";

/* eslint-disable @typescript-eslint/no-explicit-any */
const nat = (): any => (window as any).MagiNative;

function fmtSize(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} Go`;
  if (bytes >= 1_000_000) return `${Math.round(bytes / 1_000_000)} Mo`;
  return `${Math.round(bytes / 1024)} Ko`;
}

/** Épisodes terminés, lus par le module natif (MagiNative d'abord, plugin Capacitor en secours). */
async function readItems(): Promise<NativeItem[]> {
  const n = nat();
  if (n?.list) return JSON.parse(n.list()) as NativeItem[];
  const c = (window as any).Capacitor;
  const plugin = c?.Plugins?.MagiDownloader ?? c?.registerPlugin?.("MagiDownloader");
  if (plugin) {
    const r = await plugin.list();
    return ((r.items ?? []) as NativeItem[]).filter((i) => i.status === "done" && i.path);
  }
  throw new Error("module natif indisponible");
}

export function OfflineApp() {
  // null = lecture en cours (on n'affiche rien plutôt qu'un faux « Aucun téléchargement »)
  const [videos, setVideos] = useState<OfflineVideo[] | null>(null);
  const [playing, setPlaying] = useState<OfflineVideo | null>(null);
  const [online, setOnline] = useState(typeof navigator === "undefined" ? true : navigator.onLine);

  const load = useCallback(async (attempt = 0): Promise<void> => {
    try {
      const items = await readItems();
      setVideos(
        items
          .filter((i) => i.status === "done" && i.path)
          .map(fromNative)
          .sort((a, b) => b.downloadedAt - a.downloadedAt),
      );
    } catch (e) {
      // Le module natif peut mettre un instant à être prêt au démarrage de la page.
      if (attempt < 8) {
        setTimeout(() => void load(attempt + 1), 400);
        return;
      }
      console.error("Lecture des téléchargements impossible :", e);
      setVideos([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const on = () => {
      setOnline(true);
      // Dès que la connexion revient, on retourne sur le site.
      location.href = SITE;
    };
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  const play = (video: OfflineVideo) => {
    setPlaying(video);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Bouton retour d'Android : ferme le lecteur au lieu de quitter la page.
  useEffect(() => {
    if (!playing) return;
    history.pushState({ p: 1 }, "");
    const onPop = () => setPlaying(null);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [playing]);

  const closePlayer = () => {
    setPlaying(null);
    try {
      history.back();
    } catch {
      /* ignoré */
    }
  };

  const removeMany = async (ids: number[]) => {
    try {
      for (const id of ids) {
        await nativePlugin().remove({ episodeId: id });
        if (playing?.episodeId === id) setPlaying(null);
      }
      toast.success(ids.length > 1 ? `${ids.length} épisodes supprimés` : "Épisode supprimé");
    } catch {
      toast.error("Suppression impossible pour le moment.");
    }
    await load();
  };

  const list = videos ?? [];
  const totalSize = list.reduce((acc, v) => acc + v.size, 0);

  return (
    <>
      <motion.div
        initial={false}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="min-h-screen bg-background"
      >
        <OfflineNavbar />

        <div className="pt-20 pb-10 mx-auto max-w-5xl px-4 md:px-6">
          <div className="flex items-center justify-between gap-3">
            <h1 className="font-display font-extrabold text-2xl md:text-3xl">Mes Téléchargements</h1>
            <span
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold ${
                online ? "bg-foreground/10 text-muted-foreground" : "bg-primary/15 text-primary"
              }`}
            >
              {online ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
              {online ? "En ligne" : "Hors ligne"}
            </span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Tes épisodes sont gardés dans l'application : regarde-les même sans internet.
            {list.length > 0 && ` · ${list.length} épisode${list.length > 1 ? "s" : ""} · ${fmtSize(totalSize)}`}
          </p>

          <button
            onClick={() => {
              location.href = SITE;
            }}
            style={{ marginTop: 12, height: 40, padding: "0 20px", borderRadius: 999, border: 0, background: "#f97316", color: "#111", fontWeight: 700, fontSize: 14 }}
          >
            Réessayer la connexion
          </button>

          <OfflineAdSlot className="mt-4" />

          <DonateCard compact className="mt-4" />

          {/* Lecteur hors ligne */}
          {playing?.filePath && (
            <div className="mt-6">
              <div className="relative w-full aspect-video bg-background rounded-2xl overflow-hidden ring-1 ring-border">
                <ServCeyPlayer
                  key={`offline-${playing.episodeId}`}
                  src={nativeFileUrl(playing.filePath)}
                  title={playing.animeTitle}
                  subtitle={`${playing.seasonLabel} — Épisode ${playing.episodeNumber} · ${playing.language}`}
                  storageKey={`offline-${playing.episodeId}`}
                />
              </div>
              <div className="mt-3 flex items-center justify-between gap-3">
                <p className="font-body font-semibold text-sm truncate">
                  {playing.animeTitle} — Épisode {playing.episodeNumber}
                </p>
                <button
                  onClick={closePlayer}
                  className="shrink-0 inline-flex items-center gap-1.5 h-9 px-4 rounded-full bg-surface border border-border-subtle text-sm font-semibold hover:bg-surface-2 transition-colors"
                >
                  <X className="w-4 h-4" />
                  Fermer
                </button>
              </div>
            </div>
          )}

          {/* Soutien */}
          <SiteLink
            to="/don"
            className="mt-8 flex items-center gap-3 rounded-2xl border border-primary/40 bg-primary/10 p-3.5 hover:bg-primary/15 transition-colors"
          >
            <span className="shrink-0 w-11 h-11 rounded-xl bg-primary text-primary-foreground flex items-center justify-center">
              <HeartHandshake className="w-5 h-5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-display font-bold text-sm">Soutiens Magi-Stream</span>
              <span className="block text-xs text-muted-foreground">
                Ton don garde le service gratuit, avec plus d'animés et des serveurs rapides.
              </span>
            </span>
          </SiteLink>

          {/* Bibliothèque hors ligne */}
          <section className="mt-8">
            {videos === null ? null : videos.length === 0 ? (
              <div className="mt-6 flex flex-col items-center text-center rounded-3xl border border-dashed border-border-subtle bg-surface/50 px-6 py-14">
                <div className="w-16 h-16 rounded-full bg-primary/15 text-primary flex items-center justify-center">
                  <CloudDownload className="w-8 h-8" />
                </div>
                <h2 className="mt-4 font-display font-bold text-lg">Aucun téléchargement</h2>
                <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                  Sur la page d'un épisode, touche « Hors ligne » pour le garder dans l'application et le regarder sans
                  internet.
                </p>
                <SiteLink
                  to="/catalogue"
                  className="mt-5 inline-flex items-center justify-center rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary-dim"
                >
                  Parcourir le catalogue
                </SiteLink>
              </div>
            ) : (
              <DownloadsLibrary videos={videos} playingId={playing?.episodeId} onPlay={play} onDelete={removeMany} />
            )}
          </section>
        </div>

        <OfflineFooter />
      </motion.div>

      {/* Même enveloppe que le site (pb-20 sur mobile pour laisser la place à la navigation du bas) */}
      <div className="pb-20 md:pb-0" aria-hidden />
      <OfflineBottomNav />
      <Sonner
        className="toaster group"
        toastOptions={{
          classNames: {
            toast:
              "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
            description: "group-[.toast]:text-muted-foreground",
            actionButton: "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
            cancelButton: "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
          },
        }}
      />
    </>
  );
}
