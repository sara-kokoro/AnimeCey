package online.magistream.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Build;

import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.work.PeriodicWorkRequest;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.TimeUnit;

/**
 * Notifications envoyées depuis le bot (/notification).
 * Toutes les ~15 minutes (même application fermée), on demande au serveur s'il y en a de nouvelles.
 * La toute première fois, on mémorise simplement la dernière : pas d'ancien historique d'un coup.
 */
public class MagiNotifyWorker extends Worker {
    static final String PREFS = "magi_prefs";
    static final String CH = "magi_news";
    static final String UNIQUE = "magi_notify";

    public MagiNotifyWorker(@NonNull Context ctx, @NonNull WorkerParameters p) {
        super(ctx, p);
    }

    /** Programme la vérification périodique (appelée depuis la page via MagiNative.configure). */
    static void schedule(Context ctx) {
        PeriodicWorkRequest req = new PeriodicWorkRequest.Builder(MagiNotifyWorker.class, 15, TimeUnit.MINUTES).build();
        WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(UNIQUE, ExistingPeriodicWorkPolicy.KEEP, req);
    }

    private static String get(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(20000);
        try (InputStream in = c.getInputStream()) {
            ByteArrayOutputStream o = new ByteArrayOutputStream();
            byte[] b = new byte[8192];
            int n;
            while ((n = in.read(b)) > 0) o.write(b, 0, n);
            return o.toString("UTF-8");
        } finally {
            c.disconnect();
        }
    }

    private static Bitmap bitmap(String url) {
        try {
            HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
            c.setConnectTimeout(15000);
            c.setReadTimeout(20000);
            try (InputStream in = c.getInputStream()) {
                return BitmapFactory.decodeStream(in);
            } finally {
                c.disconnect();
            }
        } catch (Exception e) {
            return null;
        }
    }

    @NonNull
    @Override
    public Result doWork() {
        Context ctx = getApplicationContext();
        SharedPreferences sp = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String api = sp.getString("api", "");
        if (api.isEmpty() || !api.startsWith("https://")) return Result.success();
        long last = sp.getLong("last_notif", -1);
        try {
            String base = api.endsWith("/") ? api.substring(0, api.length() - 1) : api;
            String url = base + "/app-notifications" + (last >= 0 ? "?after=" + last : "");
            JSONObject res = new JSONObject(get(url));
            long latest = res.optLong("latest_id", Math.max(last, 0));
            if (last < 0) {
                sp.edit().putLong("last_notif", latest).apply();
                return Result.success();
            }
            JSONArray items = res.optJSONArray("items");
            if (items != null) for (int i = 0; i < items.length(); i++) show(ctx, items.getJSONObject(i));
            sp.edit().putLong("last_notif", latest).apply();
            return Result.success();
        } catch (Exception e) {
            return Result.retry();
        }
    }

    private void show(Context ctx, JSONObject it) {
        NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26) {
            nm.createNotificationChannel(new NotificationChannel(CH, "Nouveautés Magi-Stream", NotificationManager.IMPORTANCE_DEFAULT));
        }
        int id = it.optInt("id");
        String target = it.optString("path", "/");
        Intent open;
        if (target.startsWith("https://")) {
            // lien externe (Telegram, X, site…) : ouvert dans l'application ou le navigateur adapté
            open = new Intent(Intent.ACTION_VIEW, android.net.Uri.parse(target));
            open.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        } else {
            open = new Intent(ctx, MainActivity.class);
            open.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            open.putExtra("magi_path", target);
        }
        PendingIntent pi = PendingIntent.getActivity(ctx, id, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        int small = ctx.getResources().getIdentifier("ic_stat_magi", "drawable", ctx.getPackageName());
        NotificationCompat.Builder b = new NotificationCompat.Builder(ctx, CH)
                .setSmallIcon(small != 0 ? small : android.R.drawable.ic_dialog_info)
                .setContentTitle(it.optString("title", "Magi-Stream"))
                .setContentText(it.optString("body", ""))
                .setStyle(new NotificationCompat.BigTextStyle().bigText(it.optString("body", "")))
                .setContentIntent(pi)
                .setAutoCancel(true)
                .setPriority(NotificationCompat.PRIORITY_DEFAULT);
        String img = it.optString("image_url", "");
        if (!img.isEmpty() && !it.isNull("image_url")) {
            Bitmap bmp = bitmap(img);
            if (bmp != null) {
                b.setLargeIcon(bmp);
                b.setStyle(new NotificationCompat.BigPictureStyle().bigPicture(bmp).bigLargeIcon((Bitmap) null)
                        .setSummaryText(it.optString("body", "")));
            }
        }
        try {
            nm.notify(100000 + id, b.build());
        } catch (SecurityException ignored) {
            // permission de notification refusée
        }
    }
}
