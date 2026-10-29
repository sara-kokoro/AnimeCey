package online.magistream.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * Mémoire des téléchargements (SharedPreferences) : un petit JSON par épisode.
 * Le service écrit ici, le plugin lit ici et prévient la page (événement « downloadUpdate »).
 */
final class DownloadStore {
    interface Listener {
        void onUpdate(JSONObject item);
    }

    static volatile Listener listener;

    private static final String PREFS = "magi_downloads";
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private DownloadStore() {}

    private static SharedPreferences prefs(Context c) {
        return c.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static File dir(Context c) {
        File base = c.getExternalFilesDir(null);
        if (base == null) base = c.getFilesDir();
        File d = new File(base, "downloads");
        //noinspection ResultOfMethodCallIgnored
        d.mkdirs();
        return d;
    }

    static File finalFile(Context c, int id) {
        return new File(dir(c), id + ".mp4");
    }

    static File partFile(Context c, int id) {
        return new File(dir(c), id + ".mp4.part");
    }

    static JSONObject get(Context c, int id) {
        String raw = prefs(c).getString("item_" + id, null);
        if (raw == null) return null;
        try {
            return new JSONObject(raw);
        } catch (JSONException e) {
            return null;
        }
    }

    static List<JSONObject> all(Context c) {
        List<JSONObject> out = new ArrayList<>();
        for (Object v : prefs(c).getAll().values()) {
            if (!(v instanceof String)) continue;
            try {
                JSONObject o = new JSONObject((String) v);
                if (o.has("episodeId")) out.add(o);
            } catch (JSONException ignored) {
                // entrée illisible : ignorée
            }
        }
        return out;
    }

    /** Enregistre l'état d'un téléchargement et prévient la page. */
    static void save(Context c, JSONObject item) {
        int id = item.optInt("episodeId");
        prefs(c).edit().putString("item_" + id, item.toString()).apply();
        notifyPage(item);
    }

    static void remove(Context c, int id) {
        prefs(c).edit().remove("item_" + id).apply();
    }

    static void notifyPage(final JSONObject item) {
        final Listener l = listener;
        if (l == null) return;
        MAIN.post(new Runnable() {
            @Override
            public void run() {
                l.onUpdate(item);
            }
        });
    }
}
