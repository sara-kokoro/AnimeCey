/**
 * Stockage interne de l'application (IndexedDB) pour les épisodes téléchargés.
 * Les vidéos restent dans le coffre de l'app : elles n'apparaissent jamais
 * dans la galerie ou les fichiers du téléphone, et restent lisibles hors ligne.
 */

const DB_NAME = "magi-offline";
const STORE = "videos";

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
  blob: Blob;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE, { keyPath: "episodeId" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function tx<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return openDb().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const t = db.transaction(STORE, mode);
        const req = run(t.objectStore(STORE));
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
        t.oncomplete = () => db.close();
        t.onerror = () => reject(t.error);
      }),
  );
}

export function saveVideo(video: OfflineVideo): Promise<IDBValidKey> {
  return tx("readwrite", (s) => s.put(video));
}

export function getVideo(episodeId: number): Promise<OfflineVideo | undefined> {
  return tx("readonly", (s) => s.get(episodeId) as IDBRequest<OfflineVideo | undefined>);
}

export function listVideos(): Promise<OfflineVideo[]> {
  return tx("readonly", (s) => s.getAll() as IDBRequest<OfflineVideo[]>).then((all) =>
    all.sort((a, b) => b.downloadedAt - a.downloadedAt),
  );
}

export function deleteVideo(episodeId: number): Promise<undefined> {
  return tx("readwrite", (s) => s.delete(episodeId));
}

export async function hasVideo(episodeId: number): Promise<boolean> {
  try {
    return (await getVideo(episodeId)) !== undefined;
  } catch {
    return false;
  }
}
