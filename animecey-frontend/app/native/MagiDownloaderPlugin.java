package online.magistream.app;

import android.Manifest;
import android.content.Context;
import android.content.Intent;

import androidx.core.content.ContextCompat;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;

import org.json.JSONObject;

import java.io.File;

/**
 * Plugin Capacitor « MagiDownloader » : pont entre le site (JavaScript) et le service de téléchargement.
 * Méthodes : start, cancel, remove, list, requestPermissions. Événement : downloadUpdate.
 */
@CapacitorPlugin(
        name = "MagiDownloader",
        permissions = {@Permission(strings = {Manifest.permission.POST_NOTIFICATIONS}, alias = "notifications")}
)
public class MagiDownloaderPlugin extends Plugin {

    @Override
    public void load() {
        DownloadStore.listener = new DownloadStore.Listener() {
            @Override
            public void onUpdate(JSONObject item) {
                try {
                    notifyListeners("downloadUpdate", new JSObject(item.toString()));
                } catch (Exception ignored) {
                    // événement perdu : la page relit la liste au prochain affichage
                }
            }
        };
    }

    @Override
    protected void handleOnDestroy() {
        DownloadStore.listener = null;
    }

    @PluginMethod
    public void start(PluginCall call) {
        Integer id = call.getInt("episodeId");
        if (id == null) {
            call.reject("episodeId manquant");
            return;
        }
        Context ctx = getContext();
        Intent i = new Intent(ctx, DownloadService.class)
                .setAction(DownloadService.ACTION_START)
                .putExtra("episodeId", id)
                .putExtra("apiBase", call.getString("apiBase", ""))
                .putExtra("meta", call.getString("meta", "{}"))
                .putExtra("title", call.getString("title", "Épisode"))
                .putExtra("subtitle", call.getString("subtitle", ""));
        ContextCompat.startForegroundService(ctx, i);
        call.resolve();
    }

    @PluginMethod
    public void cancel(PluginCall call) {
        Integer id = call.getInt("episodeId");
        if (id != null) DownloadService.cancel(getContext(), id);
        call.resolve();
    }

    @PluginMethod
    public void remove(PluginCall call) {
        Integer id = call.getInt("episodeId");
        if (id != null) {
            DownloadService.cancel(getContext(), id);
            DownloadService.deleteFiles(getContext(), id);
            DownloadStore.remove(getContext(), id);
        }
        call.resolve();
    }

    @PluginMethod
    public void list(PluginCall call) {
        Context ctx = getContext();
        JSArray items = new JSArray();
        for (JSONObject o : DownloadStore.all(ctx)) {
            try {
                String status = o.optString("status");
                // téléchargement interrompu par la fermeture du service : on le propose en « Réessayer »
                if (("downloading".equals(status) || "pending".equals(status)) && !DownloadService.running) {
                    o.put("status", "error").put("error", "Téléchargement interrompu. Appuie sur « Réessayer » pour reprendre.");
                }
                // fichier effacé depuis l'extérieur
                if ("done".equals(o.optString("status"))) {
                    File f = new File(o.optString("path", ""));
                    if (!f.exists()) continue;
                }
                items.put(o);
            } catch (Exception ignored) {
                // entrée ignorée
            }
        }
        JSObject res = new JSObject();
        res.put("items", items);
        call.resolve(res);
    }
}
