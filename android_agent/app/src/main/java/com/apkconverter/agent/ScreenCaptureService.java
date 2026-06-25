package com.apkconverter.agent;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
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

public class ScreenCaptureService extends Service {
    static final String ACTION_START = "com.apkconverter.agent.SCREEN_START";
    static final String ACTION_STOP = "com.apkconverter.agent.SCREEN_STOP";
    static final String EXTRA_RESULT_CODE = "result_code";
    static final String EXTRA_RESULT_DATA = "result_data";

    private static final String CHANNEL_ID = "apk_agent_screen";
    private static final int NOTIFICATION_ID = 42;
    private static volatile boolean running;
    private static final AtomicLong uploadedFrames = new AtomicLong();
    private static final AtomicLong droppedFrames = new AtomicLong();
    private static volatile long lastUploadMs;
    private static volatile String lastError = "";

    private MediaProjection mediaProjection;
    private VirtualDisplay virtualDisplay;
    private ImageReader imageReader;
    private HandlerThread handlerThread;
    private PowerManager.WakeLock wakeLock;
    private final ExecutorService uploadExecutor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean uploadInProgress = new AtomicBoolean(false);
    private long lastUploadAt;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopCapture();
            return START_NOT_STICKY;
        }

        startForeground(NOTIFICATION_ID, buildNotification("Screen is streaming"));
        if (intent == null || !ACTION_START.equals(intent.getAction())) {
            return START_STICKY;
        }

        int resultCode = intent.getIntExtra(EXTRA_RESULT_CODE, 0);
        Intent resultData = intent.getParcelableExtra(EXTRA_RESULT_DATA);
        if (resultCode == 0 || resultData == null) {
            stopSelf();
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
        stopCapture();
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
            stopSelf();
            return;
        }
        mediaProjection = manager.getMediaProjection(resultCode, resultData);
        if (mediaProjection == null) {
            lastError = "MediaProjection permission is unavailable";
            stopSelf();
            return;
        }

        DisplayMetrics metrics = new DisplayMetrics();
        WindowManager windowManager = (WindowManager) getSystemService(Context.WINDOW_SERVICE);
        if (windowManager == null) {
            lastError = "Window service is unavailable";
            stopCapture();
            return;
        }
        windowManager.getDefaultDisplay().getRealMetrics(metrics);

        int width = metrics.widthPixels;
        int height = metrics.heightPixels;
        int density = metrics.densityDpi;

        imageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2);
        handlerThread = new HandlerThread("screen-capture");
        handlerThread.start();
        Handler handler = new Handler(handlerThread.getLooper());
        mediaProjection.registerCallback(new MediaProjection.Callback() {
            @Override
            public void onStop() {
                stopCapture();
            }
        }, handler);

        imageReader.setOnImageAvailableListener(reader -> {
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
            uploadExecutor.execute(() -> captureAndUpload(image));
        }, handler);

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
        running = true;
    }

    private void captureAndUpload(Image image) {
        long started = System.currentTimeMillis();
        try {
            Image.Plane[] planes = image.getPlanes();
            ByteBuffer buffer = planes[0].getBuffer();
            int pixelStride = planes[0].getPixelStride();
            int rowStride = planes[0].getRowStride();
            int rowPadding = rowStride - pixelStride * image.getWidth();

            Bitmap bitmap = Bitmap.createBitmap(
                    image.getWidth() + rowPadding / pixelStride,
                    image.getHeight(),
                    Bitmap.Config.ARGB_8888
            );
            bitmap.copyPixelsFromBuffer(buffer);

            Bitmap cropped = Bitmap.createBitmap(bitmap, 0, 0, image.getWidth(), image.getHeight());
            int maxSize = AgentConfig.prefs(this).getInt(AgentConfig.KEY_SCREEN_MAX_SIZE, 960);
            maxSize = Math.max(360, Math.min(2160, maxSize));
            int longestSide = Math.max(cropped.getWidth(), cropped.getHeight());
            float scale = longestSide <= maxSize ? 1f : (float) maxSize / longestSide;
            int targetWidth = Math.max(1, Math.round(cropped.getWidth() * scale));
            int targetHeight = Math.max(1, Math.round(cropped.getHeight() * scale));
            Bitmap scaled = Bitmap.createScaledBitmap(cropped, targetWidth, targetHeight, true);
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
            lastError = "";

            bitmap.recycle();
            cropped.recycle();
            scaled.recycle();
        } catch (Exception exc) {
            droppedFrames.incrementAndGet();
            lastError = String.valueOf(exc.getMessage());
            // The heartbeat service surfaces command state; capture upload failures are retried by next frame.
        } finally {
            image.close();
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

    private void stopCapture() {
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
            projection.stop();
        }
        if (handlerThread != null) {
            handlerThread.quitSafely();
            handlerThread = null;
        }
        releaseWakeLock();
        running = false;
        uploadInProgress.set(false);
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    static boolean isRunning() {
        return running;
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
        wakeLock.acquire(6 * 60 * 60 * 1000L);
    }

    private void releaseWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
        wakeLock = null;
    }

    private Notification buildNotification(String status) {
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);

        return builder
                .setContentTitle("APK Agent screen")
                .setContentText(status)
                .setSmallIcon(android.R.drawable.presence_video_online)
                .setOngoing(true)
                .build();
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
