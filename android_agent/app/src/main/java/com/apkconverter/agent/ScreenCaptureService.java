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

public class ScreenCaptureService extends Service {
    static final String ACTION_START = "com.apkconverter.agent.SCREEN_START";
    static final String ACTION_STOP = "com.apkconverter.agent.SCREEN_STOP";
    static final String EXTRA_RESULT_CODE = "result_code";
    static final String EXTRA_RESULT_DATA = "result_data";

    private static final String CHANNEL_ID = "apk_agent_screen";
    private static final int NOTIFICATION_ID = 42;

    private MediaProjection mediaProjection;
    private VirtualDisplay virtualDisplay;
    private ImageReader imageReader;
    private HandlerThread handlerThread;
    private PowerManager.WakeLock wakeLock;
    private final ExecutorService uploadExecutor = Executors.newSingleThreadExecutor();
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

        startForeground(NOTIFICATION_ID, buildNotification("Экран передаётся"));
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
        mediaProjection = manager.getMediaProjection(resultCode, resultData);

        DisplayMetrics metrics = new DisplayMetrics();
        WindowManager windowManager = (WindowManager) getSystemService(Context.WINDOW_SERVICE);
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
    }

    private void captureAndUpload(Image image) {
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
            int targetWidth = Math.min(720, cropped.getWidth());
            int targetHeight = Math.round((float) cropped.getHeight() * targetWidth / cropped.getWidth());
            Bitmap scaled = Bitmap.createScaledBitmap(cropped, targetWidth, targetHeight, true);

            ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
            scaled.compress(Bitmap.CompressFormat.JPEG, 65, outputStream);
            DeviceApiClient.uploadScreenFrame(this, outputStream.toByteArray());

            bitmap.recycle();
            cropped.recycle();
            scaled.recycle();
        } catch (Exception ignored) {
            // The heartbeat service surfaces command state; capture upload failures are retried by next frame.
        } finally {
            image.close();
        }
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
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    private void acquireWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) {
            return;
        }
        PowerManager powerManager = (PowerManager) getSystemService(Context.POWER_SERVICE);
        wakeLock = powerManager.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK,
                "apkconverter:screen-capture"
        );
        wakeLock.setReferenceCounted(false);
        wakeLock.acquire(30 * 60 * 1000L);
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
                .setContentTitle("APK Agent экран")
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
        manager.createNotificationChannel(channel);
    }
}
