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
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
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
    private Switch agentSwitch;
    private Switch notificationSwitch;
    private Switch batterySwitch;
    private Switch accessibilitySwitch;
    private Switch screenSwitch;
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
    protected void onResume() {
        super.onResume();
        if (AgentConfig.prefs(this).getBoolean(AgentConfig.KEY_ENABLED, false)) {
            AgentStarter.start(this);
        }
        renderStatus();
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private ScrollView buildContentView() {
        int padding = dp(16);

        ScrollView scrollView = new ScrollView(this);
        scrollView.setBackgroundColor(Color.rgb(245, 247, 251));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(padding, padding, padding, padding);
        root.setGravity(Gravity.CENTER_HORIZONTAL);

        LinearLayout hero = card();
        TextView title = text("Hunter Android Agent", 26, Color.rgb(9, 32, 40), true);
        TextView mode = badge(BuildConfig.FULL_CONTROL ? "FULL CONTROL" : "LITE");
        TextView subtitle = text(
                BuildConfig.FULL_CONTROL
                        ? "Полный режим: экран, жесты и управление после твоих разрешений."
                        : "Lite режим: безопасное подключение, QR и статус без экрана и жестов.",
                14,
                Color.rgb(82, 99, 112),
                false
        );
        hero.addView(title, matchWidth());
        hero.addView(mode, matchWidthWithTopMargin(6));
        hero.addView(subtitle, matchWidthWithTopMargin(8));
        root.addView(hero, matchWidth());

        LinearLayout connectCard = card();
        connectCard.addView(sectionTitle("Подключение"));

        permissionsText = new TextView(this);
        permissionsText.setTextSize(14);
        permissionsText.setTextColor(Color.rgb(82, 99, 112));

        serverUrlInput = input("Server URL, например https://web-production-715d7.up.railway.app");
        pairingCodeInput = input("Код из QR или команды /pair");
        ownerIdInput = input("Owner ID, заполняется после QR");
        tokenInput = input("Токен не нужен при подключении через QR");
        deviceNameInput = input("Имя устройства, например POCO C75");

        addField(connectCard, "Сервер", serverUrlInput);
        addField(connectCard, "Код подключения", pairingCodeInput);
        addField(connectCard, "Owner ID", ownerIdInput);
        addField(connectCard, "Токен, резервный режим", tokenInput);
        addField(connectCard, "Имя устройства", deviceNameInput);

        Button saveButton = primaryButton("Сохранить настройки");
        saveButton.setOnClickListener(view -> {
            savePrefs();
            renderStatus();
        });

        Button pairButton = primaryButton("Подключить по коду");
        pairButton.setOnClickListener(view -> {
            savePrefs();
            pairWithCurrentCode();
        });

        Button pasteButton = secondaryButton("Вставить QR-ссылку или код");
        pasteButton.setOnClickListener(view -> pastePairFromClipboard());

        connectCard.addView(saveButton, matchWidthWithTopMargin());
        connectCard.addView(pasteButton, matchWidthWithTopMargin());
        connectCard.addView(pairButton, matchWidthWithTopMargin());
        root.addView(connectCard, matchWidthWithTopMargin(12));

        LinearLayout togglesCard = card();
        togglesCard.addView(sectionTitle("Переключатели"));
        agentSwitch = switchRow("Агент работает в фоне");
        agentSwitch.setOnClickListener(view -> {
            savePrefs();
            if (agentSwitch.isChecked()) {
                startAgentService();
            } else {
                AgentStarter.stop(this);
            }
            renderStatus();
        });

        notificationSwitch = switchRow("Уведомления");
        notificationSwitch.setOnClickListener(view -> {
            openNotificationSettings();
            renderStatus();
        });

        batterySwitch = switchRow(BuildConfig.FULL_CONTROL ? "Не ограничивать фон" : "Фон без автозапуска в Lite");
        batterySwitch.setOnClickListener(view -> {
            openBatterySettings();
            renderStatus();
        });

        accessibilitySwitch = switchRow(BuildConfig.FULL_CONTROL ? "Жесты и тапы" : "Жесты отключены в Lite");
        accessibilitySwitch.setOnClickListener(view -> {
            openAccessibilitySettings();
            renderStatus();
        });

        screenSwitch = switchRow(BuildConfig.FULL_CONTROL ? "Передача экрана" : "Экран отключен в Lite");
        screenSwitch.setOnClickListener(view -> {
            requestScreenCapture();
            renderStatus();
        });

        togglesCard.addView(agentSwitch, matchWidthWithTopMargin(8));
        togglesCard.addView(notificationSwitch, matchWidthWithTopMargin(6));
        togglesCard.addView(batterySwitch, matchWidthWithTopMargin(6));
        togglesCard.addView(accessibilitySwitch, matchWidthWithTopMargin(6));
        togglesCard.addView(screenSwitch, matchWidthWithTopMargin(6));
        togglesCard.addView(permissionsText, matchWidthWithTopMargin(10));
        root.addView(togglesCard, matchWidthWithTopMargin(12));

        LinearLayout actionsCard = card();
        actionsCard.addView(sectionTitle("Действия"));

        Button setupButton = primaryButton(BuildConfig.FULL_CONTROL ? "Мастер разрешений" : "Проверить Lite режим");
        setupButton.setOnClickListener(view -> startPermissionWizard());

        Button testButton = secondaryButton("Проверить связь");
        testButton.setOnClickListener(view -> {
            savePrefs();
            setStatus("Проверяю связь...");
            executor.execute(() -> {
                try {
                    DeviceApiClient.heartbeat(this);
                    runOnUiThread(() -> setStatus("Тест успешен. Сервер принимает устройство."));
                } catch (Exception exc) {
                    runOnUiThread(() -> setStatus("Ошибка теста: " + exc.getMessage()));
                }
            });
        });

        Button accessibilityButton = secondaryButton("Открыть Accessibility");
        accessibilityButton.setOnClickListener(view -> {
            openAccessibilitySettings();
            renderStatus();
        });

        Button notificationButton = secondaryButton("Открыть уведомления");
        notificationButton.setOnClickListener(view -> openNotificationSettings());

        Button screenButton = secondaryButton(BuildConfig.FULL_CONTROL ? "Запустить экран" : "Экран недоступен в Lite");
        screenButton.setOnClickListener(view -> requestScreenCapture());

        Button batteryButton = secondaryButton(BuildConfig.FULL_CONTROL ? "Настроить фон" : "Фон без автозапуска в Lite");
        batteryButton.setOnClickListener(view -> openBatterySettings());

        actionsCard.addView(setupButton, matchWidthWithTopMargin());
        actionsCard.addView(testButton, matchWidthWithTopMargin());
        actionsCard.addView(screenButton, matchWidthWithTopMargin());
        actionsCard.addView(accessibilityButton, matchWidthWithTopMargin());
        actionsCard.addView(notificationButton, matchWidthWithTopMargin());
        actionsCard.addView(batteryButton, matchWidthWithTopMargin());
        root.addView(actionsCard, matchWidthWithTopMargin(12));

        deviceIdText = new TextView(this);
        deviceIdText.setTextSize(13);
        deviceIdText.setTextColor(Color.rgb(82, 99, 112));

        statusText = new TextView(this);
        statusText.setTextSize(15);
        statusText.setTextColor(Color.rgb(9, 32, 40));
        statusText.setPadding(0, dp(8), 0, 0);

        LinearLayout statusCard = card();
        statusCard.addView(sectionTitle("Статус"));
        statusCard.addView(deviceIdText, matchWidth());
        statusCard.addView(statusText, matchWidth());
        root.addView(statusCard, matchWidthWithTopMargin(12));

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
        boolean accessibilityReady = BuildConfig.FULL_CONTROL && TouchControlService.isReady();
        boolean batteryReady = !BuildConfig.FULL_CONTROL || batteryReady();

        if (agentSwitch != null) {
            agentSwitch.setChecked(enabled);
        }
        if (notificationSwitch != null) {
            notificationSwitch.setChecked(notificationsReady);
        }
        if (batterySwitch != null) {
            batterySwitch.setChecked(batteryReady);
        }
        if (accessibilitySwitch != null) {
            accessibilitySwitch.setChecked(accessibilityReady);
        }
        if (screenSwitch != null) {
            screenSwitch.setChecked(false);
        }

        deviceIdText.setText("Device ID: " + AgentConfig.getDeviceId(this));
        permissionsText.setText(
                "Разрешения:\n"
                        + "Уведомления: " + (notificationsReady ? "готово" : "нужно разрешить") + "\n"
                        + "Работа в фоне: " + (batteryReady ? "готово" : "нужно отключить оптимизацию батареи") + "\n"
                        + "Жесты/Accessibility: " + (BuildConfig.FULL_CONTROL ? (accessibilityReady ? "готово" : "открой настройки и включи Hunter Agent") : "отключено в Lite") + "\n"
                        + "Экран: " + (BuildConfig.FULL_CONTROL ? "нажми «Разрешить просмотр экрана», когда нужен preview" : "отключен в Lite")
        );
        statusText.setText(
                (enabled ? "Агент включён" : "Агент выключен")
                        + "\nПодключение: " + (paired ? "готово" : "нужно открыть QR или ввести код")
                        + "\nРежим: " + (BuildConfig.FULL_CONTROL ? "полный" : "Lite")
                        + "\nЖесты: " + (BuildConfig.FULL_CONTROL ? (TouchControlService.isReady() ? "включены" : "нужно включить вручную") : "отключены")
                        + "\n" + lastStatus
        );
    }

    private void setStatus(String text) {
        statusText.setText(text);
    }

    private LinearLayout card() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(dp(16), dp(14), dp(16), dp(14));
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.WHITE);
        background.setCornerRadius(dp(14));
        background.setStroke(dp(1), Color.rgb(221, 229, 236));
        layout.setBackground(background);
        return layout;
    }

    private TextView text(String value, int size, int color, boolean bold) {
        TextView textView = new TextView(this);
        textView.setText(value);
        textView.setTextSize(size);
        textView.setTextColor(color);
        if (bold) {
            textView.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        }
        return textView;
    }

    private TextView sectionTitle(String value) {
        TextView textView = text(value, 17, Color.rgb(9, 32, 40), true);
        textView.setPadding(0, 0, 0, dp(6));
        return textView;
    }

    private TextView badge(String value) {
        TextView textView = text(value, 12, BuildConfig.FULL_CONTROL ? Color.WHITE : Color.rgb(9, 96, 104), true);
        textView.setGravity(Gravity.CENTER);
        textView.setPadding(dp(10), dp(5), dp(10), dp(5));
        GradientDrawable background = new GradientDrawable();
        background.setColor(BuildConfig.FULL_CONTROL ? Color.rgb(14, 124, 134) : Color.rgb(218, 246, 242));
        background.setCornerRadius(dp(999));
        textView.setBackground(background);
        return textView;
    }

    private void addField(LinearLayout parent, String title, EditText editText) {
        parent.addView(label(title));
        parent.addView(editText, matchWidth());
    }

    private Switch switchRow(String text) {
        Switch row = new Switch(this);
        row.setText(text);
        row.setTextSize(15);
        row.setTextColor(Color.rgb(9, 32, 40));
        row.setPadding(0, dp(4), 0, dp(4));
        return row;
    }

    private EditText input(String hint) {
        EditText editText = new EditText(this);
        editText.setHint(hint);
        editText.setSingleLine(true);
        editText.setTextSize(15);
        editText.setPadding(dp(12), dp(10), dp(12), dp(10));
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.rgb(248, 251, 253));
        background.setCornerRadius(dp(10));
        background.setStroke(dp(1), Color.rgb(221, 229, 236));
        editText.setBackground(background);
        return editText;
    }

    private TextView label(String text) {
        TextView textView = new TextView(this);
        textView.setText(text);
        textView.setTextSize(12);
        textView.setTextColor(Color.rgb(82, 99, 112));
        textView.setPadding(0, dp(10), 0, dp(4));
        return textView;
    }

    private Button button(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        button.setTextSize(14);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setMinHeight(dp(46));
        return button;
    }

    private Button primaryButton(String text) {
        Button button = button(text);
        button.setTextColor(Color.WHITE);
        GradientDrawable background = new GradientDrawable(
                GradientDrawable.Orientation.LEFT_RIGHT,
                new int[]{Color.rgb(14, 124, 134), Color.rgb(47, 183, 160)}
        );
        background.setCornerRadius(dp(12));
        button.setBackground(background);
        return button;
    }

    private Button secondaryButton(String text) {
        Button button = button(text);
        button.setTextColor(Color.rgb(14, 124, 134));
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.rgb(235, 247, 248));
        background.setCornerRadius(dp(12));
        background.setStroke(dp(1), Color.rgb(190, 225, 226));
        button.setBackground(background);
        return button;
    }

    private LinearLayout.LayoutParams matchWidth() {
        return new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
    }

    private LinearLayout.LayoutParams matchWidthWithTopMargin() {
        return matchWidthWithTopMargin(8);
    }

    private LinearLayout.LayoutParams matchWidthWithTopMargin(int topMarginDp) {
        LinearLayout.LayoutParams params = matchWidth();
        params.topMargin = dp(topMarginDp);
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
        AgentStarter.start(this);
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
        if (!BuildConfig.FULL_CONTROL) {
            statusText.setText("Lite-сборка не запрашивает Accessibility, чтобы установка была безопаснее.");
            return;
        }
        statusText.setText("В настройках Accessibility включи Hunter Agent, затем вернись сюда.");
        startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
    }

    private void openBatterySettings() {
        if (!BuildConfig.FULL_CONTROL) {
            statusText.setText("Lite-сборка не запрашивает отключение оптимизации батареи. Для связи держи агент запущенным.");
            return;
        }
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
        if (!BuildConfig.FULL_CONTROL) {
            statusText.setText("Lite-режим готов: подключение и heartbeat работают без доступа к экрану, жестам и автозапуску.");
            return;
        }
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
        if (!BuildConfig.FULL_CONTROL) {
            statusText.setText("Просмотр экрана отключен в Lite-сборке. Для него нужна отдельная полная сборка.");
            return;
        }
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
        if (screenSwitch != null) {
            screenSwitch.setChecked(true);
        }
        statusText.setText("Передача экрана запущена");
    }
}
