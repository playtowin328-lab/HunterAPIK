package com.apkconverter.agent;

import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.BatteryManager;
import android.os.Build;

final class AgentTelemetry {
    private AgentTelemetry() {
    }

    static String toJson(Context context) {
        BatteryStatus battery = batteryStatus(context);
        android.content.SharedPreferences prefs = AgentConfig.prefs(context);
        return "{"
                + "\"battery_percent\":" + battery.percent + ","
                + "\"charging\":" + battery.charging + ","
                + "\"network\":\"" + escape(networkType(context)) + "\","
                + "\"android\":\"" + escape(Build.VERSION.RELEASE) + "\","
                + "\"manufacturer\":\"" + escape(Build.MANUFACTURER) + "\","
                + "\"model\":\"" + escape(Build.MODEL) + "\","
                + "\"full_control\":" + BuildConfig.FULL_CONTROL + ","
                + "\"accessibility\":" + (BuildConfig.FULL_CONTROL && TouchControlService.isReady()) + ","
                + "\"screen_streaming\":" + (BuildConfig.FULL_CONTROL && ScreenCaptureService.isRunning()) + ","
                + "\"loop_ms\":" + prefs.getLong(AgentConfig.KEY_LAST_LOOP_MS, 0) + ","
                + "\"command_ms\":" + prefs.getLong(AgentConfig.KEY_LAST_COMMAND_MS, 0) + ","
                + "\"gesture_ms\":" + prefs.getLong(AgentConfig.KEY_LAST_GESTURE_MS, 0) + ","
                + "\"gesture_result\":\"" + escape(prefs.getString(AgentConfig.KEY_LAST_GESTURE_RESULT, "")) + "\","
                + "\"error_count\":" + prefs.getInt(AgentConfig.KEY_LAST_ERROR_COUNT, 0) + ","
                + "\"last_error\":\"" + escape(prefs.getString(AgentConfig.KEY_LAST_ERROR, "")) + "\","
                + "\"screen_ms\":" + ScreenCaptureService.getLastUploadMs() + ","
                + "\"screen_frames\":" + ScreenCaptureService.getUploadedFrames() + ","
                + "\"screen_dropped\":" + ScreenCaptureService.getDroppedFrames() + ","
                + "\"screen_error\":\"" + escape(ScreenCaptureService.getLastError()) + "\""
                + "}";
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

    private static String escape(String value) {
        if (value == null) {
            return "";
        }
        return value
                .replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r");
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
