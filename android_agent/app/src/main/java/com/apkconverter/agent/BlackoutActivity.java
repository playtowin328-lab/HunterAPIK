package com.apkconverter.agent;

import android.app.Activity;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.TextView;

public class BlackoutActivity extends Activity {
    static final String ACTION_ON = "com.apkconverter.agent.BLACKOUT_ON";
    static final String ACTION_OFF = "com.apkconverter.agent.BLACKOUT_OFF";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (ACTION_OFF.equals(getIntent().getAction())) {
            setBlackoutEnabled(false);
            finish();
            return;
        }
        setBlackoutEnabled(true);
        configureWindow();
        setContentView(buildView());
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (!AgentConfig.prefs(this).getBoolean(AgentConfig.KEY_BLACKOUT_ENABLED, false)) {
            finish();
            return;
        }
        hideSystemUi();
    }

    @Override
    public void onBackPressed() {
        // Lost mode is controlled remotely from the mini app.
    }

    private void setBlackoutEnabled(boolean enabled) {
        AgentConfig.prefs(this).edit().putBoolean(AgentConfig.KEY_BLACKOUT_ENABLED, enabled).apply();
    }

    private void configureWindow() {
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().addFlags(
                WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
                        | WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
                        | WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
        );
        hideSystemUi();
    }

    private View buildView() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);

        TextView status = new TextView(this);
        status.setText("Protected mode");
        status.setTextColor(Color.rgb(18, 18, 18));
        status.setTextSize(12);
        status.setGravity(Gravity.CENTER);

        root.addView(status, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
        ));
        return root;
    }

    private void hideSystemUi() {
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        );
    }
}
