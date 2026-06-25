package com.apkconverter.agent;

import android.app.Notification;
import android.content.SharedPreferences;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;

public final class NotificationMonitorService extends NotificationListenerService {
    private static final int MAX_TEXT = 160;

    @Override
    public void onListenerConnected() {
        AgentConfig.prefs(this)
                .edit()
                .putBoolean(AgentConfig.KEY_NOTIFICATION_LISTENER_ENABLED, true)
                .apply();
    }

    @Override
    public void onListenerDisconnected() {
        AgentConfig.prefs(this)
                .edit()
                .putBoolean(AgentConfig.KEY_NOTIFICATION_LISTENER_ENABLED, false)
                .apply();
    }

    @Override
    public void onNotificationPosted(StatusBarNotification notification) {
        if (notification == null || notification.getNotification() == null) {
            return;
        }

        Notification androidNotification = notification.getNotification();
        CharSequence title = androidNotification.extras.getCharSequence(Notification.EXTRA_TITLE);
        CharSequence text = androidNotification.extras.getCharSequence(Notification.EXTRA_TEXT);
        SharedPreferences prefs = AgentConfig.prefs(this);
        int count = prefs.getInt(AgentConfig.KEY_NOTIFICATION_COUNT, 0) + 1;
        prefs.edit()
                .putBoolean(AgentConfig.KEY_NOTIFICATION_LISTENER_ENABLED, true)
                .putString(AgentConfig.KEY_NOTIFICATION_LAST_APP, limit(notification.getPackageName()))
                .putString(AgentConfig.KEY_NOTIFICATION_LAST_TITLE, redact(title))
                .putString(AgentConfig.KEY_NOTIFICATION_LAST_TEXT, redact(text))
                .putLong(AgentConfig.KEY_NOTIFICATION_LAST_TIME, System.currentTimeMillis())
                .putInt(AgentConfig.KEY_NOTIFICATION_COUNT, count)
                .apply();
    }

    @Override
    public void onNotificationRemoved(StatusBarNotification notification) {
        AgentConfig.prefs(this)
                .edit()
                .putBoolean(AgentConfig.KEY_NOTIFICATION_LISTENER_ENABLED, true)
                .apply();
    }

    private static String redact(CharSequence value) {
        String text = value == null ? "" : value.toString();
        text = text.replaceAll("\\b\\d{4,8}\\b", "••••");
        return limit(text);
    }

    private static String limit(String value) {
        if (value == null) {
            return "";
        }
        String clean = value.replace('\n', ' ').replace('\r', ' ').trim();
        return clean.length() <= MAX_TEXT ? clean : clean.substring(0, MAX_TEXT) + "...";
    }
}
