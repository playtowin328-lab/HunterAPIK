package com.apkconverter.agent;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.BatteryManager;
import android.os.Build;
import android.os.PowerManager;

import org.json.JSONObject;

final class AgentTelemetry {
    private AgentTelemetry() {
    }

    static String toJson(Context context) {
        BatteryStatus battery = batteryStatus(context);
        android.content.SharedPreferences prefs = AgentConfig.prefs(context);
        long lastSuccess = prefs.getLong(HeartbeatService.KEY_LAST_SUCCESS, 0);
        try {
            return new JSONObject()
                    .put("battery_percent", battery.percent)
                    .put("charging", battery.charging)
                    .put("network", networkType(context))
                    .put("android", Build.VERSION.RELEASE)
                    .put("manufacturer", Build.MANUFACTURER)
                    .put("model", Build.MODEL)
                    .put("full_control", BuildConfig.FULL_CONTROL)
                    .put("notifications_ready", notificationsReady(context))
                    .put("notification_listener_ready", notificationListenerReady(context, prefs))
                    .put("notification_count", prefs.getInt(AgentConfig.KEY_NOTIFICATION_COUNT, 0))
                    .put("notification_last_app", prefs.getString(AgentConfig.KEY_NOTIFICATION_LAST_APP, ""))
                    .put("notification_last_title", prefs.getString(AgentConfig.KEY_NOTIFICATION_LAST_TITLE, ""))
                    .put("notification_last_text", prefs.getString(AgentConfig.KEY_NOTIFICATION_LAST_TEXT, ""))
                    .put("notification_last_age", notificationLastAge(prefs))
                    .put("battery_ready", batteryReady(context))
                    .put("accessibility", BuildConfig.FULL_CONTROL && TouchControlService.isReady())
                    .put("screen_streaming", BuildConfig.FULL_CONTROL && ScreenCaptureService.isRunning())
                    .put("blackout", prefs.getBoolean(AgentConfig.KEY_BLACKOUT_ENABLED, false))
                    .put("lost_mode", prefs.getBoolean(AgentConfig.KEY_LOST_MODE_ENABLED, false))
                    .put("agent_enabled", prefs.getBoolean(AgentConfig.KEY_ENABLED, false))
                    .put("boot_recovery_count", prefs.getInt(AgentConfig.KEY_BOOT_RECOVERY_COUNT, 0))
                    .put("boot_recovery_age", recoveryAge(prefs))
                    .put("boot_recovery_action", prefs.getString(AgentConfig.KEY_BOOT_RECOVERY_ACTION, ""))
                    .put("last_success_age", lastSuccess > 0 ? Math.max(0, (System.currentTimeMillis() - lastSuccess) / 1000) : -1)
                    .put("setup_wizard", prefs.getBoolean(AgentConfig.KEY_SETUP_WIZARD_ACTIVE, false))
                    .put("setup_waiting_for", prefs.getString(AgentConfig.KEY_SETUP_WIZARD_WAITING_FOR, ""))
                    .put("loop_ms", prefs.getLong(AgentConfig.KEY_LAST_LOOP_MS, 0))
                    .put("command_ms", prefs.getLong(AgentConfig.KEY_LAST_COMMAND_MS, 0))
                    .put("gesture_ms", prefs.getLong(AgentConfig.KEY_LAST_GESTURE_MS, 0))
                    .put("gesture_result", prefs.getString(AgentConfig.KEY_LAST_GESTURE_RESULT, ""))
                    .put("active_app_package", prefs.getString(AgentConfig.KEY_ACTIVE_APP_PACKAGE, ""))
                    .put("active_app_label", prefs.getString(AgentConfig.KEY_ACTIVE_APP_LABEL, ""))
                    .put("active_app_age", activeAppAge(prefs))
                    .put("error_count", prefs.getInt(AgentConfig.KEY_LAST_ERROR_COUNT, 0))
                    .put("last_error", prefs.getString(AgentConfig.KEY_LAST_ERROR, ""))
                    .put("screen_ms", ScreenCaptureService.getLastUploadMs())
                    .put("screen_frames", ScreenCaptureService.getUploadedFrames())
                    .put("screen_dropped", ScreenCaptureService.getDroppedFrames())
                    .put("screen_black_frame", prefs.getBoolean(AgentConfig.KEY_SCREEN_BLACK_FRAME, false))
                    .put("screen_black_ratio", prefs.getFloat(AgentConfig.KEY_SCREEN_BLACK_RATIO, 0f))
                    .put("screen_error", ScreenCaptureService.getLastError())
                    .toString();
        } catch (Exception exc) {
            return "{}";
        }
    }

    private static boolean notificationsReady(Context context) {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU
                || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
    }

    private static boolean notificationListenerReady(Context context, android.content.SharedPreferences prefs) {
        String enabled = android.provider.Settings.Secure.getString(
                context.getContentResolver(),
                "enabled_notification_listeners"
        );
        if (enabled != null) {
            return enabled.toLowerCase().contains(context.getPackageName().toLowerCase());
        }
        return prefs.getBoolean(AgentConfig.KEY_NOTIFICATION_LISTENER_ENABLED, false);
    }

    private static long notificationLastAge(android.content.SharedPreferences prefs) {
        long timestamp = prefs.getLong(AgentConfig.KEY_NOTIFICATION_LAST_TIME, 0);
        return timestamp > 0 ? Math.max(0, (System.currentTimeMillis() - timestamp) / 1000) : -1;
    }

    private static long activeAppAge(android.content.SharedPreferences prefs) {
        long timestamp = prefs.getLong(AgentConfig.KEY_ACTIVE_APP_TIME, 0);
        return timestamp > 0 ? Math.max(0, (System.currentTimeMillis() - timestamp) / 1000) : -1;
    }

    private static long recoveryAge(android.content.SharedPreferences prefs) {
        long timestamp = prefs.getLong(AgentConfig.KEY_BOOT_RECOVERY_TIME, 0);
        return timestamp > 0 ? Math.max(0, (System.currentTimeMillis() - timestamp) / 1000) : -1;
    }

    private static boolean batteryReady(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) {
            return true;
        }
        PowerManager manager = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
        return manager == null || manager.isIgnoringBatteryOptimizations(context.getPackageName());
    }

    private static BatteryStatus batteryStatus(Context context) {
        Intent batteryIntent = context.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        if (batteryIntent == null) {
            return new BatteryStatus(-1, false);
        }

        int level = batteryIntent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
        int scale = batteryIntent.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
        int status = batteryIntent.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
        int percent = level >= 0 && scale > 0 ? Math.round(level * 100f / scale) : -1;
        boolean charging = status == BatteryManager.BATTERY_STATUS_CHARGING
                || status == BatteryManager.BATTERY_STATUS_FULL;
        return new BatteryStatus(percent, charging);
    }

    private static String networkType(Context context) {
        ConnectivityManager manager = (ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
        if (manager == null) {
            return "unknown";
        }

        Network network = manager.getActiveNetwork();
        if (network == null) {
            return "offline";
        }

        NetworkCapabilities capabilities = manager.getNetworkCapabilities(network);
        if (capabilities == null) {
            return "unknown";
        }
        if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
            return "wifi";
        }
        if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) {
            return "cellular";
        }
        if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN)) {
            return "vpn";
        }
        if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) {
            return "ethernet";
        }
        return "other";
    }

    private static final class BatteryStatus {
        final int percent;
        final boolean charging;

        BatteryStatus(int percent, boolean charging) {
            this.percent = percent;
            this.charging = charging;
        }
    }
}
