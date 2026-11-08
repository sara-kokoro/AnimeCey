import { useCallback, useEffect, useRef, useState } from "react";
import { Toaster, toast } from "sonner";
import { CloudDownload, HeartHandshake, RefreshCw, WifiOff, X } from "lucide-react";
import { DownloadsLibrary } from "@/components/downloads/DownloadsLibrary";
import { ServCeyPlayer } from "@/components/player/ServCeyPlayer";
import { DonateCard } from "@/components/donate/DonateCard";
import { fromNative, type OfflineVideo } from "@/lib/offlineDb";
import { nativeFileUrl, nativePlugin, type NativeItem } from "@/lib/nativeDownloads";

/* eslint-disable @typescript-eslint/no-explicit-any */
const SITE = "https://www.magi-stream.online/";
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

/** Dernière pub enregistrée par l'application (affichée même sans connexion). */
function OfflineAd() {
  let data: any = null;
  try {
    data = JSON.parse(nat()?.getOfflineAd?.() || "null");
  } catch {
    /* pas de pub enregistrée */
  }
  const ad = data?.ad;
  const contact = data?.contact ?? { telegram: "https://t.me/zgatez", telegram_name: "@zgatez", email: "antiflix9@gmail.com" };
  const open = (u?: string) => u && nat()?.openExternal?.(u);

  if (ad?.image) {
    return (
      <div className="mt-4 rounded-2xl overflow-hidden border border-border-subtle bg-surface">
        <p className="px-3 pt-2 text-[10px] text-muted-foreground">Publicité</p>
        <img src={ad.image} alt="Publicité" className="w-full max-h-64 object-contain bg-black" onClick={() => open(ad.link)} />
        {ad.text && <p className="m-3 pl-3 border-l-2 border-highlight text-sm whitespace-pre-line">{ad.text}</p>}
        {ad.button_text && ad.button_link && (
          <button
            onClick={() => open(ad.button_link)}
            className="m-3 mt-0 w-[calc(100%-1.5rem)] rounded-full bg-highlight text-white font-semibold py-2.5 text-sm"
          >
            {ad.button_text}
          </button>
        )}
      </div>
    );
  }
  return (
    <button
      onClick={() => open(contact.telegram)}
      className="mt-4 w-full text-left rounded-2xl border border-dashed border-border-subtle bg-surface p-4"
    >
      <b className="block text-sm">Affiche ta pub ici</b>
      <span className="block mt-1 text-xs text-muted-foreground">
        Augmente ta visibilité avec la pub Magi-Stream. Contact : {contact.telegram_name} · {contact.email}
      </span>
    </button>
  );
}

export function OfflineApp() {
  const [videos, setVideos] = useState<OfflineVideo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState<OfflineVideo | null>(null);
  const donateRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async (attempt = 0): Promise<void> => {
    try {
      const items = await readItems();
      setVideos(
        items
          .filter((i) => i.status === "done" && i.path)
          .map(fromNative)
          .sort((a, b) => b.downloadedAt - a.downloadedAt),
      );
      setError(null);
    } catch (e) {
      // Le module natif peut mettre un instant à être prêt au démarrage de la page.
      if (attempt < 8) {
        setTimeout(() => void load(attempt + 1), 400);
        return;
      }
      setVideos([]);
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
    // Dès que la connexion revient, on retourne sur le site.
    const back = () => {
      location.href = SITE;
    };
    window.addEventListener("online", back);
    return () => window.removeEventListener("online", back);
  }, [load]);

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

  const totalSize = (videos ?? []).reduce((n, v) => n + v.size, 0);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-5xl px-4 md:px-6 pb-10" style={{ paddingTop: "max(1.25rem, env(safe-area-inset-top))" }}>
        <div className="flex items-center justify-between gap-3">
          <h1 className="font-display font-extrabold text-2xl md:text-3xl">Mes Téléchargements</h1>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-primary/15 text-primary">
            <WifiOff className="w-3.5 h-3.5" /> Hors ligne
          </span>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Tu es hors connexion : regarde tes épisodes téléchargés, ou reconnecte-toi pour retrouver tout le catalogue.
          {videos && videos.length > 0 && ` · ${videos.length} épisode${videos.length > 1 ? "s" : ""} · ${fmtSize(totalSize)}`}
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            onClick={() => {
              location.href = SITE;
            }}
            className="inline-flex items-center gap-2 h-11 px-5 rounded-full bg-primary text-primary-foreground text-sm font-bold"
          >
            <RefreshCw className="w-4 h-4" /> Réessayer la connexion
          </button>
          <button
            onClick={() => donateRef.current?.scrollIntoView({ behavior: "smooth" })}
            className="inline-flex items-center gap-2 h-11 px-5 rounded-full bg-surface border border-border-subtle text-sm font-bold"
          >
            <HeartHandshake className="w-4 h-4" /> Faire un don
          </button>
        </div>

        {playing?.filePath && (
          <div className="mt-6">
            <div className="relative w-full aspect-video bg-black rounded-2xl overflow-hidden ring-1 ring-border">
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
                className="shrink-0 inline-flex items-center gap-1.5 h-9 px-4 rounded-full bg-surface border border-border-subtle text-sm font-semibold"
              >
                <X className="w-4 h-4" /> Fermer
              </button>
            </div>
          </div>
        )}

        <section className="mt-8">
          {videos === null ? (
            <p className="text-sm text-muted-foreground">Lecture des téléchargements…</p>
          ) : videos.length === 0 ? (
            <div className="flex flex-col items-center text-center rounded-3xl border border-dashed border-border-subtle bg-surface/50 px-6 py-14">
              <div className="w-16 h-16 rounded-full bg-primary/15 text-primary flex items-center justify-center">
                <CloudDownload className="w-8 h-8" />
              </div>
              <h2 className="mt-4 font-display font-bold text-lg">Aucun épisode téléchargé</h2>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                {error
                  ? `Impossible de lire les téléchargements : ${error}`
                  : "Quand tu auras une connexion, touche « Hors ligne » sur la page d'un épisode pour le garder dans l'application."}
              </p>
            </div>
          ) : (
            <DownloadsLibrary videos={videos} playingId={playing?.episodeId} onPlay={(v) => setPlaying(v)} onDelete={removeMany} />
          )}
        </section>

        <OfflineAd />

        <div ref={donateRef} className="mt-8">
          <DonateCard />
        </div>
      </div>
      <Toaster theme="dark" position="top-center" />
    </div>
  );
}
