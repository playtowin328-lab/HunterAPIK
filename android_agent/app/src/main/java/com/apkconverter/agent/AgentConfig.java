package com.apkconverter.agent;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;
import android.provider.Settings;

import java.util.UUID;

final class AgentConfig {
    static final String PREFS_NAME = "apk_agent";
    static final String KEY_SERVER_URL = "server_url";
    static final String KEY_OWNER_ID = "owner_id";
    static final String KEY_API_TOKEN = "api_token";
    static final String KEY_DEVICE_SECRET = "device_secret";
    static final String KEY_DEVICE_NAME = "device_name";
    static final String KEY_DEVICE_ID = "device_id";
    static final String KEY_ENABLED = "enabled";
    static final String KEY_LAST_LOOP_MS = "last_loop_ms";
    static final String KEY_LAST_COMMAND_MS = "last_command_ms";
    static final String KEY_LAST_ERROR_COUNT = "last_error_count";
    static final String KEY_LAST_ERROR = "last_error";
    static final String KEY_LAST_GESTURE_MS = "last_gesture_ms";
    static final String KEY_LAST_GESTURE_RESULT = "last_gesture_result";
    static final String KEY_BLACKOUT_ENABLED = "blackout_enabled";
    static final String KEY_LOST_MODE_ENABLED = "lost_mode_enabled";

    private AgentConfig() {
    }

    static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    static String getDeviceId(Context context) {
        SharedPreferences prefs = prefs(context);
        String existing = prefs.getString(KEY_DEVICE_ID, "");
        if (!existing.isEmpty()) {
            return existing;
        }

        String androidId = Settings.Secure.getString(context.getContentResolver(), Settings.Secure.ANDROID_ID);
        String deviceId = androidId == null || androidId.isEmpty() ? UUID.randomUUID().toString() : androidId;
        prefs.edit().putString(KEY_DEVICE_ID, deviceId).apply();
        return deviceId;
    }

    static String defaultDeviceName() {
        String manufacturer = Build.MANUFACTURER == null ? "" : Build.MANUFACTURER.trim();
        String model = Build.MODEL == null ? "Android device" : Build.MODEL.trim();
        if (model.toLowerCase().startsWith(manufacturer.toLowerCase())) {
            return model;
        }
        return (manufacturer + " " + model).trim();
    }

    static String platformLabel() {
        return "Android " + Build.VERSION.RELEASE;
    }
}
