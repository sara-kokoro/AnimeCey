package online.magistream.app;

import android.content.Context;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageInfo;
import android.net.Uri;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebView;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;

import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    private long lastBack = 0;

    /** Page hors connexion embarquée dans l'APK (app/www/offline.html), servie par Capacitor en https://localhost. */
    private static final String OFFLINE_URL = "https://localhost/offline.html";
    /** Au-delà de ce délai sans réponse du site (progression < 25 %), on bascule sur la page hors connexion. */
    private static final long SITE_TIMEOUT_MS = 12000;

    /** true si le téléphone a un accès réel à internet (un Wi-Fi sans internet donne false). */
    private boolean hasInternet() {
        try {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
            Network n = cm.getActiveNetwork();
            if (n == null) return false;
            NetworkCapabilities c = cm.getNetworkCapabilities(n);
            return c != null
                    && c.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                    && c.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
        } catch (Exception e) {
            return true; // doute : on laisse le site essayer
        }
    }

    /**
     * DIAGNOSTIC TEMPORAIRE (à retirer quand la page hors connexion marche) : à 8 s puis 20 s, si la page affichée
     * n'est pas le site, une bulle indique : adresse (u), présence du repère de version v3 de offline.html (v3),
     * React démarré (b), éléments dans #root (r), longueur du texte (t), version de Chrome du WebView, 1re erreur.
     */
    private void diagToast(final WebView wv) {
        final String js = "(function(){var r=document.getElementById('root'),m=document.querySelector('meta[name=magi-offline]'),"
                + "c=navigator.userAgent.match(/Chrome\\/(\\d+)/);"
                + "return 'u='+location.pathname+' v3='+(m?1:0)+' b='+(document.documentElement.getAttribute('data-booted')||0)"
                + "+' r='+(r?r.childNodes.length:-1)+' t='+(document.body?document.body.innerText.length:-1)"
                + "+' chrome='+(c?c[1]:'?')+' err='+((window.__magiErrs||[]).slice(0,2).join(' | ')||'-')+' h='+location.hostname})()";
        long[] delais = {8000, 20000};
        for (long d : delais) {
            new Handler(Looper.getMainLooper()).postDelayed(new Runnable() {
                @Override
                public void run() {
                    try {
                        wv.evaluateJavascript(js, new ValueCallback<String>() {
                            @Override
                            public void onReceiveValue(String v) {
                                if (v != null && !v.contains("magi-stream.online")) {
                                    Toast.makeText(MainActivity.this, "DIAG " + v.replace("\"", ""), Toast.LENGTH_LONG).show();
                                }
                            }
                        });
                    } catch (Exception ignored) {
                        // diagnostic impossible
                    }
                }
            }, d);
        }
    }

    /**
     * Si le site ne répond pas du tout (Wi-Fi sans internet, réseau bloqué), le chargement peut durer très
     * longtemps sur un écran noir : on bascule alors sur la page hors connexion.
     */

    private void watchSiteLoad(final WebView wv) {
        new Handler(Looper.getMainLooper()).postDelayed(new Runnable() {
            @Override
            public void run() {
                try {
                    String u = wv.getUrl();
                    boolean onSiteOrBlank = u == null || u.equals("about:blank") || u.startsWith("https://www.magi-stream.online");
                    if (onSiteOrBlank && wv.getProgress() < 25) wv.loadUrl(OFFLINE_URL);
                } catch (Exception ignored) {
                    // page déjà détruite : rien à faire
                }
            }
        }, SITE_TIMEOUT_MS);
    }

    /**
     * Petite interface pour la page « hors connexion » (app/www/offline.html).
     * Cette page est locale : le pont Capacitor n'y est pas actif, elle passe donc par ici.
     */
    /** Page à ouvrir après un clic sur une notification (lue par le site au démarrage). */
    static String pendingPath = null;

    private void readPath(Intent i) {
        if (i == null) return;
        String p = i.getStringExtra("magi_path");
        if (p != null && p.startsWith("/")) {
            pendingPath = p;
            i.removeExtra("magi_path");
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        readPath(intent);
        if (pendingPath != null) {
            try {
                final String path = pendingPath;
                pendingPath = null;
                getBridge().getWebView().loadUrl("https://www.magi-stream.online" + path);
            } catch (Exception ignored) {
                // le site lira pendingPath au prochain démarrage
            }
        }
    }

    class OfflineApi {
        private final Context ctx;

        OfflineApi(Context ctx) {
            this.ctx = ctx;
        }

        /** Épisodes téléchargés (JSON). */
        @JavascriptInterface
        public String list() {
            return DownloadStore.doneJson(ctx);
        }

        /** Supprime un épisode téléchargé (fichier + fiche), pour la page hors connexion. */
        @JavascriptInterface
        public void remove(int episodeId) {
            try {
                DownloadService.cancel(ctx, episodeId);
                DownloadService.deleteFiles(ctx, episodeId);
                DownloadStore.remove(ctx, episodeId);
            } catch (Exception ignored) {
                // suppression impossible : la page affichera l'erreur au rechargement de la liste
            }
        }

        /** Plein écran : paysage + barres système masquées, ou retour au mode normal. */
        @JavascriptInterface
        public void setFullscreen(final boolean on) {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    setRequestedOrientation(on
                            ? ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
                            : ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED);
                    WindowInsetsControllerCompat c =
                            WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
                    if (on) {
                        c.setSystemBarsBehavior(WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
                        c.hide(WindowInsetsCompat.Type.systemBars());
                    } else {
                        c.show(WindowInsetsCompat.Type.systemBars());
                    }
                }
            });
        }

        /** Numéro de version de l'application installée (= numéro de build GitHub). */
        @JavascriptInterface
        public int appVersion() {
            try {
                PackageInfo pi = ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0);
                return (int) (android.os.Build.VERSION.SDK_INT >= 28 ? pi.getLongVersionCode() : pi.versionCode);
            } catch (Exception e) {
                return 0;
            }
        }

        /** Ouvre un lien https dans le navigateur du téléphone (téléchargement de la mise à jour). */
        @JavascriptInterface
        public void openExternal(final String url) {
            if (url == null || !url.startsWith("https://")) return;
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                    } catch (Exception ignored) {
                        // aucun navigateur : rien à faire
                    }
                }
            });
        }

        /** true si la connexion active est du Wi-Fi (ou Ethernet) ; utilisé par « Wi-Fi seulement ». */
        @JavascriptInterface
        public boolean isWifi() {
            try {
                ConnectivityManager cm = (ConnectivityManager) ctx.getSystemService(Context.CONNECTIVITY_SERVICE);
                Network n = cm.getActiveNetwork();
                if (n == null) return false;
                NetworkCapabilities c = cm.getNetworkCapabilities(n);
                return c != null && (c.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
                        || c.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET));
            } catch (Exception e) {
                return true; // doute : on ne bloque pas le téléchargement
            }
        }

        /** Le site donne l'adresse de l'API : active les notifications du bot (vérification toutes les ~15 min). */
        @JavascriptInterface
        public void configure(String apiBase) {
            if (apiBase == null || !apiBase.startsWith("https://")) return;
            ctx.getSharedPreferences(MagiNotifyWorker.PREFS, Context.MODE_PRIVATE).edit().putString("api", apiBase).apply();
            try {
                MagiNotifyWorker.schedule(ctx);
                MagiFirebaseService.syncToken(ctx);
            } catch (Exception ignored) {
                // WorkManager indisponible : pas de notifications
            }
        }

        /** Page demandée par un clic sur une notification (une seule lecture). */
        @JavascriptInterface
        public String consumeOpenPath() {
            String p = pendingPath;
            pendingPath = null;
            return p == null ? "" : p;
        }

        /** Dernière pub « hors ligne » (JSON avec image en data-URL), gardée pour la page sans connexion. */
        @JavascriptInterface
        public void saveOfflineAd(String json) {
            if (json == null || json.length() > 3_000_000) return;
            ctx.getSharedPreferences(MagiNotifyWorker.PREFS, Context.MODE_PRIVATE).edit().putString("offline_ad", json).apply();
        }

        @JavascriptInterface
        public String getOfflineAd() {
            return ctx.getSharedPreferences(MagiNotifyWorker.PREFS, Context.MODE_PRIVATE).getString("offline_ad", "");
        }

        /** Vignettes paysage des animés téléchargés (data-URL JPEG réduites), par identifiant d'animé. */
        @JavascriptInterface
        public void saveCover(String animeId, String dataUrl) {
            if (animeId == null || dataUrl == null || dataUrl.length() > 400_000) return;
            ctx.getSharedPreferences("magi_covers", Context.MODE_PRIVATE).edit().putString(animeId, dataUrl).apply();
        }

        @JavascriptInterface
        public void removeCover(String animeId) {
            if (animeId == null) return;
            ctx.getSharedPreferences("magi_covers", Context.MODE_PRIVATE).edit().remove(animeId).apply();
        }

        @JavascriptInterface
        public String getCovers() {
            java.util.Map<String, ?> all = ctx.getSharedPreferences("magi_covers", Context.MODE_PRIVATE).getAll();
            org.json.JSONObject o = new org.json.JSONObject();
            try {
                for (java.util.Map.Entry<String, ?> e : all.entrySet()) {
                    if (e.getValue() instanceof String) o.put(e.getKey(), (String) e.getValue());
                }
            } catch (Exception ignored) {
            }
            return o.toString();
        }

        /** Garde l'écran allumé pendant la lecture. */
        @JavascriptInterface
        public void keepAwake(final boolean on) {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    if (on) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                    else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                }
            });
        }
    }

    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(MagiDownloaderPlugin.class);
        super.onCreate(savedInstanceState);
        try {
            WebView webView = getBridge().getWebView();
            webView.addJavascriptInterface(new OfflineApi(getApplicationContext()), "MagiNative");
        } catch (Exception ignored) {
            // la page hors connexion affichera alors un message d'erreur
        }

        // Pas d'accès réel à internet : page hors connexion tout de suite, au lieu d'attendre sur un écran noir
        // que le chargement du site échoue. Sinon, on surveille que le site répond bien.
        try {
            WebView wv = getBridge().getWebView();
            if (!hasInternet()) wv.loadUrl(OFFLINE_URL);
            else watchSiteLoad(wv);
            diagToast(wv);
        } catch (Exception ignored) {
            // pont indisponible : Capacitor garde son comportement par défaut
        }

        readPath(getIntent());

        // Android 13+ : autorisation d'afficher les notifications (téléchargements et nouveautés)
        if (android.os.Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, 4242);
        }

        // Bouton « retour » : revient à la page précédente ; il faut le presser deux fois de suite pour quitter l'app.
        // (ajouté après celui de Capacitor : il passe en premier)
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                final WebView wv = getBridge().getWebView();
                if (wv.canGoBack()) {
                    wv.goBack();
                    return;
                }
                // Historique du site (pages ouvertes sans rechargement) : on laisse la page revenir en arrière
                wv.evaluateJavascript("(function(){return history.length})()", new ValueCallback<String>() {
                    @Override
                    public void onReceiveValue(String value) {
                        int n = 0;
                        try {
                            n = Integer.parseInt(value.replace("\"", "").trim());
                        } catch (Exception ignored) {
                            // valeur illisible : on considère qu'il n'y a pas d'historique
                        }
                        if (n > 1) {
                            wv.evaluateJavascript("history.back()", null);
                            return;
                        }
                        long now = System.currentTimeMillis();
                        if (now - lastBack < 2000) {
                            finish();
                        } else {
                            lastBack = now;
                            Toast.makeText(MainActivity.this, "Appuie encore une fois pour quitter", Toast.LENGTH_SHORT).show();
                        }
                    }
                });
            }
        });
    }
}
