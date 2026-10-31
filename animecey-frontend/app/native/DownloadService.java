package online.magistream.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;
import androidx.core.app.ServiceCompat;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLongArray;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Service de téléchargement en arrière-plan.
 * - un épisode à la fois, les autres attendent leur tour ;
 * - notification de progression avec bouton « Annuler », puis notification « terminé » ;
 * - vitesse : un épisode est téléchargé en 4 morceaux EN MÊME TEMPS (4 connexions), chacun écrit à sa place dans le fichier ;
 * - reprise : un fichier .part déjà commencé continue là où il s'est arrêté (en-tête Range) ;
 * - l'adresse de la vidéo est redemandée au serveur juste avant chaque téléchargement (elle expire).
 */
public class DownloadService extends Service {
    static final String ACTION_START = "online.magistream.app.START";
    static final String ACTION_CANCEL = "online.magistream.app.CANCEL";

    private static final String CH_PROGRESS = "magi_downloads";
    private static final String CH_DONE = "magi_done";
    private static final int FG_ID = 1001;
    /** Nombre de connexions simultanées pour un épisode. */
    private static final int SEGMENTS = 4;
    /** En dessous de cette taille, une seule connexion suffit. */
    private static final long MIN_SEGMENTED = 8L * 1024 * 1024;

    static volatile boolean running = false;
    private static final Set<Integer> CANCELLED = ConcurrentHashMap.newKeySet();

    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final AtomicInteger queued = new AtomicInteger(0);
    private volatile int currentId = -1;
    private PowerManager.WakeLock wakeLock;

    /* ───────── Appels depuis le plugin ───────── */

    static void cancel(Context c, int id) {
        CANCELLED.add(id);
        if (!running) cleanupCancelled(c, id);
    }

    static void deleteFiles(Context c, int id) {
        //noinspection ResultOfMethodCallIgnored
        DownloadStore.finalFile(c, id).delete();
        //noinspection ResultOfMethodCallIgnored
        DownloadStore.partFile(c, id).delete();
        //noinspection ResultOfMethodCallIgnored
        new File(DownloadStore.partFile(c, id).getPath() + ".seg").delete();
    }

    private static void cleanupCancelled(Context c, int id) {
        CANCELLED.remove(id);
        deleteFiles(c, id);
        JSONObject item = DownloadStore.get(c, id);
        DownloadStore.remove(c, id);
        try {
            JSONObject o = item != null ? item : new JSONObject().put("episodeId", id);
            o.put("status", "cancelled");
            DownloadStore.notifyPage(o);
        } catch (Exception ignored) {
            // rien à faire
        }
    }

    /* ───────── Cycle de vie ───────── */

    @Override
    public void onCreate() {
        super.onCreate();
        running = true;
        createChannels();
        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (pm != null) {
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "magistream:download");
            wakeLock.setReferenceCounted(false);
            wakeLock.acquire(6 * 60 * 60 * 1000L);
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        showForeground(buildProgress("Magi-Stream", "Préparation du téléchargement…", -1, -1));
        if (intent == null) {
            maybeStop();
            return START_NOT_STICKY;
        }
        final int id = intent.getIntExtra("episodeId", -1);
        if (ACTION_CANCEL.equals(intent.getAction())) {
            if (id >= 0) cancel(this, id);
            return START_NOT_STICKY;
        }
        if (ACTION_START.equals(intent.getAction()) && id >= 0) {
            final String apiBase = intent.getStringExtra("apiBase");
            final String meta = intent.getStringExtra("meta");
            final String title = intent.getStringExtra("title");
            final String subtitle = intent.getStringExtra("subtitle");
            CANCELLED.remove(id);
            JSONObject item = DownloadStore.get(this, id);
            try {
                if (item == null) item = new JSONObject().put("episodeId", id);
                item.put("status", "pending").put("progress", 0).put("meta", meta == null ? "{}" : meta);
                item.remove("error");
                DownloadStore.save(this, item);
            } catch (Exception ignored) {
                // rien à faire
            }
            queued.incrementAndGet();
            worker.execute(new Runnable() {
                @Override
                public void run() {
                    try {
                        download(id, apiBase, title == null ? "Épisode" : title, subtitle == null ? "" : subtitle);
                    } finally {
                        queued.decrementAndGet();
                        currentId = -1;
                        maybeStop();
                    }
                }
            });
        }
        return START_NOT_STICKY;
    }

    @Override
    public void onDestroy() {
        running = false;
        worker.shutdownNow();
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        super.onDestroy();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void maybeStop() {
        if (queued.get() <= 0) {
            stopForeground(true);
            stopSelf();
        }
    }

    /* ───────── Téléchargement ───────── */

    private void download(int id, String apiBase, String title, String subtitle) {
        if (CANCELLED.contains(id)) {
            cleanupCancelled(this, id);
            return;
        }
        currentId = id;
        File part = DownloadStore.partFile(this, id);
        HttpURLConnection conn = null;
        try {
            setStatus(id, "downloading", null);
            showForeground(buildProgress(title, "Connexion…", -1, id));

            String videoUrl = resolveVideoUrl(apiBase, id);

            long offset = part.exists() ? part.length() : 0;
            File seg = segFile(part);
            if (seg.exists()) {
                // reprise d'un téléchargement en plusieurs morceaux
                long known = readSegTotal(seg);
                if (known > 0 && part.exists() && part.length() == known) {
                    downloadSegmented(id, videoUrl, known, title, subtitle, part, seg);
                    return;
                }
                //noinspection ResultOfMethodCallIgnored
                seg.delete();
                //noinspection ResultOfMethodCallIgnored
                part.delete();
                offset = 0;
            }
            if (offset == 0) {
                long total = probeSize(videoUrl);
                if (total >= MIN_SEGMENTED) {
                    downloadSegmented(id, videoUrl, total, title, subtitle, part, seg);
                    return;
                }
            }
            conn = open(videoUrl, offset);
            int code = conn.getResponseCode();
            if (code == 416 && offset > 0) {
                // fichier déjà complet côté serveur
                finish(id, part, offset, title);
                return;
            }
            if (code != 200 && code != 206) throw new Exception("Serveur indisponible (HTTP " + code + ")");
            if (offset > 0 && code != 206) {
                offset = 0; // le serveur ignore la reprise : on recommence depuis le début
                //noinspection ResultOfMethodCallIgnored
                part.delete();
            }
            long length = conn.getContentLengthLong();
            long total = length > 0 ? offset + length : -1;

            long received = offset;
            long lastTick = 0;
            byte[] buf = new byte[64 * 1024];
            try (InputStream in = conn.getInputStream();
                 OutputStream out = new FileOutputStream(part, offset > 0)) {
                int n;
                while ((n = in.read(buf)) != -1) {
                    if (CANCELLED.contains(id) || Thread.currentThread().isInterrupted()) {
                        cleanupCancelled(this, id);
                        return;
                    }
                    out.write(buf, 0, n);
                    received += n;
                    long now = System.currentTimeMillis();
                    if (now - lastTick > 600) {
                        lastTick = now;
                        int pct = total > 0 ? (int) Math.min(99, received * 100 / total) : -1;
                        progress(id, received, pct);
                        showForeground(buildProgress(title, subtitle, pct, id));
                    }
                }
            }
            if (total > 0 && received < total) throw new Exception("Connexion interrompue. Appuie sur « Réessayer » pour reprendre.");
            finish(id, part, received, title);
        } catch (Exception e) {
            if (CANCELLED.contains(id)) {
                cleanupCancelled(this, id);
                return;
            }
            String msg = e.getMessage() == null ? "Téléchargement interrompu." : e.getMessage();
            setStatus(id, "error", msg);
            notifyDone(id, "Échec du téléchargement", title + " — appuie pour réessayer dans l'app.");
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    /* ───────── Téléchargement en plusieurs connexions ───────── */

    private static File segFile(File part) {
        return new File(part.getPath() + ".seg");
    }

    /** Taille totale du fichier (requête Range 0-0), ou -1 si le serveur ne la donne pas. */
    private long probeSize(String url) {
        HttpURLConnection c = null;
        try {
            c = open(url, 0);
            c.setRequestProperty("Range", "bytes=0-0");
            if (c.getResponseCode() != 206) return -1;
            String cr = c.getHeaderField("Content-Range"); // « bytes 0-0/123456 »
            if (cr == null) return -1;
            int slash = cr.lastIndexOf('/');
            return slash < 0 ? -1 : Long.parseLong(cr.substring(slash + 1).trim());
        } catch (Exception e) {
            return -1;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    private static long readSegTotal(File seg) {
        try {
            List<String> lines = Files.readAllLines(seg.toPath(), StandardCharsets.UTF_8);
            return lines.isEmpty() ? -1 : Long.parseLong(lines.get(0).trim());
        } catch (Exception e) {
            return -1;
        }
    }

    private static void writeSeg(File seg, long total, AtomicLongArray done) {
        StringBuilder sb = new StringBuilder().append(total).append('\n');
        for (int i = 0; i < done.length(); i++) sb.append(i == 0 ? "" : ",").append(done.get(i));
        try {
            Files.write(seg.toPath(), sb.toString().getBytes(StandardCharsets.UTF_8));
        } catch (IOException ignored) {
            // la reprise repartira simplement du début
        }
    }

    private void downloadSegmented(final int id, final String url, final long total, String title, String subtitle,
                                   final File part, File seg) throws Exception {
        final long segLen = (total + SEGMENTS - 1) / SEGMENTS;
        final long[] start = new long[SEGMENTS];
        final long[] end = new long[SEGMENTS];
        final AtomicLongArray done = new AtomicLongArray(SEGMENTS);
        for (int i = 0; i < SEGMENTS; i++) {
            start[i] = i * segLen;
            end[i] = Math.min(total, (i + 1) * segLen) - 1;
        }
        boolean resume = false;
        if (seg.exists() && part.exists() && part.length() == total) {
            try {
                List<String> lines = Files.readAllLines(seg.toPath(), StandardCharsets.UTF_8);
                String[] parts = lines.get(1).split(",");
                for (int i = 0; i < SEGMENTS && i < parts.length; i++) {
                    long size = Math.max(0, end[i] - start[i] + 1);
                    done.set(i, Math.min(size, Math.max(0, Long.parseLong(parts[i].trim()))));
                }
                resume = true;
            } catch (Exception e) {
                resume = false;
            }
        }
        if (!resume) {
            for (int i = 0; i < SEGMENTS; i++) done.set(i, 0);
            try (RandomAccessFile raf = new RandomAccessFile(part, "rw")) {
                raf.setLength(total);
            }
            writeSeg(seg, total, done);
        }

        final AtomicBoolean abort = new AtomicBoolean(false);
        ExecutorService pool = Executors.newFixedThreadPool(SEGMENTS);
        List<Future<Void>> futures = new ArrayList<>();
        boolean complete = false;
        try {
            for (int i = 0; i < SEGMENTS; i++) {
                final int idx = i;
                futures.add(pool.submit(new Callable<Void>() {
                    @Override
                    public Void call() throws Exception {
                        downloadSegment(id, url, part, idx, start[idx], end[idx], done, abort);
                        return null;
                    }
                }));
            }
            long lastTick = 0;
            long lastSave = 0;
            while (true) {
                boolean allDone = true;
                for (Future<Void> f : futures) {
                    if (!f.isDone()) {
                        allDone = false;
                    } else {
                        try {
                            f.get();
                        } catch (ExecutionException ee) {
                            Throwable cause = ee.getCause();
                            throw cause instanceof Exception ? (Exception) cause : new Exception(cause);
                        }
                    }
                }
                if (CANCELLED.contains(id) || Thread.currentThread().isInterrupted()) {
                    abort.set(true);
                    pool.shutdownNow();
                    //noinspection ResultOfMethodCallIgnored
                    seg.delete();
                    cleanupCancelled(this, id);
                    return;
                }
                long received = 0;
                for (int i = 0; i < SEGMENTS; i++) received += done.get(i);
                long now = System.currentTimeMillis();
                if (now - lastTick > 600) {
                    lastTick = now;
                    int pct = (int) Math.min(99, received * 100 / total);
                    progress(id, received, pct);
                    showForeground(buildProgress(title, subtitle, pct, id));
                }
                if (now - lastSave > 2500) {
                    lastSave = now;
                    writeSeg(seg, total, done);
                }
                if (allDone) {
                    if (received < total) throw new Exception("Connexion interrompue. Appuie sur « Réessayer » pour reprendre.");
                    complete = true;
                    break;
                }
                Thread.sleep(300);
            }
        } catch (Exception e) {
            abort.set(true);
            writeSeg(seg, total, done); // garde ce qui est déjà reçu pour « Réessayer »
            throw e;
        } finally {
            pool.shutdownNow();
        }
        if (complete) {
            //noinspection ResultOfMethodCallIgnored
            seg.delete();
            finish(id, part, total, title);
        }
    }

    /** Un morceau : demande sa plage d'octets et l'écrit à sa place ; réessaie 3 fois si la connexion coupe. */
    private void downloadSegment(int id, String url, File part, int idx, long start, long end,
                                 AtomicLongArray done, AtomicBoolean abort) throws Exception {
        final long size = end - start + 1;
        if (size <= 0) return;
        Exception last = null;
        for (int attempt = 0; attempt < 4; attempt++) {
            if (done.get(idx) >= size) return;
            HttpURLConnection c = null;
            try {
                long from = start + done.get(idx);
                c = open(url, 0);
                c.setRequestProperty("Range", "bytes=" + from + "-" + end);
                int code = c.getResponseCode();
                if (code != 206) throw new IOException("Serveur indisponible (HTTP " + code + ")");
                try (InputStream in = c.getInputStream(); RandomAccessFile raf = new RandomAccessFile(part, "rw")) {
                    raf.seek(from);
                    byte[] buf = new byte[128 * 1024];
                    int n;
                    while ((n = in.read(buf)) != -1) {
                        if (abort.get() || CANCELLED.contains(id) || Thread.currentThread().isInterrupted()) return;
                        int w = (int) Math.min(n, size - done.get(idx));
                        if (w <= 0) break;
                        raf.write(buf, 0, w);
                        done.addAndGet(idx, w);
                        if (done.get(idx) >= size) break;
                    }
                }
                if (done.get(idx) >= size) return;
                last = new IOException("Flux coupé avant la fin");
            } catch (IOException e) {
                last = e;
            } finally {
                if (c != null) c.disconnect();
            }
            if (abort.get()) return;
            Thread.sleep(1500L * (attempt + 1));
        }
        throw last != null ? last : new IOException("Connexion interrompue");
    }

    private String resolveVideoUrl(String apiBase, int id) throws Exception {
        String base = apiBase == null ? "" : apiBase.replaceAll("/+$", "");
        HttpURLConnection c = (HttpURLConnection) new URL(base + "/episodes/" + id + "/stream?server=servcey1").openConnection();
        c.setConnectTimeout(30000);
        c.setReadTimeout(30000);
        try {
            if (c.getResponseCode() != 200) throw new Exception("Source introuvable (HTTP " + c.getResponseCode() + ")");
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (InputStream in = c.getInputStream()) {
                byte[] b = new byte[4096];
                int n;
                while ((n = in.read(b)) != -1) bytes.write(b, 0, n);
            }
            JSONObject j = new JSONObject(bytes.toString("UTF-8"));
            String url = j.optString("url", "");
            String type = j.optString("type", "");
            if (url.isEmpty() || !"mp4".equals(type)) throw new Exception("Cet épisode n'est pas téléchargeable hors ligne.");
            return url;
        } finally {
            c.disconnect();
        }
    }

    private HttpURLConnection open(String url, long offset) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(30000);
        c.setReadTimeout(60000);
        c.setInstanceFollowRedirects(true);
        if (offset > 0) c.setRequestProperty("Range", "bytes=" + offset + "-");
        return c;
    }

    private void finish(int id, File part, long size, String title) throws Exception {
        File dest = DownloadStore.finalFile(this, id);
        //noinspection ResultOfMethodCallIgnored
        dest.delete();
        if (!part.renameTo(dest)) throw new Exception("Impossible d'enregistrer le fichier.");
        JSONObject item = DownloadStore.get(this, id);
        if (item == null) item = new JSONObject().put("episodeId", id);
        item.put("status", "done").put("progress", 100).put("size", dest.length()).put("path", dest.getAbsolutePath())
                .put("downloadedAt", System.currentTimeMillis());
        item.remove("error");
        DownloadStore.save(this, item);
        notifyDone(id, "Téléchargement terminé", title);
    }

    private void progress(int id, long received, int pct) {
        try {
            JSONObject item = DownloadStore.get(this, id);
            if (item == null) item = new JSONObject().put("episodeId", id);
            item.put("status", "downloading").put("size", received).put("progress", Math.max(pct, 0));
            DownloadStore.save(this, item);
        } catch (Exception ignored) {
            // rien à faire
        }
    }

    private void setStatus(int id, String status, String error) {
        try {
            JSONObject item = DownloadStore.get(this, id);
            if (item == null) item = new JSONObject().put("episodeId", id);
            item.put("status", status);
            if (error != null) item.put("error", error);
            else item.remove("error");
            DownloadStore.save(this, item);
        } catch (Exception ignored) {
            // rien à faire
        }
    }

    /* ───────── Notifications ───────── */

    private void createChannels() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;
        nm.createNotificationChannel(new NotificationChannel(CH_PROGRESS, "Téléchargements en cours", NotificationManager.IMPORTANCE_LOW));
        nm.createNotificationChannel(new NotificationChannel(CH_DONE, "Téléchargements terminés", NotificationManager.IMPORTANCE_DEFAULT));
    }

    private PendingIntent openApp() {
        Intent launch = getPackageManager().getLaunchIntentForPackage(getPackageName());
        if (launch == null) launch = new Intent();
        return PendingIntent.getActivity(this, 0, launch, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    /** Icône monochrome Magi-Stream (le « M »), créée au build ; icône du système en secours. */
    private int smallIcon(int fallback) {
        int res = getResources().getIdentifier("ic_stat_magi", "drawable", getPackageName());
        return res != 0 ? res : fallback;
    }

    /** Logo en couleur affiché dans la notification. */
    private Bitmap largeIcon() {
        try {
            int res = getResources().getIdentifier("ic_launcher", "mipmap", getPackageName());
            return res != 0 ? BitmapFactory.decodeResource(getResources(), res) : null;
        } catch (Exception e) {
            return null;
        }
    }

    private Notification buildProgress(String title, String text, int pct, int id) {
        int waiting = Math.max(0, queued.get() - 1);
        String content = waiting > 0 ? text + " · " + waiting + " en attente" : text;
        NotificationCompat.Builder b = new NotificationCompat.Builder(this, CH_PROGRESS)
                .setSmallIcon(smallIcon(android.R.drawable.stat_sys_download))
                .setLargeIcon(largeIcon())
                .setColor(0xFFF97316)
                .setContentTitle(title)
                .setContentText(pct >= 0 ? pct + " % · " + content : content)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setContentIntent(openApp());
        if (pct >= 0) b.setProgress(100, pct, false);
        else b.setProgress(0, 0, true);
        if (id >= 0) {
            Intent cancel = new Intent(this, DownloadService.class).setAction(ACTION_CANCEL).putExtra("episodeId", id);
            PendingIntent pi = PendingIntent.getService(this, id, cancel, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
            b.addAction(android.R.drawable.ic_menu_close_clear_cancel, "Annuler", pi);
        }
        return b.build();
    }

    private void showForeground(Notification n) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceCompat.startForeground(this, FG_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        } else {
            startForeground(FG_ID, n);
        }
    }

    private void notifyDone(int id, String title, String text) {
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;
        Notification n = new NotificationCompat.Builder(this, CH_DONE)
                .setSmallIcon(smallIcon(android.R.drawable.stat_sys_download_done))
                .setLargeIcon(largeIcon())
                .setColor(0xFFF97316)
                .setContentTitle(title)
                .setContentText(text)
                .setAutoCancel(true)
                .setContentIntent(openApp())
                .build();
        try {
            nm.notify(3000 + id, n);
        } catch (SecurityException ignored) {
            // notifications refusées par l'utilisateur
        }
    }
}
