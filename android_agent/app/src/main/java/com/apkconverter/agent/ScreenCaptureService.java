package com.apkconverter.agent;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.PowerManager;
import android.util.DisplayMetrics;
import android.view.WindowManager;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.UUID;

public class ScreenCaptureService extends Service {
    static final String ACTION_START = "com.apkconverter.agent.SCREEN_START";
    static final String ACTION_STOP = "com.apkconverter.agent.SCREEN_STOP";
    static final String EXTRA_RESULT_CODE = "result_code";
    static final String EXTRA_RESULT_DATA = "result_data";

    private static final String CHANNEL_ID = "apk_agent_screen";
    private static final int NOTIFICATION_ID = 42;
    private static final long PERMISSION_PROMPT_COOLDOWN_MS = 45_000L;
    private static final long PERMISSION_PROMPT_TIMEOUT_MS = 2 * 60_000L;
    private static final long WAKE_LOCK_RENEWAL_MS = 10 * 60_000L;
    private static volatile boolean running;
    private static final AtomicLong uploadedFrames = new AtomicLong();
    private static final AtomicLong droppedFrames = new AtomicLong();
    private static volatile long lastUploadMs;
    private static volatile String lastError = "";
    private static volatile long sessionStartedAt;
    private static volatile long lastFrameAt;
    private static volatile String sessionId = "";

    private MediaProjection mediaProjection;
    private VirtualDisplay virtualDisplay;
    private ImageReader imageReader;
    private HandlerThread handlerThread;
    private PowerManager.WakeLock wakeLock;
    private final ExecutorService uploadExecutor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean uploadInProgress = new AtomicBoolean(false);
    private final AtomicBoolean stopping = new AtomicBoolean(false);
    private long lastUploadAt;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopCapture("user_stopped", true);
            return START_NOT_STICKY;
        }

        if (intent == null || !ACTION_START.equals(intent.getAction())) {
            startForeground(NOTIFICATION_ID, buildNotification("Screen confirmation required"));
            lastError = "Screen consent expired after Android restarted the capture process.";
            stopCapture("process_restarted", false);
            return START_NOT_STICKY;
        }

        startForeground(NOTIFICATION_ID, buildNotification("Persistent screen session active"));

        int resultCode = intent.getIntExtra(EXTRA_RESULT_CODE, 0);
        Intent resultData = intent.getParcelableExtra(EXTRA_RESULT_DATA);
        if (resultCode == 0 || resultData == null) {
            lastError = "Screen consent data is missing.";
            stopCapture("invalid_consent", false);
            return START_NOT_STICKY;
        }

        startProjection(resultCode, resultData);
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        if (!stopping.get()) {
            stopCapture("service_destroyed", true);
        }
        uploadExecutor.shutdownNow();
        super.onDestroy();
    }

    private void startProjection(int resultCode, Intent resultData) {
        if (mediaProjection != null) {
            return;
        }
        acquireWakeLock();

        MediaProjectionManager manager = (MediaProjectionManager) getSystemService(Context.MEDIA_PROJECTION_SERVICE);
        if (manager == null) {
            lastError = "MediaProjection service is unavailable";
            stopCapture("projection_unavailable", false);
            return;
        }
        try {
            mediaProjection = manager.getMediaProjection(resultCode, resultData);
        } catch (RuntimeException exc) {
            lastError = safeMessage(exc, "MediaProjection permission was rejected");
            stopCapture("consent_rejected", false);
            return;
        }
        if (mediaProjection == null) {
            lastError = "MediaProjection permission is unavailable";
            stopCapture("consent_unavailable", false);
            return;
        }

        DisplayMetrics metrics = new DisplayMetrics();
        WindowManager windowManager = (WindowManager) getSystemService(Context.WINDOW_SERVICE);
        if (windowManager == null) {
            lastError = "Window service is unavailable";
            stopCapture("window_unavailable", true);
            return;
        }
        windowManager.getDefaultDisplay().getRealMetrics(metrics);

        int sourceWidth = metrics.widthPixels;
        int sourceHeight = metrics.heightPixels;
        int maxSize = AgentConfig.prefs(this).getInt(AgentConfig.KEY_SCREEN_MAX_SIZE, 960);
        maxSize = Math.max(360, Math.min(1440, maxSize));
        int longestSide = Math.max(sourceWidth, sourceHeight);
        float displayScale = longestSide <= maxSize ? 1f : (float) maxSize / longestSide;
        int width = Math.max(1, Math.round(sourceWidth * displayScale));
        int height = Math.max(1, Math.round(sourceHeight * displayScale));
        int density = metrics.densityDpi;

        imageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2);
        handlerThread = new HandlerThread("screen-capture");
        handlerThread.start();
        Handler handler = new Handler(handlerThread.getLooper());
        mediaProjection.registerCallback(new MediaProjection.Callback() {
            @Override
            public void onStop() {
                stopCapture("android_stopped_projection", false);
            }
        }, handler);

        imageReader.setOnImageAvailableListener(reader -> {
            acquireWakeLock();
            long now = System.currentTimeMillis();
            if (now - lastUploadAt < 900) {
                Image skipped = reader.acquireLatestImage();
                if (skipped != null) {
                    skipped.close();
                }
                return;
            }
            lastUploadAt = now;
            Image image = reader.acquireLatestImage();
            if (image == null) {
                return;
            }
            if (!uploadInProgress.compareAndSet(false, true)) {
                droppedFrames.incrementAndGet();
                image.close();
                return;
            }
            try {
                uploadExecutor.execute(() -> captureAndUpload(image));
            } catch (RuntimeException exc) {
                droppedFrames.incrementAndGet();
                lastError = String.valueOf(exc.getMessage());
                image.close();
                uploadInProgress.set(false);
            }
        }, handler);

        try {
            virtualDisplay = mediaProjection.createVirtualDisplay(
                    "apk-agent-screen",
                    width,
                    height,
                    density,
                    DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                    imageReader.getSurface(),
                    null,
                    handler
            );
        } catch (RuntimeException exc) {
            lastError = safeMessage(exc, "Unable to create screen session");
            stopCapture("virtual_display_failed", true);
            return;
        }
        if (virtualDisplay == null) {
            lastError = "Android did not create the screen session";
            stopCapture("virtual_display_unavailable", true);
            return;
        }
        sessionStartedAt = System.currentTimeMillis();
        lastFrameAt = 0L;
        sessionId = UUID.randomUUID().toString();
        running = true;
        lastError = "";
        AgentConfig.prefs(this).edit()
                .putString(AgentConfig.KEY_SCREEN_SESSION_STATE, "active")
                .putString(AgentConfig.KEY_SCREEN_SESSION_ID, sessionId)
                .putLong(AgentConfig.KEY_SCREEN_SESSION_STARTED_AT, sessionStartedAt)
                .putLong(AgentConfig.KEY_SCREEN_LAST_FRAME_AT, 0L)
                .putString(AgentConfig.KEY_SCREEN_STOP_REASON, "")
                .putBoolean(AgentConfig.KEY_SCREEN_PERMISSION_REQUIRED, false)
                .putBoolean(AgentConfig.KEY_SCREEN_PERMISSION_PENDING, false)
                .apply();
    }

    private void captureAndUpload(Image image) {
        long started = System.currentTimeMillis();
        Bitmap bitmap = null;
        Bitmap cropped = null;
        Bitmap scaled = null;
        try {
            Image.Plane[] planes = image.getPlanes();
            ByteBuffer buffer = planes[0].getBuffer();
            int pixelStride = planes[0].getPixelStride();
            int rowStride = planes[0].getRowStride();
            int rowPadding = rowStride - pixelStride * image.getWidth();

            bitmap = Bitmap.createBitmap(
                    image.getWidth() + rowPadding / pixelStride,
                    image.getHeight(),
                    Bitmap.Config.ARGB_8888
            );
            bitmap.copyPixelsFromBuffer(buffer);

            cropped = Bitmap.createBitmap(bitmap, 0, 0, image.getWidth(), image.getHeight());
            int maxSize = AgentConfig.prefs(this).getInt(AgentConfig.KEY_SCREEN_MAX_SIZE, 960);
            maxSize = Math.max(360, Math.min(1440, maxSize));
            int longestSide = Math.max(cropped.getWidth(), cropped.getHeight());
            float scale = longestSide <= maxSize ? 1f : (float) maxSize / longestSide;
            int targetWidth = Math.max(1, Math.round(cropped.getWidth() * scale));
            int targetHeight = Math.max(1, Math.round(cropped.getHeight() * scale));
            scaled = scale >= 0.999f ? cropped : Bitmap.createScaledBitmap(cropped, targetWidth, targetHeight, true);
            float blackRatio = blackFrameRatio(scaled);
            boolean blackFrame = blackRatio >= 0.985f;

            ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
            scaled.compress(Bitmap.CompressFormat.JPEG, 65, outputStream);
            DeviceApiClient.uploadScreenFrame(this, outputStream.toByteArray(), blackFrame, blackRatio);
            AgentConfig.prefs(this)
                    .edit()
                    .putBoolean(AgentConfig.KEY_SCREEN_BLACK_FRAME, blackFrame)
                    .putFloat(AgentConfig.KEY_SCREEN_BLACK_RATIO, blackRatio)
                    .apply();
            uploadedFrames.incrementAndGet();
            lastUploadMs = System.currentTimeMillis() - started;
            lastFrameAt = System.currentTimeMillis();
            lastError = "";
            AgentConfig.prefs(this).edit()
                    .putLong(AgentConfig.KEY_SCREEN_LAST_FRAME_AT, lastFrameAt)
                    .apply();
        } catch (Exception exc) {
            droppedFrames.incrementAndGet();
            lastError = String.valueOf(exc.getMessage());
            // The heartbeat service surfaces command state; capture upload failures are retried by next frame.
        } finally {
            image.close();
            if (scaled != null && scaled != cropped && !scaled.isRecycled()) {
                scaled.recycle();
            }
            if (cropped != null && !cropped.isRecycled()) {
                cropped.recycle();
            }
            if (bitmap != null && !bitmap.isRecycled()) {
                bitmap.recycle();
            }
            uploadInProgress.set(false);
        }
    }

    private float blackFrameRatio(Bitmap bitmap) {
        int width = bitmap.getWidth();
        int height = bitmap.getHeight();
        int stepX = Math.max(1, width / 48);
        int stepY = Math.max(1, height / 48);
        int total = 0;
        int black = 0;
        for (int y = stepY / 2; y < height; y += stepY) {
            for (int x = stepX / 2; x < width; x += stepX) {
                int color = bitmap.getPixel(x, y);
                int r = (color >> 16) & 0xff;
                int g = (color >> 8) & 0xff;
                int b = color & 0xff;
                if (r < 12 && g < 12 && b < 12) {
                    black++;
                }
                total++;
            }
        }
        return total == 0 ? 0f : (float) black / total;
    }

    private void stopCapture(String reason, boolean stopProjection) {
        if (!stopping.compareAndSet(false, true)) {
            return;
        }
        running = false;
        if (virtualDisplay != null) {
            virtualDisplay.release();
            virtualDisplay = null;
        }
        if (imageReader != null) {
            imageReader.close();
            imageReader = null;
        }
        if (mediaProjection != null) {
            MediaProjection projection = mediaProjection;
            mediaProjection = null;
            if (stopProjection) {
                try {
                    projection.stop();
                } catch (RuntimeException ignored) {
                }
            }
        }
        if (handlerThread != null) {
            handlerThread.quitSafely();
            handlerThread = null;
        }
        releaseWakeLock();
        uploadInProgress.set(false);
        markStopped(reason, lastError);
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    private void markStopped(String reason, String error) {
        running = false;
        long now = System.currentTimeMillis();
        String safeReason = reason == null || reason.isEmpty() ? "stopped" : reason;
        lastError = error == null ? "" : error;
        AgentConfig.prefs(this).edit()
                .putString(AgentConfig.KEY_SCREEN_SESSION_STATE, "consent_required")
                .putLong(AgentConfig.KEY_SCREEN_STOPPED_AT, now)
                .putString(AgentConfig.KEY_SCREEN_STOP_REASON, safeReason)
                .putBoolean(AgentConfig.KEY_SCREEN_PERMISSION_REQUIRED, true)
                .putBoolean(AgentConfig.KEY_SCREEN_PERMISSION_PENDING, false)
                .apply();
    }

    static boolean isRunning() {
        return running;
    }

    static boolean reservePermissionPrompt(Context context, boolean force) {
        if (running) {
            return false;
        }
        android.content.SharedPreferences prefs = AgentConfig.prefs(context);
        long now = System.currentTimeMillis();
        long requestedAt = prefs.getLong(AgentConfig.KEY_SCREEN_PERMISSION_REQUESTED_AT, 0L);
        boolean pending = prefs.getBoolean(AgentConfig.KEY_SCREEN_PERMISSION_PENDING, false);
        if (pending && now - requestedAt < PERMISSION_PROMPT_TIMEOUT_MS) {
            return false;
        }
        if (!force && requestedAt > 0 && now - requestedAt < PERMISSION_PROMPT_COOLDOWN_MS) {
            return false;
        }
        prefs.edit()
                .putString(AgentConfig.KEY_SCREEN_SESSION_STATE, "consent_pending")
                .putBoolean(AgentConfig.KEY_SCREEN_PERMISSION_REQUIRED, true)
                .putBoolean(AgentConfig.KEY_SCREEN_PERMISSION_PENDING, true)
                .putLong(AgentConfig.KEY_SCREEN_PERMISSION_REQUESTED_AT, now)
                .apply();
        return true;
    }

    static void markPermissionResult(Context context, boolean granted) {
        AgentConfig.prefs(context).edit()
                .putString(AgentConfig.KEY_SCREEN_SESSION_STATE, granted ? "starting" : "consent_required")
                .putString(AgentConfig.KEY_SCREEN_STOP_REASON, granted ? "" : "consent_denied")
                .putBoolean(AgentConfig.KEY_SCREEN_PERMISSION_REQUIRED, !granted)
                .putBoolean(AgentConfig.KEY_SCREEN_PERMISSION_PENDING, false)
                .apply();
    }

    static boolean isPermissionPending(Context context) {
        android.content.SharedPreferences prefs = AgentConfig.prefs(context);
        if (!prefs.getBoolean(AgentConfig.KEY_SCREEN_PERMISSION_PENDING, false)) {
            return false;
        }
        long requestedAt = prefs.getLong(AgentConfig.KEY_SCREEN_PERMISSION_REQUESTED_AT, 0L);
        return requestedAt > 0 && System.currentTimeMillis() - requestedAt < PERMISSION_PROMPT_TIMEOUT_MS;
    }

    static boolean isPermissionRequired(Context context) {
        return !running && AgentConfig.prefs(context).getBoolean(AgentConfig.KEY_SCREEN_PERMISSION_REQUIRED, true);
    }

    static String getSessionState(Context context) {
        if (running) {
            return "active";
        }
        if (isPermissionPending(context)) {
            return "consent_pending";
        }
        return AgentConfig.prefs(context).getString(AgentConfig.KEY_SCREEN_SESSION_STATE, "consent_required");
    }

    static String getSessionId(Context context) {
        return running ? sessionId : AgentConfig.prefs(context).getString(AgentConfig.KEY_SCREEN_SESSION_ID, "");
    }

    static long getSessionAgeSeconds(Context context) {
        long startedAt = running ? sessionStartedAt : AgentConfig.prefs(context).getLong(AgentConfig.KEY_SCREEN_SESSION_STARTED_AT, 0L);
        return startedAt > 0 ? Math.max(0L, (System.currentTimeMillis() - startedAt) / 1000L) : -1L;
    }

    static long getLastFrameAgeSeconds(Context context) {
        long frameAt = lastFrameAt > 0 ? lastFrameAt : AgentConfig.prefs(context).getLong(AgentConfig.KEY_SCREEN_LAST_FRAME_AT, 0L);
        return frameAt > 0 ? Math.max(0L, (System.currentTimeMillis() - frameAt) / 1000L) : -1L;
    }

    static String getStopReason(Context context) {
        return AgentConfig.prefs(context).getString(AgentConfig.KEY_SCREEN_STOP_REASON, "");
    }

    static long getLastUploadMs() {
        return lastUploadMs;
    }

    static long getUploadedFrames() {
        return uploadedFrames.get();
    }

    static long getDroppedFrames() {
        return droppedFrames.get();
    }

    static String getLastError() {
        return lastError == null ? "" : lastError;
    }

    private void acquireWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) {
            return;
        }
        PowerManager powerManager = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (powerManager == null) {
            return;
        }
        wakeLock = powerManager.newWakeLock(
                PowerManager.SCREEN_DIM_WAKE_LOCK | PowerManager.ON_AFTER_RELEASE,
                "apkconverter:screen-capture"
        );
        wakeLock.setReferenceCounted(false);
        wakeLock.acquire(WAKE_LOCK_RENEWAL_MS);
    }

    private void releaseWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
        wakeLock = null;
    }

    private Notification buildNotification(String status) {
        Intent openIntent = new Intent(this, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent contentIntent = PendingIntent.getActivity(
                this,
                0,
                openIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        Intent stopIntent = new Intent(this, ScreenCaptureService.class).setAction(ACTION_STOP);
        PendingIntent stopPendingIntent = PendingIntent.getService(
                this,
                1,
                stopIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);

        return builder
                .setContentTitle("APK Agent screen")
                .setContentText(status)
                .setSmallIcon(android.R.drawable.presence_video_online)
                .setContentIntent(contentIntent)
                .addAction(new Notification.Action.Builder(
                        android.R.drawable.ic_menu_close_clear_cancel,
                        "Stop",
                        stopPendingIntent
                ).build())
                .setOngoing(true)
                .build();
    }

    private static String safeMessage(Exception exc, String fallback) {
        if (exc == null || exc.getMessage() == null || exc.getMessage().trim().isEmpty()) {
            return fallback;
        }
        String message = exc.getMessage().trim();
        return message.length() <= 240 ? message : message.substring(0, 240);
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }

        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "Screen capture",
                NotificationManager.IMPORTANCE_LOW
        );
        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.createNotificationChannel(channel);
        }
    }
}
