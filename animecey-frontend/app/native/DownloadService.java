package online.magistream.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
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
import java.io.OutputStream;
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
 * - reprise : un fichier .part déjà commencé continue là où il s'est arrêté (en-tête Range) ;
 * - l'adresse de la vidéo est redemandée au serveur juste avant chaque téléchargement (elle expire).
 */
public class DownloadService extends Service {
    static final String ACTION_START = "online.magistream.app.START";
    static final String ACTION_CANCEL = "online.magistream.app.CANCEL";

    private static final String CH_PROGRESS = "magi_downloads";
    private static final String CH_DONE = "magi_done";
    private static final int FG_ID = 1001;

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

    private Notification buildProgress(String title, String text, int pct, int id) {
        int waiting = Math.max(0, queued.get() - 1);
        String content = waiting > 0 ? text + " · " + waiting + " en attente" : text;
        NotificationCompat.Builder b = new NotificationCompat.Builder(this, CH_PROGRESS)
                .setSmallIcon(android.R.drawable.stat_sys_download)
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
                .setSmallIcon(android.R.drawable.stat_sys_download_done)
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
