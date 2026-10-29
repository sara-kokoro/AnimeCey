package online.magistream.app;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(MagiDownloaderPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
