package com.apkconverter.agent;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

final class AgentStarter {
    static final String ACTION_RESTART = "com.apkconverter.agent.RESTART";

    private static final int RESTART_REQUEST_CODE = 7101;
    private static final long RESTART_DELAY_MS = 5_000L;

    private AgentStarter() {
    }

    static void start(Context context) {
        Intent intent = new Intent(context, HeartbeatService.class).setAction(HeartbeatService.ACTION_START);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    static void stop(Context context) {
        Intent intent = new Intent(context, HeartbeatService.class).setAction(HeartbeatService.ACTION_STOP);
        context.startService(intent);
    }

    static void restartIfEnabled(Context context) {
        if (AgentConfig.prefs(context).getBoolean(AgentConfig.KEY_ENABLED, false)) {
            start(context);
        }
    }

    static void scheduleRestart(Context context) {
        if (!AgentConfig.prefs(context).getBoolean(AgentConfig.KEY_ENABLED, false)) {
            return;
        }

        Intent intent = new Intent(context, BootReceiver.class).setAction(ACTION_RESTART);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }
        PendingIntent pendingIntent = PendingIntent.getBroadcast(context, RESTART_REQUEST_CODE, intent, flags);
        AlarmManager alarmManager = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        if (alarmManager == null) {
            return;
        }

        long triggerAt = System.currentTimeMillis() + RESTART_DELAY_MS;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pendingIntent);
        } else {
            alarmManager.set(AlarmManager.RTC_WAKEUP, triggerAt, pendingIntent);
        }
    }
}
