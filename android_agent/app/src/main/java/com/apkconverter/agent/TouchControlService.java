package com.apkconverter.agent;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityService.GestureResultCallback;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.accessibilityservice.GestureDescription;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.graphics.Path;
import android.os.Bundle;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.SystemClock;
import android.util.DisplayMetrics;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityManager;
import android.view.accessibility.AccessibilityNodeInfo;

import java.util.List;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

public class TouchControlService extends AccessibilityService {
    private static final Object GESTURE_LOCK = new Object();
    private static final long GESTURE_RESULT_TIMEOUT_MS = 3_000L;
    private static volatile TouchControlService instance;
    private static volatile long lastGestureMs;
    private static volatile String lastGestureResult = "";
    private static volatile long connectedAt;
    private static volatile String connectionSessionId = "";
    private static volatile boolean gestureInFlight;
    private HandlerThread gestureCallbackThread;
    private Handler gestureCallbackHandler;

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        stopGestureCallbackThread();
        gestureCallbackThread = new HandlerThread("gesture-callback");
        gestureCallbackThread.start();
        gestureCallbackHandler = new Handler(gestureCallbackThread.getLooper());
        connectedAt = System.currentTimeMillis();
        connectionSessionId = UUID.randomUUID().toString();
        instance = this;
        AgentConfig.prefs(this).edit()
                .putLong(AgentConfig.KEY_ACCESSIBILITY_CONNECTED_AT, connectedAt)
                .putString(AgentConfig.KEY_ACCESSIBILITY_SESSION_ID, connectionSessionId)
                .apply();
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event == null || event.getPackageName() == null) {
            return;
        }
        int type = event.getEventType();
        if (type != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED && type != AccessibilityEvent.TYPE_WINDOWS_CHANGED) {
            return;
        }
        String packageName = event.getPackageName().toString();
        AgentConfig.prefs(this)
                .edit()
                .putString(AgentConfig.KEY_ACTIVE_APP_PACKAGE, packageName)
                .putString(AgentConfig.KEY_ACTIVE_APP_LABEL, appLabel(packageName))
                .putLong(AgentConfig.KEY_ACTIVE_APP_TIME, System.currentTimeMillis())
                .apply();
    }

    @Override
    public void onInterrupt() {
    }

    @Override
    public boolean onUnbind(android.content.Intent intent) {
        markDisconnected(this);
        stopGestureCallbackThread();
        return super.onUnbind(intent);
    }

    @Override
    public void onDestroy() {
        markDisconnected(this);
        stopGestureCallbackThread();
        super.onDestroy();
    }

    static boolean isReady() {
        return instance != null;
    }

    static boolean isEnabledInSettings(Context context) {
        AccessibilityManager manager = (AccessibilityManager) context.getSystemService(Context.ACCESSIBILITY_SERVICE);
        if (manager == null || !manager.isEnabled()) {
            return false;
        }
        List<AccessibilityServiceInfo> enabledServices = manager.getEnabledAccessibilityServiceList(
                AccessibilityServiceInfo.FEEDBACK_ALL_MASK
        );
        String packageName = context.getPackageName();
        String serviceName = TouchControlService.class.getName();
        for (AccessibilityServiceInfo info : enabledServices) {
            if (info == null || info.getResolveInfo() == null || info.getResolveInfo().serviceInfo == null) {
                continue;
            }
            android.content.pm.ServiceInfo resolved = info.getResolveInfo().serviceInfo;
            if (packageName.equals(resolved.packageName) && serviceName.equals(resolved.name)) {
                return true;
            }
        }
        return false;
    }

    static String getConnectionState(Context context) {
        if (isReady()) {
            return "connected";
        }
        return isEnabledInSettings(context) ? "reconnecting" : "disabled";
    }

    static String getConnectionSessionId(Context context) {
        return isReady()
                ? connectionSessionId
                : AgentConfig.prefs(context).getString(AgentConfig.KEY_ACCESSIBILITY_SESSION_ID, "");
    }

    static long getConnectionAgeSeconds(Context context) {
        long timestamp = isReady()
                ? connectedAt
                : AgentConfig.prefs(context).getLong(AgentConfig.KEY_ACCESSIBILITY_CONNECTED_AT, 0L);
        return timestamp > 0 ? Math.max(0L, (System.currentTimeMillis() - timestamp) / 1000L) : -1L;
    }

    static boolean isGestureInFlight() {
        return gestureInFlight;
    }

    static boolean tapNormalized(float normalizedX, float normalizedY) {
        if (instance == null) {
            recordGesture("tap", 0, false, "service not ready");
            return false;
        }

        DisplayMetrics metrics = new DisplayMetrics();
        WindowManager windowManager = (WindowManager) instance.getSystemService(WINDOW_SERVICE);
        if (windowManager == null) {
            recordGesture("tap", 0, false, "window service unavailable");
            return false;
        }
        windowManager.getDefaultDisplay().getRealMetrics(metrics);

        float x = clamp(normalizedX) * metrics.widthPixels;
        float y = clamp(normalizedY) * metrics.heightPixels;

        Path path = new Path();
        path.moveTo(x, y);

        GestureDescription gesture = new GestureDescription.Builder()
                .addStroke(new GestureDescription.StrokeDescription(path, 0, 80))
                .build();
        return dispatch("tap", gesture);
    }

    static boolean longTapNormalized(float normalizedX, float normalizedY) {
        if (instance == null) {
            recordGesture("long_tap", 0, false, "service not ready");
            return false;
        }

        DisplayMetrics metrics = new DisplayMetrics();
        WindowManager windowManager = (WindowManager) instance.getSystemService(WINDOW_SERVICE);
        if (windowManager == null) {
            recordGesture("long_tap", 0, false, "window service unavailable");
            return false;
        }
        windowManager.getDefaultDisplay().getRealMetrics(metrics);

        float x = clamp(normalizedX) * metrics.widthPixels;
        float y = clamp(normalizedY) * metrics.heightPixels;

        Path path = new Path();
        path.moveTo(x, y);

        GestureDescription gesture = new GestureDescription.Builder()
                .addStroke(new GestureDescription.StrokeDescription(path, 0, 520))
                .build();
        return dispatch("long_tap", gesture);
    }

    static boolean swipeNormalized(float startX, float startY, float endX, float endY) {
        return swipeNormalized(startX, startY, endX, endY, 220);
    }

    static boolean swipeNormalized(float startX, float startY, float endX, float endY, long durationMs) {
        if (instance == null) {
            recordGesture("swipe", 0, false, "service not ready");
            return false;
        }

        DisplayMetrics metrics = new DisplayMetrics();
        WindowManager windowManager = (WindowManager) instance.getSystemService(WINDOW_SERVICE);
        if (windowManager == null) {
            recordGesture("swipe", 0, false, "window service unavailable");
            return false;
        }
        windowManager.getDefaultDisplay().getRealMetrics(metrics);

        Path path = new Path();
        path.moveTo(clamp(startX) * metrics.widthPixels, clamp(startY) * metrics.heightPixels);
        path.lineTo(clamp(endX) * metrics.widthPixels, clamp(endY) * metrics.heightPixels);

        GestureDescription gesture = new GestureDescription.Builder()
                .addStroke(new GestureDescription.StrokeDescription(path, 0, durationMs))
                .build();
        return dispatch("swipe", gesture);
    }

    static long getLastGestureMs() {
        return lastGestureMs;
    }

    static String getLastGestureResult() {
        return lastGestureResult == null ? "" : lastGestureResult;
    }

    static boolean notifications() {
        return performGlobalActionCompat(AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS);
    }

    static boolean quickSettings() {
        return performGlobalActionCompat(AccessibilityService.GLOBAL_ACTION_QUICK_SETTINGS);
    }

    static boolean lockScreen() {
        return android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P
                && performGlobalActionCompat(AccessibilityService.GLOBAL_ACTION_LOCK_SCREEN);
    }

    static boolean back() {
        return performGlobalActionCompat(AccessibilityService.GLOBAL_ACTION_BACK);
    }

    static boolean home() {
        return performGlobalActionCompat(AccessibilityService.GLOBAL_ACTION_HOME);
    }

    static boolean recents() {
        return performGlobalActionCompat(AccessibilityService.GLOBAL_ACTION_RECENTS);
    }

    static boolean inputText(String text) {
        long started = SystemClock.elapsedRealtime();
        if (instance == null || text == null) {
            recordGesture("input_text", 0, false, "service not ready");
            return false;
        }

        AccessibilityNodeInfo node = findEditableNode();
        if (node == null) {
            recordGesture("input_text", SystemClock.elapsedRealtime() - started, false, "editable focus not found");
            return false;
        }

        boolean result = appendText(node, text) || pasteText(node, text);
        recordGesture("input_text", SystemClock.elapsedRealtime() - started, result, result ? "inserted" : "setText and paste rejected");
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

    private static AccessibilityNodeInfo findEditableNode() {
        if (instance == null) {
            return null;
        }
        AccessibilityNodeInfo focus = instance.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
        if (focus != null && focus.isEditable()) {
            return focus;
        }
        if (focus != null) {
            focus.recycle();
        }
        AccessibilityNodeInfo root = instance.getRootInActiveWindow();
        AccessibilityNodeInfo match = findEditableNode(root, true);
        if (root != null) {
            root.recycle();
        }
        return match;
    }

    private static AccessibilityNodeInfo findEditableNode(AccessibilityNodeInfo node, boolean allowFirstEditable) {
        if (node == null) {
            return null;
        }
        if (node.isEditable() && (node.isFocused() || allowFirstEditable)) {
            return AccessibilityNodeInfo.obtain(node);
        }
        for (int index = 0; index < node.getChildCount(); index++) {
            AccessibilityNodeInfo child = node.getChild(index);
            AccessibilityNodeInfo match = findEditableNode(child, false);
            if (child != null) {
                child.recycle();
            }
            if (match != null) {
                return match;
            }
        }
        if (allowFirstEditable) {
            for (int index = 0; index < node.getChildCount(); index++) {
                AccessibilityNodeInfo child = node.getChild(index);
                AccessibilityNodeInfo match = findEditableNode(child, true);
                if (child != null) {
                    child.recycle();
                }
                if (match != null) {
                    return match;
                }
            }
        }
        return null;
    }

    private static boolean appendText(AccessibilityNodeInfo node, String text) {
        node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        CharSequence currentText = node.getText();
        String value = currentText == null ? "" : currentText.toString();

        Bundle appendArgs = new Bundle();
        appendArgs.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, value + text);
        if (node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, appendArgs)) {
            return true;
        }

        Bundle replaceArgs = new Bundle();
        replaceArgs.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
        return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, replaceArgs);
    }

    private static boolean pasteText(AccessibilityNodeInfo node, String text) {
        ClipboardManager clipboard = (ClipboardManager) instance.getSystemService(Context.CLIPBOARD_SERVICE);
        if (clipboard == null) {
            return false;
        }
        clipboard.setPrimaryClip(ClipData.newPlainText("remote text", text));
        node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        return node.performAction(AccessibilityNodeInfo.ACTION_PASTE);
    }

    private static boolean performGlobalActionCompat(int action) {
        synchronized (GESTURE_LOCK) {
            TouchControlService service = instance;
            if (service == null) {
                recordGesture("global_action", 0, false, "service not ready");
                return false;
            }
            long started = SystemClock.elapsedRealtime();
            boolean result = service.performGlobalAction(action);
            recordGesture("global_action", SystemClock.elapsedRealtime() - started, result, result ? "completed" : "rejected");
            return result;
        }
    }

    private static boolean dispatch(String label, GestureDescription gesture) {
        synchronized (GESTURE_LOCK) {
            TouchControlService service = instance;
            if (service == null) {
                recordGesture(label, 0, false, "service not ready");
                return false;
            }
            gestureInFlight = true;
            try {
                for (int attempt = 0; attempt < 2; attempt++) {
                    long started = SystemClock.elapsedRealtime();
                    CountDownLatch completion = new CountDownLatch(1);
                    AtomicBoolean completed = new AtomicBoolean(false);
                    boolean accepted;
                    try {
                        accepted = service.dispatchGesture(gesture, new GestureResultCallback() {
                            @Override
                            public void onCompleted(GestureDescription gestureDescription) {
                                completed.set(true);
                                incrementCounter(service, AgentConfig.KEY_GESTURE_COMPLETED_COUNT);
                                recordGesture(label, SystemClock.elapsedRealtime() - started, true, "completed");
                                completion.countDown();
                            }

                            @Override
                            public void onCancelled(GestureDescription gestureDescription) {
                                incrementCounter(service, AgentConfig.KEY_GESTURE_CANCELLED_COUNT);
                                recordGesture(label, SystemClock.elapsedRealtime() - started, false, "cancelled");
                                completion.countDown();
                            }
                        }, service.gestureCallbackHandler);
                    } catch (RuntimeException exc) {
                        incrementCounter(service, AgentConfig.KEY_GESTURE_REJECTED_COUNT);
                        recordGesture(label, SystemClock.elapsedRealtime() - started, false, "dispatch error");
                        return false;
                    }
                    if (!accepted) {
                        incrementCounter(service, AgentConfig.KEY_GESTURE_REJECTED_COUNT);
                        recordGesture(label, SystemClock.elapsedRealtime() - started, false, "rejected");
                        if (attempt == 0 && instance == service) {
                            SystemClock.sleep(100L);
                            continue;
                        }
                        return false;
                    }
                    recordGesture(label, SystemClock.elapsedRealtime() - started, true, "running");
                    try {
                        if (!completion.await(GESTURE_RESULT_TIMEOUT_MS, TimeUnit.MILLISECONDS)) {
                            incrementCounter(service, AgentConfig.KEY_GESTURE_TIMEOUT_COUNT);
                            recordGesture(label, SystemClock.elapsedRealtime() - started, false, "timeout");
                            return false;
                        }
                    } catch (InterruptedException exc) {
                        Thread.currentThread().interrupt();
                        recordGesture(label, SystemClock.elapsedRealtime() - started, false, "interrupted");
                        return false;
                    }
                    return completed.get();
                }
                return false;
            } finally {
                gestureInFlight = false;
            }
        }
    }

    private static void incrementCounter(TouchControlService service, String key) {
        android.content.SharedPreferences prefs = AgentConfig.prefs(service);
        prefs.edit().putInt(key, prefs.getInt(key, 0) + 1).apply();
    }

    private static void markDisconnected(TouchControlService service) {
        if (instance != service) {
            return;
        }
        instance = null;
        gestureInFlight = false;
        AgentConfig.prefs(service).edit()
                .putLong(AgentConfig.KEY_ACCESSIBILITY_DISCONNECTED_AT, System.currentTimeMillis())
                .apply();
    }

    private void stopGestureCallbackThread() {
        gestureCallbackHandler = null;
        if (gestureCallbackThread != null) {
            gestureCallbackThread.quitSafely();
            gestureCallbackThread = null;
        }
    }

    private static void recordGesture(String label, long durationMs, boolean success, String detail) {
        lastGestureMs = Math.max(0, durationMs);
        lastGestureResult = label + ":" + (success ? "ok" : "fail") + ":" + detail;
        TouchControlService service = instance;
        if (service != null) {
            AgentConfig.prefs(service)
                    .edit()
                    .putLong(AgentConfig.KEY_LAST_GESTURE_MS, lastGestureMs)
                    .putString(AgentConfig.KEY_LAST_GESTURE_RESULT, lastGestureResult)
                    .apply();
        }
    }

    private static float clamp(float value) {
        return Math.max(0f, Math.min(1f, value));
    }

    private String appLabel(String packageName) {
        try {
            PackageManager manager = getPackageManager();
            ApplicationInfo info = manager.getApplicationInfo(packageName, 0);
            CharSequence label = manager.getApplicationLabel(info);
            return label == null ? packageName : label.toString();
        } catch (Exception exc) {
            return packageName;
        }
    }
}
