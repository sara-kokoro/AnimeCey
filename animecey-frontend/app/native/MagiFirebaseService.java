package online.magistream.app;

import android.content.Context;
import android.content.SharedPreferences;

import androidx.annotation.NonNull;

import com.google.firebase.messaging.FirebaseMessaging;
import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Map;

/**
 * Notifications Firebase (FCM) : reçues en quelques secondes, même application fermée.
 *
 * Le serveur envoie des messages « data » (sans bloc notification) : c'est donc ce service qui est
 * appelé dans tous les cas, et on réutilise l'affichage de MagiNotifyWorker (image, ouverture de la
 * bonne page). Le token FCM est envoyé au serveur (POST {api}/push/fcm).
 * Si google-services.json est absent, tout ceci est ignoré sans erreur : MagiNotifyWorker reste actif.
 */
public class MagiFirebaseService extends FirebaseMessagingService {

    @Override
    public void onNewToken(@NonNull String token) {
        Context ctx = getApplicationContext();
        ctx.getSharedPreferences(MagiNotifyWorker.PREFS, Context.MODE_PRIVATE).edit().putString("fcm_token", token).apply();
        sendToken(ctx, token);
    }

    @Override
    public void onMessageReceived(@NonNull RemoteMessage msg) {
        Map<String, String> d = msg.getData();
        if (d == null || d.isEmpty()) return;
        Context ctx = getApplicationContext();
        try {
            JSONObject it = new JSONObject();
            for (Map.Entry<String, String> e : d.entrySet()) it.put(e.getKey(), e.getValue());
            int id = it.optInt("id", (int) (System.currentTimeMillis() / 1000));
            it.put("id", id);
            MagiNotifyWorker.show(ctx, it);
            // Déjà affichée : la vérification périodique ne doit pas la remontrer.
            SharedPreferences sp = ctx.getSharedPreferences(MagiNotifyWorker.PREFS, Context.MODE_PRIVATE);
            if (id > sp.getLong("last_notif", -1)) sp.edit().putLong("last_notif", id).apply();
        } catch (Exception ignored) {
            // message illisible : ignoré
        }
    }

    /** Récupère le token FCM et l'envoie au serveur s'il ne l'a pas encore (appelé par MagiNative.configure). */
    static void syncToken(final Context ctx) {
        try {
            FirebaseMessaging.getInstance().getToken().addOnCompleteListener(task -> {
                if (!task.isSuccessful() || task.getResult() == null) return;
                String token = task.getResult();
                ctx.getSharedPreferences(MagiNotifyWorker.PREFS, Context.MODE_PRIVATE).edit().putString("fcm_token", token).apply();
                sendToken(ctx, token);
            });
        } catch (Throwable ignored) {
            // Firebase non configuré (pas de google-services.json) : pas de notifications Firebase
        }
    }

    private static void sendToken(final Context ctx, final String token) {
        final SharedPreferences sp = ctx.getSharedPreferences(MagiNotifyWorker.PREFS, Context.MODE_PRIVATE);
        final String api = sp.getString("api", "");
        if (api.isEmpty() || !api.startsWith("https://")) return; // sera renvoyé quand le site donnera l'adresse de l'API
        final String stamp = api + "|" + token;
        if (stamp.equals(sp.getString("fcm_sent", ""))) return; // le serveur a déjà ce token
        new Thread(() -> {
            HttpURLConnection c = null;
            try {
                String base = api.endsWith("/") ? api.substring(0, api.length() - 1) : api;
                c = (HttpURLConnection) new URL(base + "/push/fcm").openConnection();
                c.setRequestMethod("POST");
                c.setConnectTimeout(15000);
                c.setReadTimeout(20000);
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json");
                JSONObject body = new JSONObject();
                body.put("token", token);
                body.put("platform", "android");
                try (OutputStream out = c.getOutputStream()) {
                    out.write(body.toString().getBytes("UTF-8"));
                }
                int code = c.getResponseCode();
                if (code >= 200 && code < 300) sp.edit().putString("fcm_sent", stamp).apply();
            } catch (Exception ignored) {
                // réessayé au prochain démarrage de l'application
            } finally {
                if (c != null) c.disconnect();
            }
        }).start();
    }
}
