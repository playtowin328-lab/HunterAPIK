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
    private static final int HEARTBEAT_SECONDS = 5;
    private static final int MAX_COMMANDS_PER_TICK = 6;

    private ScheduledExecutorService executor;

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
        startForeground(NOTIFICATION_ID, buildNotification("Запускаю подключение"));
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
        super.onDestroy();
    }

    private void startHeartbeatLoop() {
        if (executor != null && !executor.isShutdown()) {
            return;
        }

        executor = Executors.newSingleThreadScheduledExecutor();
        executor.scheduleWithFixedDelay(this::sendHeartbeat, 0, HEARTBEAT_SECONDS, TimeUnit.SECONDS);
    }

    private void sendHeartbeat() {
        SharedPreferences.Editor editor = AgentConfig.prefs(this).edit();
        String timestamp = DateFormat.getTimeInstance(DateFormat.SHORT).format(new Date());

        try {
            DeviceApiClient.heartbeat(this);
            String commandStatus = handlePendingCommands();
            editor.putString(KEY_LAST_STATUS, "Online · " + timestamp + commandStatus);
            editor.putLong(KEY_LAST_SUCCESS, System.currentTimeMillis());
            updateNotification("Online · " + timestamp);
        } catch (Exception exc) {
            editor.putString(KEY_LAST_STATUS, "Ошибка: " + exc.getMessage());
            updateNotification("Ошибка подключения");
        }

        editor.apply();
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
        String result;
        if ("request_screen".equals(command.type)) {
            if (!BuildConfig.FULL_CONTROL) {
                result = "Screen preview is disabled in Lite build.";
                DeviceApiClient.completeCommand(this, command, "rejected", result);
                return "\nКоманда: " + command.type + "\n" + result;
            }
            Intent intent = new Intent(this, MainActivity.class)
                    .setAction(MainActivity.ACTION_REQUEST_SCREEN_CAPTURE)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            result = "Screen permission requested on device.";
        } else if ("stop_screen".equals(command.type)) {
            if (!BuildConfig.FULL_CONTROL) {
                result = "Screen preview is disabled in Lite build.";
                DeviceApiClient.completeCommand(this, command, "rejected", result);
                return "\nКоманда: " + command.type + "\n" + result;
            }
            Intent intent = new Intent(this, ScreenCaptureService.class).setAction(ScreenCaptureService.ACTION_STOP);
            startService(intent);
            result = "Screen capture stop requested.";
        } else if ("request_files".equals(command.type)) {
            result = "Files request received. Storage picker module is not enabled yet.";
        } else if ("request_actions".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.isReady()
                    ? "Actions module is ready for taps and navigation."
                    : "Actions are disabled in Lite build.";
        } else if ("tap".equals(command.type)) {
            if (!BuildConfig.FULL_CONTROL) {
                result = "Tap rejected. Lite build has no Accessibility control.";
            } else if (!TouchControlService.isReady()) {
                result = "Tap rejected. Enable APK Agent Accessibility Service in Android settings.";
            } else if (command.x < 0 || command.y < 0) {
                result = "Tap rejected. Coordinates are missing.";
            } else {
                boolean dispatched = TouchControlService.tapNormalized(command.x, command.y);
                result = dispatched ? "Tap dispatched." : "Tap dispatch failed.";
            }
        } else if ("back".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.back() ? "Back dispatched." : "Back failed or disabled in Lite build.";
        } else if ("home".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.home() ? "Home dispatched." : "Home failed or disabled in Lite build.";
        } else if ("recents".equals(command.type)) {
            result = BuildConfig.FULL_CONTROL && TouchControlService.recents() ? "Recents dispatched." : "Recents failed or disabled in Lite build.";
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
            if (!BuildConfig.FULL_CONTROL) {
                result = "Text input failed. Lite build has no Accessibility control.";
            } else if (!TouchControlService.isReady()) {
                result = "Text input failed. Enable Accessibility Service.";
            } else if (command.text == null || command.text.isEmpty()) {
                result = "Text input failed. Text is empty.";
            } else {
                result = TouchControlService.inputText(command.text)
                        ? "Text inserted."
                        : "Text input failed. Focus an editable field on the phone.";
            }
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
        }

        DeviceApiClient.completeCommand(this, command, "acknowledged", result);
        return "\nКоманда: " + command.type + "\n" + result;
    }

    private void stopAgent() {
        AgentConfig.prefs(this).edit().putBoolean(AgentConfig.KEY_ENABLED, false).apply();
        if (executor != null) {
            executor.shutdownNow();
        }
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    private void updateNotification(String status) {
        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        manager.notify(NOTIFICATION_ID, buildNotification(status));
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
        manager.createNotificationChannel(channel);
    }
}
