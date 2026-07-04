package com.apkconverter.agent;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !shouldStart(intent.getAction())) {
            return;
        }

        android.content.SharedPreferences prefs = AgentConfig.prefs(context);
        prefs.edit()
                .putInt(AgentConfig.KEY_BOOT_RECOVERY_COUNT, prefs.getInt(AgentConfig.KEY_BOOT_RECOVERY_COUNT, 0) + 1)
                .putLong(AgentConfig.KEY_BOOT_RECOVERY_TIME, System.currentTimeMillis())
                .putString(AgentConfig.KEY_BOOT_RECOVERY_ACTION, intent.getAction() == null ? "unknown" : intent.getAction())
                .apply();
        AgentStarter.restartIfEnabled(context);
    }

    private boolean shouldStart(String action) {
        return Intent.ACTION_BOOT_COMPLETED.equals(action)
                || Intent.ACTION_LOCKED_BOOT_COMPLETED.equals(action)
                || Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)
                || AgentStarter.ACTION_RESTART.equals(action)
                || "android.intent.action.QUICKBOOT_POWERON".equals(action)
                || "com.htc.intent.action.QUICKBOOT_POWERON".equals(action);
    }
}
