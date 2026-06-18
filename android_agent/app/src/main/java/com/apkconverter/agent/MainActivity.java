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
import android.os.PowerManager;
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
        title.setText("Hunter Android Agent");
        title.setTextSize(26);
        title.setGravity(Gravity.START);
        root.addView(title, matchWidth());

        TextView subtitle = new TextView(this);
        subtitle.setText("Подключает этот телефон к Telegram-боту и мини-апу. Управление работает только после твоих разрешений.");
        subtitle.setTextSize(14);
        subtitle.setPadding(0, dp(6), 0, dp(14));
        root.addView(subtitle, matchWidth());

        permissionsText = new TextView(this);
        permissionsText.setTextSize(14);
        permissionsText.setPadding(0, 0, 0, dp(12));
        root.addView(permissionsText, matchWidth());

        serverUrlInput = input("Server URL, например https://web-production-715d7.up.railway.app");
        pairingCodeInput = input("Код из QR или команды /pair");
        ownerIdInput = input("Owner ID, заполняется после QR");
        tokenInput = input("Токен не нужен при подключении через QR");
        deviceNameInput = input("Имя устройства, например POCO C75");

        root.addView(label("Сервер"));
        root.addView(serverUrlInput, matchWidth());
        root.addView(label("Код подключения"));
        root.addView(pairingCodeInput, matchWidth());
        root.addView(label("Owner ID"));
        root.addView(ownerIdInput, matchWidth());
        root.addView(label("Токен, резервный режим"));
        root.addView(tokenInput, matchWidth());
        root.addView(label("Имя устройства"));
        root.addView(deviceNameInput, matchWidth());

        Button saveButton = button("Сохранить настройки");
        saveButton.setOnClickListener(view -> {
            savePrefs();
            renderStatus();
        });

        Button pairButton = button("Подключить по коду");
        pairButton.setOnClickListener(view -> {
            savePrefs();
            pairWithCurrentCode();
        });

        Button pasteButton = button("Вставить QR-ссылку или код");
        pasteButton.setOnClickListener(view -> pastePairFromClipboard());

        Button startButton = button("Запустить агент");
        startButton.setOnClickListener(view -> {
            savePrefs();
            startAgentService();
            renderStatus();
        });

        Button stopButton = button("Остановить агент");
        stopButton.setOnClickListener(view -> {
            startService(new Intent(this, HeartbeatService.class).setAction(HeartbeatService.ACTION_STOP));
            renderStatus();
        });

        Button testButton = button("Проверить связь");
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

        Button accessibilityButton = button("Разрешить жесты и тапы");
        accessibilityButton.setOnClickListener(view -> {
            Intent intent = new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS);
            startActivity(intent);
        });

        Button setupButton = button("Открыть мастер разрешений");
        setupButton.setOnClickListener(view -> startPermissionWizard());

        Button notificationButton = button("Разрешить уведомления");
        notificationButton.setOnClickListener(view -> openNotificationSettings());

        Button screenButton = button("Разрешить просмотр экрана");
        screenButton.setOnClickListener(view -> requestScreenCapture());

        Button batteryButton = button("Разрешить работу в фоне");
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
        boolean batteryReady = batteryReady();

        deviceIdText.setText("Device ID: " + AgentConfig.getDeviceId(this));
        permissionsText.setText(
                "Разрешения:\n"
                        + "Уведомления: " + (notificationsReady ? "готово" : "нужно разрешить") + "\n"
                        + "Работа в фоне: " + (batteryReady ? "готово" : "нужно отключить оптимизацию батареи") + "\n"
                        + "Жесты/Accessibility: " + (accessibilityReady ? "готово" : "открой настройки и включи Hunter Agent") + "\n"
                        + "Экран: нажми «Разрешить просмотр экрана», когда нужен preview"
        );
        statusText.setText(
                (enabled ? "Агент включён" : "Агент выключен")
                        + "\nПодключение: " + (paired ? "готово" : "нужно открыть QR или ввести код")
                        + "\nЖесты: " + (TouchControlService.isReady() ? "включены" : "нужно включить вручную")
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

    private boolean batteryReady() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) {
            return true;
        }
        PowerManager manager = (PowerManager) getSystemService(Context.POWER_SERVICE);
        return manager == null || manager.isIgnoringBatteryOptimizations(getPackageName());
    }

    private void startAgentService() {
        Intent intent = new Intent(this, HeartbeatService.class).setAction(HeartbeatService.ACTION_START);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent);
        } else {
            startService(intent);
        }
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
        statusText.setText("В настройках Accessibility включи Hunter Agent, затем вернись сюда.");
        startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
    }

    private void openBatterySettings() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !batteryReady()) {
                Intent intent = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
                        .setData(Uri.parse("package:" + getPackageName()));
                startActivity(intent);
                return;
            }
            startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));
        } catch (Exception exc) {
            Intent fallback = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                    .setData(Uri.parse("package:" + getPackageName()));
            startActivity(fallback);
        }
    }

    private void startPermissionWizard() {
        requestNotificationPermission();
        if (!batteryReady()) {
            statusText.setText("Шаг 1: разреши работу в фоне, чтобы Android не останавливал агент.");
            openBatterySettings();
            return;
        }
        if (!TouchControlService.isReady()) {
            statusText.setText("Шаг 2: включи Accessibility, если нужны тапы, свайпы и кнопки Back/Home.");
            openAccessibilitySettings();
            return;
        }
        statusText.setText("Шаг 3: подтверди просмотр экрана, если хочешь видеть экран в мини-апе.");
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
                    statusText.setText("Подключение успешно. Агент запускается и открывает мастер разрешений.");
                    startAgentService();
                    renderStatus();
                    startPermissionWizard();
                });
            } catch (Exception exc) {
                runOnUiThread(() -> statusText.setText("Ошибка подключения: " + exc.getMessage()));
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
