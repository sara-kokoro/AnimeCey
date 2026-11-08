import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Check, ChevronRight, Folder, Play, Trash2, X } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { OfflineVideo } from "@/lib/offlineDb";
import { getCover } from "@/lib/covers";
import { seasonNumberOf } from "@/lib/downloadOrder";

function fmtSize(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} Go`;
  if (bytes >= 1_000_000) return `${Math.round(bytes / 1_000_000)} Mo`;
  return `${Math.round(bytes / 1024)} Ko`;
}

const plural = (n: number, one: string, many: string) => `${n} ${n > 1 ? many : one}`;

interface SeasonGroup {
  label: string;
  videos: OfflineVideo[];
}
interface AnimeGroup {
  animeId: number;
  title: string;
  seasons: SeasonGroup[];
  videos: OfflineVideo[];
  size: number;
}

function group(videos: OfflineVideo[]): AnimeGroup[] {
  const byAnime = new Map<number, OfflineVideo[]>();
  for (const v of videos) byAnime.set(v.animeId, [...(byAnime.get(v.animeId) ?? []), v]);
  return [...byAnime.entries()]
    .map(([animeId, vids]) => {
      const bySeason = new Map<string, OfflineVideo[]>();
      for (const v of vids) bySeason.set(v.seasonLabel || "Saison 1", [...(bySeason.get(v.seasonLabel || "Saison 1") ?? []), v]);
      const seasons = [...bySeason.entries()]
        .map(([label, sv]) => ({ label, videos: [...sv].sort((a, b) => a.episodeNumber - b.episodeNumber) }))
        .sort((a, b) => seasonNumberOf(a.label) - seasonNumberOf(b.label) || a.label.localeCompare(b.label));
      return {
        animeId,
        title: vids[0].animeTitle,
        seasons,
        videos: vids,
        size: vids.reduce((n, v) => n + v.size, 0),
      };
    })
    .sort((a, b) => a.title.localeCompare(b.title, "fr"));
}

/** Vignette : affiche TMDB enregistrée, sinon la vignette d'un épisode, sinon une icône. */
function Cover({ animeId, fallback, className = "" }: { animeId: number; fallback?: string; className?: string }) {
  const [src] = useState(() => getCover(animeId) ?? fallback ?? null);
  return (
    <div className={`relative bg-foreground/5 overflow-hidden ${className}`}>
      {src ? (
        <img src={src} alt="" loading="lazy" decoding="async" className="absolute inset-0 w-full h-full object-cover" />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
          <Folder className="w-7 h-7" />
        </div>
      )}
    </div>
  );
}

interface Props {
  videos: OfflineVideo[];
  playingId?: number;
  onPlay: (v: OfflineVideo) => void;
  /** Supprime ces épisodes (déjà confirmé par l'utilisateur). */
  onDelete: (episodeIds: number[]) => Promise<void>;
}

export function DownloadsLibrary({ videos, playingId, onPlay, onDelete }: Props) {
  const groups = useMemo(() => group(videos), [videos]);
  const [animeId, setAnimeId] = useState<number | null>(null);
  const [season, setSeason] = useState<string | null>(null);
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirm, setConfirm] = useState<number[] | null>(null);
  const [busy, setBusy] = useState(false);

  const anime = animeId === null ? null : (groups.find((g) => g.animeId === animeId) ?? null);
  const multiSeason = !!anime && anime.seasons.length > 1;
  const seasonGroup = anime ? (anime.seasons.find((s) => s.label === season) ?? (multiSeason ? null : anime.seasons[0])) : null;

  // Un dossier vide disparaît : on remonte d'un niveau.
  useEffect(() => {
    if (animeId !== null && !anime) {
      setAnimeId(null);
      setSeason(null);
    } else if (anime && season && !anime.seasons.some((s) => s.label === season)) {
      setSeason(null);
    }
  }, [anime, animeId, season]);

  // La sélection ne garde que des épisodes qui existent encore.
  useEffect(() => {
    setSelected((cur) => {
      const ids = new Set(videos.map((v) => v.episodeId));
      const next = new Set([...cur].filter((id) => ids.has(id)));
      return next.size === cur.size ? cur : next;
    });
  }, [videos]);

  const level: "anime" | "season" | "episodes" = !anime ? "anime" : seasonGroup ? "episodes" : "season";

  const stopSelecting = () => {
    setSelecting(false);
    setSelected(new Set());
  };

  const toggle = (ids: number[]) =>
    setSelected((cur) => {
      const next = new Set(cur);
      const all = ids.every((id) => next.has(id));
      ids.forEach((id) => (all ? next.delete(id) : next.add(id)));
      return next;
    });

  const back = () => {
    stopSelecting();
    if (level === "episodes" && multiSeason) setSeason(null);
    else {
      setAnimeId(null);
      setSeason(null);
    }
  };

  const doDelete = async () => {
    if (!confirm) return;
    setBusy(true);
    try {
      await onDelete(confirm);
    } finally {
      setBusy(false);
      setConfirm(null);
      stopSelecting();
    }
  };

  const confirmSize = confirm ? videos.filter((v) => confirm.includes(v.episodeId)).reduce((n, v) => n + v.size, 0) : 0;

  const visible: OfflineVideo[] = level === "episodes" && seasonGroup ? seasonGroup.videos : [];
  const allIdsHere =
    level === "anime" ? videos.map((v) => v.episodeId) : level === "season" && anime ? anime.videos.map((v) => v.episodeId) : visible.map((v) => v.episodeId);

  return (
    <div>
      {/* Fil d'Ariane + actions */}
      <div className="flex items-center gap-2 min-h-10">
        {level !== "anime" && (
          <button
            onClick={back}
            aria-label="Retour"
            className="shrink-0 w-10 h-10 rounded-full border border-border flex items-center justify-center hover:border-primary/50"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
        )}
        <div className="min-w-0 flex-1 flex items-center gap-1 text-sm text-muted-foreground">
          {level === "anime" ? (
            <span className="font-display font-bold text-lg text-foreground">Mes animés</span>
          ) : (
            <>
              <button onClick={() => { stopSelecting(); setAnimeId(null); setSeason(null); }} className="hover:text-foreground">
                Téléchargements
              </button>
              <ChevronRight className="w-4 h-4 shrink-0" />
              {level === "episodes" && multiSeason ? (
                <>
                  <button onClick={() => { stopSelecting(); setSeason(null); }} className="truncate hover:text-foreground">
                    {anime?.title}
                  </button>
                  <ChevronRight className="w-4 h-4 shrink-0" />
                  <span className="truncate font-semibold text-foreground">{seasonGroup?.label}</span>
                </>
              ) : (
                <span className="truncate font-semibold text-foreground">{anime?.title}</span>
              )}
            </>
          )}
        </div>
        {selecting ? (
          <button onClick={stopSelecting} className="shrink-0 h-10 px-4 rounded-full border border-border text-sm font-semibold">
            Terminer
          </button>
        ) : (
          <button
            onClick={() => setSelecting(true)}
            className="shrink-0 h-10 px-4 rounded-full border border-border text-sm font-semibold hover:border-primary/50"
          >
            Sélectionner
          </button>
        )}
      </div>

      {/* Niveau 1 : un dossier par animé */}
      {level === "anime" && (
        <ul className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3">
          {groups.map((g) => {
            const ids = g.videos.map((v) => v.episodeId);
            const checked = ids.every((id) => selected.has(id));
            return (
              <li key={g.animeId}>
                <button
                  onClick={() => (selecting ? toggle(ids) : (setAnimeId(g.animeId), setSeason(null)))}
                  className={`group block w-full text-left rounded-2xl overflow-hidden bg-surface border transition-colors ${
                    checked ? "border-primary" : "border-border-subtle hover:border-primary/40"
                  }`}
                >
                  <Cover animeId={g.animeId} fallback={g.videos[0]?.thumbnailUrl} className="aspect-video" />
                  <div className="p-2.5">
                    <p className="font-display font-bold text-sm leading-snug line-clamp-2">{g.title}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {plural(g.videos.length, "épisode", "épisodes")} · {fmtSize(g.size)}
                    </p>
                  </div>
                </button>
                {selecting && (
                  <p className={`mt-1 text-xs font-semibold ${checked ? "text-primary" : "text-muted-foreground"}`}>
                    {checked ? "✓ Sélectionné" : "Toucher pour choisir"}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {/* Niveau 2 : les saisons d'un animé */}
      {level === "season" && anime && (
        <ul className="mt-4 grid gap-2.5">
          {anime.seasons.map((s) => {
            const ids = s.videos.map((v) => v.episodeId);
            const checked = ids.every((id) => selected.has(id));
            return (
              <li key={s.label}>
                <button
                  onClick={() => (selecting ? toggle(ids) : setSeason(s.label))}
                  className={`flex w-full items-center gap-3 rounded-2xl bg-surface border p-3 text-left transition-colors ${
                    checked ? "border-primary" : "border-border-subtle hover:border-primary/40"
                  }`}
                >
                  <span className="shrink-0 w-12 h-12 rounded-xl bg-primary/15 text-primary flex items-center justify-center">
                    {selecting && checked ? <Check className="w-6 h-6" /> : <Folder className="w-6 h-6" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-display font-bold">{s.label}</span>
                    <span className="block text-xs text-muted-foreground">
                      {plural(s.videos.length, "épisode", "épisodes")} · {fmtSize(s.videos.reduce((n, v) => n + v.size, 0))}
                    </span>
                  </span>
                  <ChevronRight className="w-5 h-5 text-muted-foreground" />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {/* Niveau 3 : les épisodes */}
      {level === "episodes" && (
        <ul className="mt-4 space-y-2.5">
          {visible.map((v) => {
            const checked = selected.has(v.episodeId);
            return (
              <li
                key={v.episodeId}
                className={`flex items-center gap-3 rounded-2xl bg-surface border p-2.5 transition-colors ${
                  checked ? "border-primary" : "border-border-subtle hover:border-primary/40"
                }`}
              >
                {selecting && (
                  <button
                    onClick={() => toggle([v.episodeId])}
                    aria-label={checked ? "Désélectionner" : "Sélectionner"}
                    className={`shrink-0 w-7 h-7 rounded-full border-2 flex items-center justify-center ${
                      checked ? "bg-primary border-primary text-primary-foreground" : "border-border"
                    }`}
                  >
                    {checked && <Check className="w-4 h-4" />}
                  </button>
                )}
                <button
                  onClick={() => (selecting ? toggle([v.episodeId]) : onPlay(v))}
                  aria-label={`Regarder l'épisode ${v.episodeNumber}`}
                  className="relative shrink-0 w-24 sm:w-28 aspect-video rounded-xl overflow-hidden bg-foreground/5"
                >
                  {v.thumbnailUrl ? (
                    <img src={v.thumbnailUrl} alt="" className="w-full h-full object-cover" loading="lazy" decoding="async" />
                  ) : (
                    <Cover animeId={v.animeId} className="absolute inset-0" />
                  )}
                  {!selecting && (
                    <span className="absolute inset-0 m-auto w-8 h-8 rounded-full bg-primary/90 text-primary-foreground flex items-center justify-center">
                      <Play className="w-4 h-4 fill-current" />
                    </span>
                  )}
                </button>
                <div className="min-w-0 flex-1">
                  <p className="font-display text-[15px] font-bold leading-snug">Épisode {v.episodeNumber}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {v.language} · {fmtSize(v.size)}
                  </p>
                </div>
                {!selecting && (
                  <div className="shrink-0 flex items-center gap-1.5">
                    <button
                      onClick={() => onPlay(v)}
                      className="inline-flex items-center justify-center gap-1.5 h-10 px-4 rounded-full bg-primary text-primary-foreground text-sm font-bold hover:bg-primary-dim transition-colors"
                    >
                      <Play className="w-4 h-4" />
                      <span className="hidden sm:inline">Regarder</span>
                    </button>
                    <button
                      onClick={() => setConfirm([v.episodeId])}
                      aria-label="Supprimer"
                      className="w-10 h-10 rounded-full border border-border flex items-center justify-center text-muted-foreground hover:text-highlight hover:border-highlight/60 transition-colors"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                    {playingId === v.episodeId && <Check className="w-5 h-5 text-primary" />}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {/* Barre d'actions de la sélection */}
      {selecting && (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-border-subtle bg-background/95 backdrop-blur px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          <div className="mx-auto max-w-5xl flex items-center gap-2">
            <button
              onClick={() => toggle(allIdsHere)}
              className="h-11 px-4 rounded-full border border-border text-sm font-semibold"
            >
              {allIdsHere.length > 0 && allIdsHere.every((id) => selected.has(id)) ? "Tout désélectionner" : "Tout sélectionner"}
            </button>
            <span className="flex-1 text-center text-sm text-muted-foreground">
              {selected.size > 0 ? plural(selected.size, "épisode choisi", "épisodes choisis") : "Rien de choisi"}
            </span>
            <button
              disabled={selected.size === 0}
              onClick={() => setConfirm([...selected])}
              className="h-11 px-5 rounded-full bg-highlight text-white text-sm font-bold disabled:opacity-40 inline-flex items-center gap-2"
            >
              <Trash2 className="w-4 h-4" /> Supprimer
            </button>
          </div>
        </div>
      )}
      {selecting && <div className="h-20" aria-hidden />}

      {/* Confirmation */}
      <AlertDialog open={confirm !== null} onOpenChange={(o) => !o && !busy && setConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirm && confirm.length > 1 ? `Supprimer ${confirm.length} épisodes ?` : "Supprimer cet épisode ?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirm && confirm.length > 1
                ? `Ces épisodes (${fmtSize(confirmSize)}) seront effacés de ton téléphone. Tu pourras les télécharger à nouveau.`
                : `Cet épisode (${fmtSize(confirmSize)}) sera effacé de ton téléphone. Tu pourras le télécharger à nouveau.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>
              <X className="w-4 h-4 mr-1" /> Annuler
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={busy}
              onClick={(e) => {
                e.preventDefault();
                void doDelete();
              }}
            >
              {busy ? "Suppression…" : "Supprimer"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
