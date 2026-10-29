package online.magistream.app;

import android.content.Context;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    /**
     * Petite interface en lecture seule pour la page « hors connexion » (app/www/offline.html).
     * Cette page est locale : le pont Capacitor n'y est pas actif, elle lit donc la liste ici.
     */
    static class OfflineApi {
        private final Context ctx;

        OfflineApi(Context ctx) {
            this.ctx = ctx;
        }

        @JavascriptInterface
        public String list() {
            return DownloadStore.doneJson(ctx);
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
    }
}
