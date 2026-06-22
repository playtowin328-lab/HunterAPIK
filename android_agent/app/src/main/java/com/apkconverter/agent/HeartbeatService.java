package com.apkconverter.agent;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.net.Uri;
import android.provider.Settings;

import java.text.DateFormat;
import java.util.Date;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class HeartbeatService extends Service {
    static final String ACTION_START = "com.apkconverter.agent.START";
    static final String ACTION_STOP = "com.apkconverter.agent.STOP";
    static final String KEY_LAST_STATUS = "last_status";
    static final String KEY_LAST_SUCCESS = "last_success";

    private static final String CHANNEL_ID = "apk_agent_connection";
    private static final int NOTIFICATION_ID = 41;
    private static final long COMMAND_POLL_INTERVAL_MS = 500L;
    private static final int MAX_COMMANDS_PER_TICK = 6;
    private static final long HEARTBEAT_INTERVAL_MS = 15_000L;

    private ScheduledExecutorService executor;
    private PowerManager.WakeLock wakeLock;
    private long lastHeartbeatAt;
    private int consecutiveErrors;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopAgent();
            return START_NOT_STICKY;
        }

        AgentConfig.prefs(this).edit().putBoolean(AgentConfig.KEY_ENABLED, true).apply();
        acquireWakeLock();
        startForeground(NOTIFICATION_ID, buildNotification("Agent online"));
        startHeartbeatLoop();
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        if (executor != null) {
            executor.shutdownNow();
        }
        releaseWakeLock();
        if (AgentConfig.prefs(this).getBoolean(AgentConfig.KEY_ENABLED, false)) {
            AgentStarter.scheduleRestart(this);
        }
        super.onDestroy();
    }

    @Override
    public void onTaskRemoved(Intent rootIntent) {
        if (AgentConfig.prefs(this).getBoolean(AgentConfig.KEY_ENABLED, false)) {
            AgentStarter.scheduleRestart(this);
        }
        super.onTaskRemoved(rootIntent);
    }

    private void startHeartbeatLoop() {
        if (executor != null && !executor.isShutdown()) {
            return;
        }

        executor = Executors.newSingleThreadScheduledExecutor();
        executor.scheduleWithFixedDelay(this::agentTick, 0, COMMAND_POLL_INTERVAL_MS, TimeUnit.MILLISECONDS);
    }

    private void agentTick() {
        long tickStarted = System.currentTimeMillis();
        acquireWakeLock();
        SharedPreferences prefs = AgentConfig.prefs(this);
        SharedPreferences.Editor editor = prefs.edit();
        String timestamp = DateFormat.getTimeInstance(DateFormat.SHORT).format(new Date());
        long now = System.currentTimeMillis();
        boolean shouldHeartbeat = lastHeartbeatAt == 0 || now - lastHeartbeatAt >= HEARTBEAT_INTERVAL_MS;

        try {
            editor.putString(AgentConfig.KEY_LAST_ERROR, "");
            String commandStatus = handlePendingCommands();
            if (shouldHeartbeat) {
                DeviceApiClient.heartbeat(this);
                lastHeartbeatAt = now;
            }
            editor.putString(KEY_LAST_STATUS, "Online - " + timestamp + commandStatus);
            editor.putLong(KEY_LAST_SUCCESS, now);
            editor.putLong(AgentConfig.KEY_LAST_LOOP_MS, System.currentTimeMillis() - tickStarted);
            editor.putInt(AgentConfig.KEY_LAST_ERROR_COUNT, 0);
            consecutiveErrors = 0;
            updateNotification("Online - " + timestamp);
        } catch (Exception exc) {
            int errorCount = prefs.getInt(AgentConfig.KEY_LAST_ERROR_COUNT, 0) + 1;
            consecutiveErrors = Math.max(consecutiveErrors + 1, errorCount);
            editor.putString(KEY_LAST_STATUS, "Error: " + exc.getMessage());
            editor.putLong(AgentConfig.KEY_LAST_LOOP_MS, System.currentTimeMillis() - tickStarted);
            editor.putInt(AgentConfig.KEY_LAST_ERROR_COUNT, errorCount);
            editor.putString(AgentConfig.KEY_LAST_ERROR, String.valueOf(exc.getMessage()));
            updateNotification("Connection error");
            applyErrorBackoff();
        }

        editor.apply();
    }

    private void applyErrorBackoff() {
        long delayMs = Math.min(30_000L, 1_000L * Math.max(1, consecutiveErrors));
        try {
            Thread.sleep(delayMs);
        } catch (InterruptedException exc) {
            Thread.currentThread().interrupt();
        }
    }

    private String handlePendingCommands() throws Exception {
        StringBuilder status = new StringBuilder();
        for (int index = 0; index < MAX_COMMANDS_PER_TICK; index++) {
            DeviceApiClient.RemoteCommand command = DeviceApiClient.nextCommand(this);
            if (command == null) {
                break;
            }
            status.append(handleCommand(command));
        }
        return status.toString();
    }

    private String handleCommand(DeviceApiClient.RemoteCommand command) throws Exception {
        long started = System.currentTimeMillis();
        String result;
        String status = "acknowledged";

        if ("request_screen".equals(command.type)) {
            if (!BuildConfig.FULL_CONTROL) {
                result = "Screen preview is disabled in Lite build.";
                status = "rejected";
            } else if (ScreenCaptureService.isRunning()) {
                result = "Screen capture already running.";
            } else {
                Intent intent = new Intent(this, MainActivity.class)
                        .setAction(MainActivity.ACTION_REQUEST_SCREEN_CAPTURE)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(intent);
                result = "Screen permission requested on device.";
            }
        } else if ("stop_screen".equals(command.type)) {
            if (!BuildConfig.FULL_CONTROL) {
                result = "Screen preview is disabled in Lite build.";
                status = "rejected";
            } else {
                Intent intent = new Intent(this, ScreenCaptureService.class).setAction(ScreenCaptureService.ACTION_STOP);
                startService(intent);
                result = "Screen capture stop requested.";
            }
        } else if ("request_files".equals(command.type)) {
            result = "Files request received. Storage picker module is not enabled yet.";
        } else if ("request_actions".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.isReady()
                    ? "Actions module is ready for taps and navigation."
                    : "Actions are disabled in Lite build.";
        } else if ("tap".equals(command.type)) {
            result = dispatchTap(command);
        } else if ("long_tap".equals(command.type)) {
            result = dispatchLongTap(command);
        } else if ("swipe".equals(command.type)) {
            result = dispatchSwipe(command);
        } else if ("back".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.back() ? "Back dispatched." : "Back failed or disabled in Lite build.";
        } else if ("home".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.home() ? "Home dispatched." : "Home failed or disabled in Lite build.";
        } else if ("recents".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.recents() ? "Recents dispatched." : "Recents failed or disabled in Lite build.";
        } else if ("notifications".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.notifications() ? "Notifications opened." : "Notifications failed or disabled in Lite build.";
        } else if ("quick_settings".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.quickSettings() ? "Quick settings opened." : "Quick settings failed or disabled in Lite build.";
        } else if ("wake_screen".equals(command.type)) {
            result = wakeScreen();
        } else if ("dismiss_keyguard".equals(command.type)) {
            result = requestDismissKeyguard();
        } else if ("blackout_on".equals(command.type)) {
            result = setBlackoutMode(true);
        } else if ("blackout_off".equals(command.type)) {
            result = setBlackoutMode(false);
        } else if ("lock_screen".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.lockScreen() ? "Screen locked." : "Lock screen failed or disabled in Lite build.";
        } else if ("open_settings".equals(command.type)) {
            result = openSystemActivity(Settings.ACTION_SETTINGS) ? "Settings opened." : "Settings open failed.";
        } else if ("open_wifi_settings".equals(command.type)) {
            result = openSystemActivity(Settings.ACTION_WIFI_SETTINGS) ? "Wi-Fi settings opened." : "Wi-Fi settings open failed.";
        } else if ("open_battery_settings".equals(command.type)) {
            result = openSystemActivity(Settings.ACTION_BATTERY_SAVER_SETTINGS) ? "Battery settings opened." : "Battery settings open failed.";
        } else if ("open_url".equals(command.type)) {
            result = openUrl(command.url);
        } else if ("open_app_details".equals(command.type)) {
            result = openAppDetails(command.packageName);
        } else if ("swipe_up".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.swipeNormalized(0.5f, 0.78f, 0.5f, 0.25f)
                    ? "Swipe up dispatched."
                    : "Swipe up failed or disabled in Lite build.";
        } else if ("swipe_down".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.swipeNormalized(0.5f, 0.25f, 0.5f, 0.78f)
                    ? "Swipe down dispatched."
                    : "Swipe down failed or disabled in Lite build.";
        } else if ("swipe_left".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.swipeNormalized(0.82f, 0.5f, 0.18f, 0.5f)
                    ? "Swipe left dispatched."
                    : "Swipe left failed or disabled in Lite build.";
        } else if ("swipe_right".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.swipeNormalized(0.18f, 0.5f, 0.82f, 0.5f)
                    ? "Swipe right dispatched."
                    : "Swipe right failed or disabled in Lite build.";
        } else if ("input_text".equals(command.type)) {
            result = dispatchText(command);
        } else if ("key_enter".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.enter()
                    ? "Enter inserted."
                    : "Enter failed or disabled in Lite build.";
        } else if ("key_delete".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.delete()
                    ? "Delete dispatched."
                    : "Delete failed or disabled in Lite build.";
        } else if ("ping".equals(command.type)) {
            result = "Ping received.";
        } else {
            result = "Unknown command: " + command.type;
            status = "rejected";
        }

        AgentConfig.prefs(this)
                .edit()
                .putLong(AgentConfig.KEY_LAST_COMMAND_MS, System.currentTimeMillis() - started)
                .apply();
        DeviceApiClient.completeCommand(this, command, status, result);
        return "\nCommand: " + command.type + "\n" + result;
    }

    private String dispatchTap(DeviceApiClient.RemoteCommand command) {
        if (!BuildConfig.FULL_CONTROL) {
            return "Tap rejected. Lite build has no Accessibility control.";
        }
        if (!TouchControlService.isReady()) {
            return "Tap rejected. Enable APK Agent Accessibility Service in Android settings.";
        }
        if (command.x < 0 || command.y < 0) {
            return "Tap rejected. Coordinates are missing.";
        }
        return TouchControlService.tapNormalized(command.x, command.y) ? "Tap dispatched." : "Tap dispatch failed.";
    }

    private String dispatchLongTap(DeviceApiClient.RemoteCommand command) {
        if (!BuildConfig.FULL_CONTROL) {
            return "Long tap rejected. Lite build has no Accessibility control.";
        }
        if (!TouchControlService.isReady()) {
            return "Long tap rejected. Enable APK Agent Accessibility Service in Android settings.";
        }
        if (command.x < 0 || command.y < 0) {
            return "Long tap rejected. Coordinates are missing.";
        }
        return TouchControlService.longTapNormalized(command.x, command.y) ? "Long tap dispatched." : "Long tap dispatch failed.";
    }

    private String dispatchSwipe(DeviceApiClient.RemoteCommand command) {
        if (!BuildConfig.FULL_CONTROL) {
            return "Swipe rejected. Lite build has no Accessibility control.";
        }
        if (!TouchControlService.isReady()) {
            return "Swipe rejected. Enable APK Agent Accessibility Service in Android settings.";
        }
        if (command.x < 0 || command.y < 0 || command.endX < 0 || command.endY < 0) {
            return "Swipe rejected. Coordinates are missing.";
        }
        return TouchControlService.swipeNormalized(command.x, command.y, command.endX, command.endY)
                ? "Swipe dispatched."
                : "Swipe dispatch failed.";
    }

    private String dispatchText(DeviceApiClient.RemoteCommand command) {
        if (!BuildConfig.FULL_CONTROL) {
            return "Text input failed. Lite build has no Accessibility control.";
        }
        if (!TouchControlService.isReady()) {
            return "Text input failed. Enable Accessibility Service.";
        }
        if (command.text == null || command.text.isEmpty()) {
            return "Text input failed. Text is empty.";
        }
        return TouchControlService.inputText(command.text)
                ? "Text inserted."
                : "Text input failed. Focus an editable field on the phone.";
    }

    private boolean openSystemActivity(String action) {
        try {
            Intent intent = new Intent(action).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            return true;
        } catch (Exception exc) {
            return false;
        }
    }

    private String wakeScreen() {
        PowerManager powerManager = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (powerManager == null) {
            return "Wake failed. PowerManager unavailable.";
        }
        PowerManager.WakeLock screenWakeLock = powerManager.newWakeLock(
                PowerManager.SCREEN_BRIGHT_WAKE_LOCK
                        | PowerManager.ACQUIRE_CAUSES_WAKEUP
                        | PowerManager.ON_AFTER_RELEASE,
                "apkconverter:wake-screen"
        );
        screenWakeLock.setReferenceCounted(false);
        screenWakeLock.acquire(5000L);
        screenWakeLock.release();
        return "Screen wake requested.";
    }

    private String requestDismissKeyguard() {
        Intent intent = new Intent(this, MainActivity.class)
                .setAction(MainActivity.ACTION_DISMISS_KEYGUARD)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(intent);
        return "Unlock requested through Android keyguard. Secure PIN/password/fingerprint must be confirmed on the phone.";
    }

    private String setBlackoutMode(boolean enabled) {
        AgentConfig.prefs(this).edit().putBoolean(AgentConfig.KEY_BLACKOUT_ENABLED, enabled).apply();
        Intent intent = new Intent(this, BlackoutActivity.class)
                .setAction(enabled ? BlackoutActivity.ACTION_ON : BlackoutActivity.ACTION_OFF)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        startActivity(intent);
        return enabled
                ? "Blackout mode enabled. The phone shows a black protected screen."
                : "Blackout mode disabled.";
    }

    private String openUrl(String url) {
        if (url == null || url.trim().isEmpty()) {
            return "Open URL failed. URL is empty.";
        }
        String trimmed = url.trim();
        if (!trimmed.startsWith("https://") && !trimmed.startsWith("http://")) {
            return "Open URL rejected. Only http and https links are supported.";
        }
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(trimmed)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            return "URL opened.";
        } catch (Exception exc) {
            return "Open URL failed: " + exc.getMessage();
        }
    }

    private String openAppDetails(String packageName) {
        String targetPackage = packageName == null || packageName.trim().isEmpty()
                ? getPackageName()
                : packageName.trim();
        try {
            Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                    .setData(Uri.parse("package:" + targetPackage))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            return "App details opened.";
        } catch (Exception exc) {
            return "App details failed: " + exc.getMessage();
        }
    }

    private void stopAgent() {
        AgentConfig.prefs(this).edit().putBoolean(AgentConfig.KEY_ENABLED, false).apply();
        if (executor != null) {
            executor.shutdownNow();
        }
        releaseWakeLock();
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    private void acquireWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) {
            return;
        }
        PowerManager powerManager = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (powerManager == null) {
            return;
        }
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "apkconverter:heartbeat");
        wakeLock.setReferenceCounted(false);
        wakeLock.acquire(12 * 60 * 60 * 1000L);
    }

    private void releaseWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
        wakeLock = null;
    }

    private void updateNotification(String status) {
        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.notify(NOTIFICATION_ID, buildNotification(status));
        }
    }

    private Notification buildNotification(String status) {
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);

        return builder
                .setContentTitle(getString(com.apkconverter.agent.R.string.notification_title))
                .setContentText(status)
                .setSmallIcon(android.R.drawable.stat_notify_sync)
                .setOngoing(true)
                .build();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }

        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                getString(com.apkconverter.agent.R.string.notification_channel),
                NotificationManager.IMPORTANCE_LOW
        );
        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.createNotificationChannel(channel);
        }
    }
}
