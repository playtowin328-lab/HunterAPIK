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
    static final String KEY_COMMAND_REPLAYS_PREVENTED = "command_replays_prevented";
    static final String KEY_LAST_ERROR_COUNT = "last_error_count";
    static final String KEY_LAST_ERROR = "last_error";
    static final String KEY_LAST_GESTURE_MS = "last_gesture_ms";
    static final String KEY_LAST_GESTURE_RESULT = "last_gesture_result";
    static final String KEY_BLACKOUT_ENABLED = "blackout_enabled";
    static final String KEY_BLACKOUT_MESSAGE = "blackout_message";
    static final String KEY_LOST_MODE_ENABLED = "lost_mode_enabled";
    static final String KEY_SCREEN_MAX_SIZE = "screen_max_size";
    static final String KEY_SCREEN_BLACK_FRAME = "screen_black_frame";
    static final String KEY_SCREEN_BLACK_RATIO = "screen_black_ratio";
    static final String KEY_SCREEN_SESSION_STATE = "screen_session_state";
    static final String KEY_SCREEN_SESSION_ID = "screen_session_id";
    static final String KEY_SCREEN_SESSION_STARTED_AT = "screen_session_started_at";
    static final String KEY_SCREEN_LAST_FRAME_AT = "screen_last_frame_at";
    static final String KEY_SCREEN_STOPPED_AT = "screen_stopped_at";
    static final String KEY_SCREEN_STOP_REASON = "screen_stop_reason";
    static final String KEY_SCREEN_PERMISSION_REQUIRED = "screen_permission_required";
    static final String KEY_SCREEN_PERMISSION_PENDING = "screen_permission_pending";
    static final String KEY_SCREEN_PERMISSION_REQUESTED_AT = "screen_permission_requested_at";
    static final String KEY_ACCESSIBILITY_CONNECTED_AT = "accessibility_connected_at";
    static final String KEY_ACCESSIBILITY_DISCONNECTED_AT = "accessibility_disconnected_at";
    static final String KEY_ACCESSIBILITY_SESSION_ID = "accessibility_session_id";
    static final String KEY_GESTURE_COMPLETED_COUNT = "gesture_completed_count";
    static final String KEY_GESTURE_CANCELLED_COUNT = "gesture_cancelled_count";
    static final String KEY_GESTURE_REJECTED_COUNT = "gesture_rejected_count";
    static final String KEY_GESTURE_TIMEOUT_COUNT = "gesture_timeout_count";
    static final String KEY_SETUP_WIZARD_ACTIVE = "setup_wizard_active";
    static final String KEY_SETUP_WIZARD_WAITING_FOR = "setup_wizard_waiting_for";
    static final String KEY_NOTIFICATION_LISTENER_ENABLED = "notification_listener_enabled";
    static final String KEY_NOTIFICATION_LAST_APP = "notification_last_app";
    static final String KEY_NOTIFICATION_LAST_TITLE = "notification_last_title";
    static final String KEY_NOTIFICATION_LAST_TEXT = "notification_last_text";
    static final String KEY_NOTIFICATION_LAST_TIME = "notification_last_time";
    static final String KEY_NOTIFICATION_COUNT = "notification_count";
    static final String KEY_ACTIVE_APP_PACKAGE = "active_app_package";
    static final String KEY_ACTIVE_APP_LABEL = "active_app_label";
    static final String KEY_ACTIVE_APP_TIME = "active_app_time";
    static final String KEY_BOOT_RECOVERY_COUNT = "boot_recovery_count";
    static final String KEY_BOOT_RECOVERY_TIME = "boot_recovery_time";
    static final String KEY_BOOT_RECOVERY_ACTION = "boot_recovery_action";

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
