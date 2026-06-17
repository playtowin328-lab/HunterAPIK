package com.apkconverter.agent;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.graphics.Path;
import android.os.Bundle;
import android.util.DisplayMetrics;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

public class TouchControlService extends AccessibilityService {
    private static TouchControlService instance;

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
    }

    @Override
    public void onInterrupt() {
    }

    @Override
    public boolean onUnbind(android.content.Intent intent) {
        instance = null;
        return super.onUnbind(intent);
    }

    static boolean isReady() {
        return instance != null;
    }

    static boolean tapNormalized(float normalizedX, float normalizedY) {
        if (instance == null) {
            return false;
        }

        DisplayMetrics metrics = new DisplayMetrics();
        WindowManager windowManager = (WindowManager) instance.getSystemService(WINDOW_SERVICE);
        windowManager.getDefaultDisplay().getRealMetrics(metrics);

        float x = clamp(normalizedX) * metrics.widthPixels;
        float y = clamp(normalizedY) * metrics.heightPixels;

        Path path = new Path();
        path.moveTo(x, y);

        GestureDescription gesture = new GestureDescription.Builder()
                .addStroke(new GestureDescription.StrokeDescription(path, 0, 80))
                .build();
        return instance.dispatchGesture(gesture, null, null);
    }

    static boolean swipeNormalized(float startX, float startY, float endX, float endY) {
        if (instance == null) {
            return false;
        }

        DisplayMetrics metrics = new DisplayMetrics();
        WindowManager windowManager = (WindowManager) instance.getSystemService(WINDOW_SERVICE);
        windowManager.getDefaultDisplay().getRealMetrics(metrics);

        Path path = new Path();
        path.moveTo(clamp(startX) * metrics.widthPixels, clamp(startY) * metrics.heightPixels);
        path.lineTo(clamp(endX) * metrics.widthPixels, clamp(endY) * metrics.heightPixels);

        GestureDescription gesture = new GestureDescription.Builder()
                .addStroke(new GestureDescription.StrokeDescription(path, 0, 420))
                .build();
        return instance.dispatchGesture(gesture, null, null);
    }

    static boolean back() {
        return performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK);
    }

    static boolean home() {
        return performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME);
    }

    static boolean recents() {
        return performGlobalAction(AccessibilityService.GLOBAL_ACTION_RECENTS);
    }

    static boolean inputText(String text) {
        if (instance == null || text == null) {
            return false;
        }

        AccessibilityNodeInfo node = instance.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
        if (node == null) {
            return false;
        }

        CharSequence currentText = node.getText();
        String value = currentText == null ? "" : currentText.toString();

        Bundle args = new Bundle();
        args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, value + text);
        boolean result = node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args);
        node.recycle();
        return result;
    }

    static boolean enter() {
        return inputText("\n");
    }

    static boolean delete() {
        if (instance == null) {
            return false;
        }

        AccessibilityNodeInfo node = instance.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
        if (node == null) {
            return false;
        }

        CharSequence currentText = node.getText();
        String value = currentText == null ? "" : currentText.toString();
        if (value.isEmpty()) {
            node.recycle();
            return true;
        }

        Bundle args = new Bundle();
        args.putCharSequence(
                AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,
                value.substring(0, value.length() - 1)
        );
        boolean result = node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args);
        node.recycle();
        return result;
    }

    private static boolean performGlobalAction(int action) {
        if (instance == null) {
            return false;
        }
        return instance.performGlobalAction(action);
    }

    private static float clamp(float value) {
        return Math.max(0f, Math.min(1f, value));
    }
}
