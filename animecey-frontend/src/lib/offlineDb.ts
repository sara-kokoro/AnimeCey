/**
 * Stockage des épisodes téléchargés.
 *
 * - Dans le navigateur : IndexedDB, par MORCEAUX de 4 Mo (un épisode n'est jamais chargé en entier
 *   dans la mémoire). Un téléchargement interrompu reste enregistré en « partiel » et peut reprendre.
 * - Dans l'application Android : fichiers gérés par le plugin natif (voir lib/nativeDownloads.ts).
 *
 * Les vidéos restent dans le coffre de l'app : elles n'apparaissent jamais dans la galerie.
 */
import { isNativeApp, nativeFileUrl, nativePlugin } from "@/lib/nativeDownloads";

const DB_NAME = "magi-offline";
const VIDEOS = "videos";
const CHUNKS = "chunks";

/** Taille d'un morceau enregistré. */
export const CHUNK_SIZE = 4 * 1024 * 1024;

export interface OfflineVideo {
  episodeId: number;
  animeId: number;
  animeTitle: string;
  episodeNumber: number;
  seasonLabel: string;
  language: string;
  thumbnailUrl?: string;
  size: number;
  downloadedAt: number;
  /** navigateur : nombre de morceaux déjà enregistrés */
  chunks?: number;
  /** false = téléchargement partiel (reprise possible). Absent = terminé. */
  complete?: boolean;
  /** taille totale attendue, quand le serveur l'a annoncée */
  total?: number;
  /** anciens enregistrements (une seule pièce) */
  blob?: Blob;
  /** application Android : chemin du fichier */
  filePath?: string;
}

interface ChunkRecord {
  episodeId: number;
  index: number;
  blob: Blob;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 2);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(VIDEOS)) db.createObjectStore(VIDEOS, { keyPath: "episodeId" });
      if (!db.objectStoreNames.contains(CHUNKS)) db.createObjectStore(CHUNKS, { keyPath: ["episodeId", "index"] });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function run<T>(stores: string[], mode: IDBTransactionMode, work: (tx: IDBTransaction) => Promise<T> | IDBRequest<T>): Promise<T> {
  return openDb().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const tx = db.transaction(stores, mode);
        let result: T;
        const out = work(tx);
        if (out instanceof IDBRequest) {
          out.onsuccess = () => {
            result = out.result;
          };
          out.onerror = () => reject(out.error);
        } else {
          out.then((v) => (result = v)).catch(reject);
        }
        tx.oncomplete = () => {
          db.close();
          resolve(result);
        };
        tx.onerror = () => reject(tx.error);
        tx.onabort = () => reject(tx.error);
      }),
  );
}

function req<T>(r: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });
}

function chunkRange(episodeId: number): IDBKeyRange {
  return IDBKeyRange.bound([episodeId, 0], [episodeId, Number.MAX_SAFE_INTEGER]);
}

/* ───────── Navigateur : métadonnées ───────── */

export function saveVideo(video: OfflineVideo): Promise<IDBValidKey> {
  return run([VIDEOS], "readwrite", (tx) => tx.objectStore(VIDEOS).put(video));
}

/** Enregistre un morceau. */
export function putChunk(episodeId: number, index: number, blob: Blob): Promise<IDBValidKey> {
  const rec: ChunkRecord = { episodeId, index, blob };
  return run([CHUNKS], "readwrite", (tx) => tx.objectStore(CHUNKS).put(rec));
}

export async function getPartial(episodeId: number): Promise<OfflineVideo | undefined> {
  const v = await run([VIDEOS], "readonly", (tx) => tx.objectStore(VIDEOS).get(episodeId) as IDBRequest<OfflineVideo | undefined>);
  return v && v.complete === false ? v : undefined;
}

async function webGet(episodeId: number): Promise<OfflineVideo | undefined> {
  return run([VIDEOS], "readonly", (tx) => tx.objectStore(VIDEOS).get(episodeId) as IDBRequest<OfflineVideo | undefined>);
}

/** Reconstitue l'épisode à partir des morceaux (les morceaux restent sur le disque, pas en mémoire). */
export async function getVideoBlob(episodeId: number): Promise<Blob> {
  const meta = await webGet(episodeId);
  if (!meta) throw new Error("Épisode introuvable.");
  if (meta.blob) return meta.blob;
  const records = await run([CHUNKS], "readonly", (tx) => tx.objectStore(CHUNKS).getAll(chunkRange(episodeId)) as IDBRequest<ChunkRecord[]>);
  records.sort((a, b) => a.index - b.index);
  if (records.length !== (meta.chunks ?? 0)) throw new Error("Téléchargement incomplet.");
  return new Blob(records.map((r) => r.blob), { type: "video/mp4" });
}

/* ───────── API commune (navigateur + application) ───────── */

function fromNative(i: import("@/lib/nativeDownloads").NativeItem): OfflineVideo {
  let m: Partial<OfflineVideo> = {};
  try {
    m = i.meta ? (JSON.parse(i.meta) as Partial<OfflineVideo>) : {};
  } catch {
    /* meta illisible : on affiche quand même l'épisode */
  }
  return {
    episodeId: i.episodeId,
    animeId: m.animeId ?? 0,
    animeTitle: m.animeTitle ?? "Épisode",
    episodeNumber: m.episodeNumber ?? 0,
    seasonLabel: m.seasonLabel ?? "",
    language: m.language ?? "",
    thumbnailUrl: m.thumbnailUrl,
    size: i.size,
    downloadedAt: i.downloadedAt ?? Date.now(),
    filePath: i.path,
  };
}

export async function getVideo(episodeId: number): Promise<OfflineVideo | undefined> {
  if (isNativeApp()) return (await listVideos()).find((v) => v.episodeId === episodeId);
  const v = await webGet(episodeId);
  return v && v.complete !== false ? v : undefined;
}

export async function listVideos(): Promise<OfflineVideo[]> {
  let all: OfflineVideo[];
  if (isNativeApp()) {
    const { items } = await nativePlugin().list();
    all = items.filter((i) => i.status === "done" && i.path).map(fromNative);
  } else {
    all = (await run([VIDEOS], "readonly", (tx) => tx.objectStore(VIDEOS).getAll() as IDBRequest<OfflineVideo[]>)).filter(
      (v) => v.complete !== false,
    );
  }
  return all.sort((a, b) => b.downloadedAt - a.downloadedAt);
}

export async function deleteVideo(episodeId: number): Promise<void> {
  if (isNativeApp()) {
    await nativePlugin().remove({ episodeId });
    return;
  }
  await run([VIDEOS, CHUNKS], "readwrite", async (tx) => {
    await req(tx.objectStore(VIDEOS).delete(episodeId));
    await req(tx.objectStore(CHUNKS).delete(chunkRange(episodeId)));
  });
}

export async function hasVideo(episodeId: number): Promise<boolean> {
  try {
    return (await getVideo(episodeId)) !== undefined;
  } catch {
    return false;
  }
}

/** Adresse de lecture d'un épisode téléchargé. `release` libère la mémoire quand on ferme le lecteur. */
export async function getPlaybackUrl(video: OfflineVideo): Promise<{ url: string; release: () => void }> {
  if (video.filePath) return { url: nativeFileUrl(video.filePath), release: () => undefined };
  const blob = await getVideoBlob(video.episodeId);
  const url = URL.createObjectURL(blob);
  return { url, release: () => URL.revokeObjectURL(url) };
}
