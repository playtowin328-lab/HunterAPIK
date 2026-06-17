package com.apkconverter.agent;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            return;
        }

        boolean enabled = AgentConfig.prefs(context).getBoolean(AgentConfig.KEY_ENABLED, false);
        if (!enabled) {
            return;
        }

        Intent serviceIntent = new Intent(context, HeartbeatService.class).setAction(HeartbeatService.ACTION_START);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(serviceIntent);
        } else {
            context.startService(serviceIntent);
        }
    }
}
