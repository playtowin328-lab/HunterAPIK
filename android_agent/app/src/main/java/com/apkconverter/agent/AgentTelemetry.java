package com.apkconverter.agent;

import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.BatteryManager;
import android.os.Build;

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
                    .put("accessibility", BuildConfig.FULL_CONTROL && TouchControlService.isReady())
                    .put("screen_streaming", BuildConfig.FULL_CONTROL && ScreenCaptureService.isRunning())
                    .put("blackout", prefs.getBoolean(AgentConfig.KEY_BLACKOUT_ENABLED, false))
                    .put("lost_mode", prefs.getBoolean(AgentConfig.KEY_LOST_MODE_ENABLED, false))
                    .put("agent_enabled", prefs.getBoolean(AgentConfig.KEY_ENABLED, false))
                    .put("last_success_age", lastSuccess > 0 ? Math.max(0, (System.currentTimeMillis() - lastSuccess) / 1000) : -1)
                    .put("setup_wizard", prefs.getBoolean(AgentConfig.KEY_SETUP_WIZARD_ACTIVE, false))
                    .put("setup_waiting_for", prefs.getString(AgentConfig.KEY_SETUP_WIZARD_WAITING_FOR, ""))
                    .put("loop_ms", prefs.getLong(AgentConfig.KEY_LAST_LOOP_MS, 0))
                    .put("command_ms", prefs.getLong(AgentConfig.KEY_LAST_COMMAND_MS, 0))
                    .put("gesture_ms", prefs.getLong(AgentConfig.KEY_LAST_GESTURE_MS, 0))
                    .put("gesture_result", prefs.getString(AgentConfig.KEY_LAST_GESTURE_RESULT, ""))
                    .put("error_count", prefs.getInt(AgentConfig.KEY_LAST_ERROR_COUNT, 0))
                    .put("last_error", prefs.getString(AgentConfig.KEY_LAST_ERROR, ""))
                    .put("screen_ms", ScreenCaptureService.getLastUploadMs())
                    .put("screen_frames", ScreenCaptureService.getUploadedFrames())
                    .put("screen_dropped", ScreenCaptureService.getDroppedFrames())
                    .put("screen_error", ScreenCaptureService.getLastError())
                    .toString();
        } catch (Exception exc) {
            return "{}";
        }
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
