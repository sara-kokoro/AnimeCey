/**
 * File d'attente des téléchargements hors ligne.
 * Un seul téléchargement actif à la fois : les autres restent en attente
 * et démarrent automatiquement quand le précédent est terminé.
 *
 * - Navigateur : l'épisode est écrit par morceaux de 4 Mo dans IndexedDB (jamais entier en mémoire).
 *   Si la connexion coupe, les morceaux déjà reçus sont gardés : « Réessayer » reprend où ça s'est arrêté.
 * - Application Android : la file est confiée au service natif (arrière-plan, notification, bouton Annuler).
 */
import { create } from "zustand";
import api from "@/api/axios";
import { getStreamUrl } from "@/api/episodes";
import { CHUNK_SIZE, deleteVideo, getPartial, hasVideo, putChunk, saveVideo } from "@/lib/offlineDb";
import { isNativeApp, nativePlugin, type NativeItem } from "@/lib/nativeDownloads";
import { RICHADS } from "@/config/ads";

export interface DownloadTask {
  episodeId: number;
  animeId: number;
  animeTitle: string;
  episodeNumber: number;
  seasonLabel: string;
  language: string;
  thumbnailUrl?: string;
  status: "pending" | "downloading" | "done" | "error";
  progress: number; // 0 à 100
  error?: string;
}

export type NewDownloadTask = Omit<DownloadTask, "status" | "progress" | "error">;

interface DownloadsState {
  tasks: DownloadTask[];
  adBatch: { id: number; items: NewDownloadTask[] } | null;
  requestDownloads: (items: NewDownloadTask[]) => Promise<number>;
  cancelAds: () => void;
  completeAds: (batchId: number) => Promise<number>;
  enqueue: (items: NewDownloadTask[]) => Promise<number>;
  retryTask: (episodeId: number) => void;
  removeTask: (episodeId: number) => void;
  clearFinished: () => void;
}

let pumping = false;
let nativeSynced = false;
let active: { episodeId: number; controller: AbortController } | null = null;
let batchSequence = 0;

export function cancelDownload(episodeId: number) {
  useDownloadsStore.getState().removeTask(episodeId);
}

export function requiredDownloadAds(count: number): number {
  return count <= 0 ? 0 : count === 1 ? 1 : 3;
}

export const useDownloadsStore = create<DownloadsState>((set, get) => ({
  tasks: [],
  adBatch: null,

  requestDownloads: async (items) => {
    if (get().adBatch) throw new Error("Une publicité de téléchargement est déjà ouverte.");
    if (!navigator.onLine) throw new Error("Reconnecte-toi pour télécharger des épisodes.");
    if (!RICHADS.vastTag.trim()) return get().enqueue(items); // pas de pub configurée : téléchargement direct
    // Réserver le lot avant les lectures IndexedDB pour éviter deux demandes simultanées.
    const id = ++batchSequence;
    set({ adBatch: { id, items: [] } });
    const fresh: NewDownloadTask[] = [];
    const seen = new Set<number>();
    try {
      for (const item of items) {
        if (seen.has(item.episodeId)) continue;
        seen.add(item.episodeId);
        if (get().tasks.some((t) => t.episodeId === item.episodeId && t.status !== "error")) continue;
        if (await hasVideo(item.episodeId)) continue;
        fresh.push(item);
      }
      if (get().adBatch?.id !== id) return 0;
      set({ adBatch: fresh.length ? { id, items: fresh } : null });
      return fresh.length;
    } catch (error) {
      if (get().adBatch?.id === id) set({ adBatch: null });
      throw error;
    }
  },
  cancelAds: () => set({ adBatch: null }),
  completeAds: async (batchId) => {
    const batch = get().adBatch;
    if (!batch || batch.id !== batchId) return 0;
    set({ adBatch: null });
    return get().enqueue(batch.items);
  },

  enqueue: async (items) => {
    const fresh: DownloadTask[] = [];
    for (const item of items) {
      if (await hasVideo(item.episodeId)) continue; // déjà dans le coffre hors ligne
      if (get().tasks.some((t) => t.episodeId === item.episodeId && t.status !== "error")) continue;
      if (fresh.some((t) => t.episodeId === item.episodeId)) continue;
      fresh.push({ ...item, status: "pending", progress: 0 });
    }
    if (fresh.length > 0) {
      set((s) => ({ tasks: [...s.tasks.filter((t) => !fresh.some((f) => f.episodeId === t.episodeId)), ...fresh] }));
      if (isNativeApp()) {
        await syncNativeDownloads();
        try {
          await nativePlugin().requestPermissions(); // notifications (Android 13+)
        } catch {
          /* refusées : le téléchargement fonctionne quand même, sans notification */
        }
        for (const t of fresh) startNative(set, t);
      } else {
        void navigator.storage?.persist?.().catch(() => undefined); // évite que le navigateur efface les épisodes
        void pump(set, get);
      }
    }
    return fresh.length;
  },

  retryTask: (episodeId) => {
    const task = get().tasks.find((t) => t.episodeId === episodeId);
    if (!task || task.status !== "error") return;
    patch(set, episodeId, { status: "pending", progress: task.progress, error: undefined });
    if (isNativeApp()) startNative(set, task);
    else void pump(set, get);
  },

  removeTask: (episodeId) => {
    const task = get().tasks.find((t) => t.episodeId === episodeId);
    if (isNativeApp()) {
      if (task && task.status !== "done") void nativePlugin().cancel({ episodeId }).catch(() => undefined);
    } else {
      if (active?.episodeId === episodeId) active.controller.abort();
      // téléchargement annulé : on efface aussi les morceaux déjà reçus
      if (task && task.status !== "done") void deleteVideo(episodeId).catch(() => undefined);
    }
    set((s) => ({ tasks: s.tasks.filter((t) => t.episodeId !== episodeId) }));
  },

  clearFinished: () => set((s) => ({ tasks: s.tasks.filter((t) => t.status === "pending" || t.status === "downloading") })),
}));

type Set = (fn: (s: DownloadsState) => Partial<DownloadsState>) => void;
type Get = () => DownloadsState;

function patch(set: Set, episodeId: number, patchObj: Partial<DownloadTask>) {
  set((s) => ({
    tasks: s.tasks.map((t) => (t.episodeId === episodeId ? { ...t, ...patchObj } : t)),
  }));
}

/* ───────── Application Android : service natif ───────── */

function startNative(set: Set, task: DownloadTask) {
  const { status: _s, progress: _p, error: _e, ...meta } = task;
  void _s;
  void _p;
  void _e;
  nativePlugin()
    .start({
      episodeId: task.episodeId,
      apiBase: String(api.defaults.baseURL ?? ""),
      meta: JSON.stringify(meta),
      title: `${task.animeTitle} — Épisode ${task.episodeNumber}`,
      subtitle: `${task.seasonLabel} · ${task.language}`.trim(),
    })
    .catch((err: unknown) =>
      patch(set, task.episodeId, {
        status: "error",
        error: err instanceof Error ? err.message : "Téléchargement impossible.",
      }),
    );
}

function applyNative(item: NativeItem) {
  const store = useDownloadsStore;
  const known = store.getState().tasks.find((t) => t.episodeId === item.episodeId);
  if (item.status === "cancelled") {
    if (known) store.setState((s) => ({ tasks: s.tasks.filter((t) => t.episodeId !== item.episodeId) }));
    return;
  }
  const status = item.status === "done" ? "done" : item.status === "error" ? "error" : item.status === "pending" ? "pending" : "downloading";
  if (known) {
    store.setState((s) => ({
      tasks: s.tasks.map((t) =>
        t.episodeId === item.episodeId
          ? { ...t, status, progress: item.status === "done" ? 100 : Math.round(item.progress), error: item.error }
          : t,
      ),
    }));
    return;
  }
  // téléchargement lancé avant la fermeture de l'app : on le réaffiche
  if (item.status === "done") return;
  let meta: Partial<NewDownloadTask> = {};
  try {
    meta = item.meta ? (JSON.parse(item.meta) as Partial<NewDownloadTask>) : {};
  } catch {
    /* meta illisible */
  }
  store.setState((s) => ({
    tasks: [
      ...s.tasks,
      {
        episodeId: item.episodeId,
        animeId: meta.animeId ?? 0,
        animeTitle: meta.animeTitle ?? "Épisode",
        episodeNumber: meta.episodeNumber ?? 0,
        seasonLabel: meta.seasonLabel ?? "",
        language: meta.language ?? "",
        thumbnailUrl: meta.thumbnailUrl,
        status,
        progress: Math.round(item.progress),
        error: item.error,
      },
    ],
  }));
}

/** À appeler au démarrage de l'app : relie la page au service natif (idempotent). Sans effet dans un navigateur. */
export async function syncNativeDownloads(): Promise<void> {
  if (nativeSynced || !isNativeApp()) return;
  nativeSynced = true;
  try {
    const plugin = nativePlugin();
    await plugin.addListener("downloadUpdate", applyNative);
    const { items } = await plugin.list();
    items.forEach(applyNative);
  } catch {
    nativeSynced = false;
  }
}

/* ───────── Navigateur : téléchargement par morceaux ───────── */

async function downloadChunked(task: DownloadTask, controller: AbortController, onProgress: (pct: number) => void) {
  const { signal } = controller;
  const stream = await getStreamUrl(task.episodeId, "servcey1");
  if (signal.aborted) return;
  if (stream.type !== "mp4" || !stream.url) {
    throw new Error("Cet épisode n'est pas téléchargeable hors ligne.");
  }

  // Reprise : les morceaux complets déjà enregistrés sont conservés.
  const partial = await getPartial(task.episodeId);
  let index = partial?.chunks ?? 0;
  let total = partial?.total ?? 0;
  let offset = index * CHUNK_SIZE;

  const res = await fetch(stream.url, { signal, headers: offset > 0 ? { Range: `bytes=${offset}-` } : undefined });
  if (offset > 0 && res.status !== 206) {
    // le serveur ignore la reprise et renvoie tout depuis le début : on repart de zéro
    await deleteVideo(task.episodeId);
    index = 0;
    offset = 0;
    total = 0;
  }
  if (!res.ok || !res.body) throw new Error(`Serveur indisponible (HTTP ${res.status}).`);

  const length = Number(res.headers.get("Content-Length") ?? 0);
  if (length > 0) total = offset + length;

  const base = {
    episodeId: task.episodeId,
    animeId: task.animeId,
    animeTitle: task.animeTitle,
    episodeNumber: task.episodeNumber,
    seasonLabel: task.seasonLabel,
    language: task.language,
    thumbnailUrl: task.thumbnailUrl,
  };
  const writeMeta = (complete: boolean, size: number) =>
    saveVideo({ ...base, size, total: total || undefined, chunks: index, complete, downloadedAt: Date.now() });

  await writeMeta(false, offset);

  const reader = res.body.getReader();
  let pending: Blob = new Blob([]); // octets reçus, pas encore enregistrés (< 4 Mo + une lecture)
  let received = offset;
  for (;;) {
    const { done, value } = await reader.read();
    if (value) {
      pending = new Blob([pending, value]);
      received += value.length;
      while (pending.size >= CHUNK_SIZE) {
        await putChunk(task.episodeId, index, pending.slice(0, CHUNK_SIZE));
        pending = pending.slice(CHUNK_SIZE);
        index += 1;
        await writeMeta(false, index * CHUNK_SIZE);
      }
      if (total > 0) onProgress(Math.min(99, Math.round((received / total) * 100)));
    }
    if (done) break;
  }
  if (signal.aborted) return;

  if (total > 0 && received < total) {
    throw new Error("Connexion interrompue. Appuie sur « Réessayer » pour reprendre.");
  }
  if (pending.size > 0) {
    await putChunk(task.episodeId, index, pending);
    index += 1;
  }
  await writeMeta(true, received);
}

async function pump(set: Set, get: Get) {
  if (pumping) return;
  pumping = true;
  try {
    for (;;) {
      const next = get().tasks.find((t) => t.status === "pending");
      if (!next) break;
      const controller = new AbortController();
      active = { episodeId: next.episodeId, controller };
      patch(set, next.episodeId, { status: "downloading", error: undefined });
      try {
        await downloadChunked(next, controller, (progress) => patch(set, next.episodeId, { progress }));
        if (controller.signal.aborted) continue;
        patch(set, next.episodeId, { status: "done", progress: 100 });
      } catch (err) {
        if (controller.signal.aborted) continue;
        const message = err instanceof Error ? err.message : "Téléchargement interrompu.";
        patch(set, next.episodeId, { status: "error", error: message });
      } finally {
        if (active?.controller === controller) active = null;
      }
    }
  } finally {
    pumping = false;
  }
}
