/**
 * File d'attente des téléchargements hors ligne.
 * Un seul téléchargement actif à la fois : les autres restent en attente
 * et démarrent automatiquement quand le précédent est terminé.
 */
import { create } from "zustand";
import axios from "axios";
import { getStreamUrl } from "@/api/episodes";
import { deleteVideo, hasVideo, saveVideo } from "@/lib/offlineDb";
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
  removeTask: (episodeId: number) => void;
  clearFinished: () => void;
}

let pumping = false;
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
      void pump(set, get);
    }
    return fresh.length;
  },

  removeTask: (episodeId) => {
    if (active?.episodeId === episodeId) active.controller.abort();
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

async function pump(set: Set, get: Get) {
  if (pumping) return;
  pumping = true;
  try {
    for (;;) {
      const next = get().tasks.find((t) => t.status === "pending");
      if (!next) break;
      const controller = new AbortController();
      active = { episodeId: next.episodeId, controller };
      patch(set, next.episodeId, { status: "downloading", progress: 0, error: undefined });
      try {
        const stream = await getStreamUrl(next.episodeId, "servcey1");
        if (controller.signal.aborted) continue;
        if (stream.type !== "mp4" || !stream.url) {
          throw new Error("Cet épisode n'est pas téléchargeable hors ligne.");
        }
        const res = await axios.get<Blob>(stream.url, {
          responseType: "blob",
          timeout: 0, // un épisode peut être long : pas de limite de temps
          signal: controller.signal,
          onDownloadProgress: (e) => {
            const total = e.total ?? 0;
            const pct = total > 0 ? Math.min(99, Math.round((e.loaded / total) * 100)) : 0;
            patch(set, next.episodeId, { progress: pct });
          },
        });
        if (controller.signal.aborted) continue;
        await saveVideo({
          episodeId: next.episodeId,
          animeId: next.animeId,
          animeTitle: next.animeTitle,
          episodeNumber: next.episodeNumber,
          seasonLabel: next.seasonLabel,
          language: next.language,
          thumbnailUrl: next.thumbnailUrl,
          size: res.data.size,
          downloadedAt: Date.now(),
          blob: res.data,
        });
        if (controller.signal.aborted) {
          await deleteVideo(next.episodeId);
          continue;
        }
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
