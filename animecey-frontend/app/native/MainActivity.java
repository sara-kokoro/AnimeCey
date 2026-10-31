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

    /**
     * Petite interface pour la page « hors connexion » (app/www/offline.html).
     * Cette page est locale : le pont Capacitor n'y est pas actif, elle passe donc par ici.
     */
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
