package com.apkconverter.agent;

import android.Manifest;
import android.app.Activity;
import android.content.ClipboardManager;
import android.content.ClipData;
import android.content.Context;
import android.media.projection.MediaProjectionManager;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.provider.Settings;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    static final String ACTION_REQUEST_SCREEN_CAPTURE = "com.apkconverter.agent.REQUEST_SCREEN_CAPTURE";
    private static final int REQUEST_SCREEN_CAPTURE = 200;

    private EditText serverUrlInput;
    private EditText pairingCodeInput;
    private EditText ownerIdInput;
    private EditText tokenInput;
    private EditText deviceNameInput;
    private TextView permissionsText;
    private TextView statusText;
    private TextView deviceIdText;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestNotificationPermission();
        setContentView(buildContentView());
        loadPrefs();
        renderStatus();
        if (ACTION_REQUEST_SCREEN_CAPTURE.equals(getIntent().getAction())) {
            requestScreenCapture();
        } else {
            handlePairIntent(getIntent(), true);
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handlePairIntent(intent, true);
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private ScrollView buildContentView() {
        int padding = dp(16);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(padding, padding, padding, padding);
        root.setGravity(Gravity.CENTER_HORIZONTAL);

        TextView title = new TextView(this);
        title.setText("APK Device Agent");
        title.setTextSize(26);
        title.setGravity(Gravity.START);
        root.addView(title, matchWidth());

        TextView subtitle = new TextView(this);
        subtitle.setText("Подключает этот Android к мини-аппу через heartbeat.");
        subtitle.setTextSize(14);
        subtitle.setPadding(0, dp(6), 0, dp(14));
        root.addView(subtitle, matchWidth());

        permissionsText = new TextView(this);
        permissionsText.setTextSize(14);
        permissionsText.setPadding(0, 0, 0, dp(12));
        root.addView(permissionsText, matchWidth());

        serverUrlInput = input("Server URL, например http://192.168.1.10:8080");
        pairingCodeInput = input("Код из /pair");
        ownerIdInput = input("Owner ID из команды /myid");
        tokenInput = input("DEVICE_API_TOKEN, если pairing не используется");
        deviceNameInput = input("Имя устройства");

        root.addView(label("Server URL"));
        root.addView(serverUrlInput, matchWidth());
        root.addView(label("Pairing code"));
        root.addView(pairingCodeInput, matchWidth());
        root.addView(label("Owner ID"));
        root.addView(ownerIdInput, matchWidth());
        root.addView(label("Token"));
        root.addView(tokenInput, matchWidth());
        root.addView(label("Device name"));
        root.addView(deviceNameInput, matchWidth());

        Button saveButton = button("Сохранить");
        saveButton.setOnClickListener(view -> {
            savePrefs();
            renderStatus();
        });

        Button pairButton = button("Pair по коду");
        pairButton.setOnClickListener(view -> {
            savePrefs();
            pairWithCurrentCode();
        });

        Button pasteButton = button("Вставить ссылку/код");
        pasteButton.setOnClickListener(view -> pastePairFromClipboard());

        Button startButton = button("Старт агента");
        startButton.setOnClickListener(view -> {
            savePrefs();
            Intent intent = new Intent(this, HeartbeatService.class).setAction(HeartbeatService.ACTION_START);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent);
            } else {
                startService(intent);
            }
            renderStatus();
        });

        Button stopButton = button("Стоп агента");
        stopButton.setOnClickListener(view -> {
            startService(new Intent(this, HeartbeatService.class).setAction(HeartbeatService.ACTION_STOP));
            renderStatus();
        });

        Button testButton = button("Тест heartbeat");
        testButton.setOnClickListener(view -> {
            savePrefs();
            statusText.setText("Проверяю...");
            executor.execute(() -> {
                try {
                    DeviceApiClient.heartbeat(this);
                    runOnUiThread(() -> statusText.setText("Тест успешен"));
                } catch (Exception exc) {
                    runOnUiThread(() -> statusText.setText("Ошибка теста: " + exc.getMessage()));
                }
            });
        });

        Button accessibilityButton = button("Открыть настройки жестов");
        accessibilityButton.setOnClickListener(view -> {
            Intent intent = new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS);
            startActivity(intent);
        });

        Button setupButton = button("Setup required permissions");
        setupButton.setOnClickListener(view -> startPermissionWizard());

        Button notificationButton = button("Enable notifications");
        notificationButton.setOnClickListener(view -> openNotificationSettings());

        Button screenButton = button("Allow screen view");
        screenButton.setOnClickListener(view -> requestScreenCapture());

        Button batteryButton = button("Battery background settings");
        batteryButton.setOnClickListener(view -> openBatterySettings());

        root.addView(saveButton, matchWidthWithTopMargin());
        root.addView(pasteButton, matchWidthWithTopMargin());
        root.addView(pairButton, matchWidthWithTopMargin());
        root.addView(setupButton, matchWidthWithTopMargin());
        root.addView(notificationButton, matchWidthWithTopMargin());
        root.addView(startButton, matchWidthWithTopMargin());
        root.addView(stopButton, matchWidthWithTopMargin());
        root.addView(testButton, matchWidthWithTopMargin());
        root.addView(screenButton, matchWidthWithTopMargin());
        root.addView(accessibilityButton, matchWidthWithTopMargin());
        root.addView(batteryButton, matchWidthWithTopMargin());

        deviceIdText = new TextView(this);
        deviceIdText.setTextSize(13);
        deviceIdText.setPadding(0, dp(18), 0, dp(8));
        root.addView(deviceIdText, matchWidth());

        statusText = new TextView(this);
        statusText.setTextSize(15);
        root.addView(statusText, matchWidth());

        ScrollView scrollView = new ScrollView(this);
        scrollView.addView(root);
        return scrollView;
    }

    private void loadPrefs() {
        SharedPreferences prefs = AgentConfig.prefs(this);
        serverUrlInput.setText(prefs.getString(AgentConfig.KEY_SERVER_URL, "http://192.168.1.10:8080"));
        ownerIdInput.setText(prefs.getString(AgentConfig.KEY_OWNER_ID, ""));
        tokenInput.setText(prefs.getString(AgentConfig.KEY_API_TOKEN, ""));
        deviceNameInput.setText(prefs.getString(AgentConfig.KEY_DEVICE_NAME, AgentConfig.defaultDeviceName()));
    }

    private void savePrefs() {
        AgentConfig.prefs(this)
                .edit()
                .putString(AgentConfig.KEY_SERVER_URL, serverUrlInput.getText().toString().trim())
                .putString(AgentConfig.KEY_OWNER_ID, ownerIdInput.getText().toString().trim())
                .putString(AgentConfig.KEY_API_TOKEN, tokenInput.getText().toString().trim())
                .putString(AgentConfig.KEY_DEVICE_NAME, deviceNameInput.getText().toString().trim())
                .apply();
    }

    private void renderStatus() {
        SharedPreferences prefs = AgentConfig.prefs(this);
        boolean enabled = prefs.getBoolean(AgentConfig.KEY_ENABLED, false);
        String lastStatus = prefs.getString(HeartbeatService.KEY_LAST_STATUS, "Сигнал ещё не отправлялся");
        boolean paired = !prefs.getString(AgentConfig.KEY_DEVICE_SECRET, "").isEmpty();
        boolean notificationsReady = notificationsReady();
        boolean accessibilityReady = TouchControlService.isReady();

        deviceIdText.setText("Device ID: " + AgentConfig.getDeviceId(this));
        permissionsText.setText(
                "Required setup:\n"
                        + "Notifications: " + (notificationsReady ? "ready" : "needs permission") + "\n"
                        + "Gestures/accessibility: " + (accessibilityReady ? "ready" : "open settings and enable APK Agent") + "\n"
                        + "Screen view: tap Allow screen view when you want preview"
        );
        statusText.setText(
                (enabled ? "Агент включён" : "Агент выключен")
                        + "\nPair: " + (paired ? "готов" : "не выполнен")
                        + "\nЖесты: " + (TouchControlService.isReady() ? "включены" : "нужно включить")
                        + "\n" + lastStatus
        );
    }

    private EditText input(String hint) {
        EditText editText = new EditText(this);
        editText.setHint(hint);
        editText.setSingleLine(true);
        editText.setTextSize(15);
        return editText;
    }

    private TextView label(String text) {
        TextView textView = new TextView(this);
        textView.setText(text);
        textView.setTextSize(12);
        textView.setPadding(0, dp(10), 0, 0);
        return textView;
    }

    private Button button(String text) {
        Button button = new Button(this);
        button.setText(text);
        return button;
    }

    private LinearLayout.LayoutParams matchWidth() {
        return new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
    }

    private LinearLayout.LayoutParams matchWidthWithTopMargin() {
        LinearLayout.LayoutParams params = matchWidth();
        params.topMargin = dp(8);
        return params;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 10);
        }
    }

    private boolean notificationsReady() {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU
                || checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
    }

    private void openNotificationSettings() {
        requestNotificationPermission();
        Intent intent;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            intent = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName());
        } else {
            intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                    .setData(Uri.parse("package:" + getPackageName()));
        }
        startActivity(intent);
    }

    private void openAccessibilitySettings() {
        statusText.setText("Enable APK Agent in Accessibility settings, then return here.");
        startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
    }

    private void openBatterySettings() {
        Intent intent = new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS);
        startActivity(intent);
    }

    private void startPermissionWizard() {
        requestNotificationPermission();
        if (!TouchControlService.isReady()) {
            openAccessibilitySettings();
            return;
        }
        requestScreenCapture();
    }

    private void handlePairIntent(Intent intent, boolean autoPair) {
        if (intent == null || intent.getData() == null) {
            return;
        }

        Uri uri = intent.getData();
        if (!"apkagent".equals(uri.getScheme()) || !"pair".equals(uri.getHost())) {
            return;
        }

        String server = uri.getQueryParameter("server");
        String code = uri.getQueryParameter("code");
        if (server != null && !server.trim().isEmpty()) {
            serverUrlInput.setText(server.trim());
        }
        if (code != null && !code.trim().isEmpty()) {
            pairingCodeInput.setText(code.trim());
        }
        savePrefs();

        if (autoPair && code != null && !code.trim().isEmpty()) {
            pairWithCurrentCode();
        }
    }

    private void pairWithCurrentCode() {
        statusText.setText("Подключаю по коду...");
        executor.execute(() -> {
            try {
                DeviceApiClient.claimPairingCode(this, pairingCodeInput.getText().toString());
                runOnUiThread(() -> {
                    loadPrefs();
                    pairingCodeInput.setText("");
                    statusText.setText("Pair успешен. Теперь можно нажать Старт агента.");
                });
            } catch (Exception exc) {
                runOnUiThread(() -> statusText.setText("Pair ошибка: " + exc.getMessage()));
            }
        });
    }

    private void pastePairFromClipboard() {
        ClipboardManager manager = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (manager == null || !manager.hasPrimaryClip()) {
            statusText.setText("Буфер обмена пуст");
            return;
        }

        ClipData clipData = manager.getPrimaryClip();
        if (clipData == null || clipData.getItemCount() == 0) {
            statusText.setText("Буфер обмена пуст");
            return;
        }

        String text = String.valueOf(clipData.getItemAt(0).coerceToText(this)).trim();
        if (text.startsWith("apkagent://")) {
            handlePairIntent(new Intent(Intent.ACTION_VIEW, Uri.parse(text)), false);
            statusText.setText("Ссылка вставлена. Нажми Pair по коду.");
        } else if (text.matches("\\d{6}")) {
            pairingCodeInput.setText(text);
            statusText.setText("Код вставлен. Проверь Server URL и нажми Pair.");
        } else {
            statusText.setText("Не похоже на pairing ссылку или 6-значный код");
        }
    }

    private void requestScreenCapture() {
        MediaProjectionManager manager = (MediaProjectionManager) getSystemService(MEDIA_PROJECTION_SERVICE);
        startActivityForResult(manager.createScreenCaptureIntent(), REQUEST_SCREEN_CAPTURE);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_SCREEN_CAPTURE) {
            return;
        }

        if (resultCode != RESULT_OK || data == null) {
            statusText.setText("Разрешение на экран не выдано");
            return;
        }

        Intent intent = new Intent(this, ScreenCaptureService.class)
                .setAction(ScreenCaptureService.ACTION_START)
                .putExtra(ScreenCaptureService.EXTRA_RESULT_CODE, resultCode)
                .putExtra(ScreenCaptureService.EXTRA_RESULT_DATA, data);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent);
        } else {
            startService(intent);
        }
        statusText.setText("Передача экрана запущена");
    }
}
