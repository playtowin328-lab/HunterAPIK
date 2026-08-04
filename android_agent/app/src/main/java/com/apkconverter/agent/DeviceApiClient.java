package com.apkconverter.agent;

import android.content.Context;
import android.content.SharedPreferences;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import android.util.Base64;

import org.json.JSONObject;

final class DeviceApiClient {
    private static final int CONNECT_TIMEOUT_MS = 10000;
    private static final int READ_TIMEOUT_MS = 12000;
    private static final int MAX_COMMAND_RESULT_LENGTH = 1200;
    private static final int NETWORK_ATTEMPTS = 4;
    private static final long RETRY_BASE_DELAY_MS = 500L;
    private static final long RETRY_MAX_DELAY_MS = 5000L;
    static final int COMMAND_WAIT_SECONDS = 6;
    private static volatile int lastAttemptCount = 0;
    private static volatile int consecutiveNetworkFailures = 0;
    private static volatile long lastRequestMs = 0L;
    private static volatile long lastRetryDelayMs = 0L;
    private static volatile long lastServerWaitMs = 0L;
    private static volatile long lastLongPollMs = 0L;
    private static volatile String lastNetworkError = "";

    private DeviceApiClient() {
    }

    static String discover(Context context) throws Exception {
        SharedPreferences prefs = AgentConfig.prefs(context);
        String serverUrl = prefs.getString(AgentConfig.KEY_SERVER_URL, "").trim();
        if (serverUrl.isEmpty()) {
            throw new IllegalStateException("Server URL is empty");
        }
        JSONObject payload = new JSONObject()
                .put("device_id", AgentConfig.getDeviceId(context))
                .put("name", prefs.getString(AgentConfig.KEY_DEVICE_NAME, AgentConfig.defaultDeviceName()).trim())
                .put("platform", AgentConfig.platformLabel())
                .put("agent", "android-agent")
                .put("telemetry", new JSONObject(AgentTelemetry.toJson(context)));
        return withRetry(() -> {
            HttpURLConnection connection = openConnection(endpoint(serverUrl, "/api/devices/discover"), "POST");
            try {
                return sendJson(connection, payload);
            } finally {
                connection.disconnect();
            }
        });
    }

    static String heartbeat(Context context) throws Exception {
        SharedPreferences prefs = AgentConfig.prefs(context);
        String serverUrl = prefs.getString(AgentConfig.KEY_SERVER_URL, "").trim();
        String ownerId = prefs.getString(AgentConfig.KEY_OWNER_ID, "").trim();
        String token = prefs.getString(AgentConfig.KEY_API_TOKEN, "").trim();
        String deviceSecret = prefs.getString(AgentConfig.KEY_DEVICE_SECRET, "").trim();
        String deviceName = prefs.getString(AgentConfig.KEY_DEVICE_NAME, AgentConfig.defaultDeviceName()).trim();

        if (serverUrl.isEmpty()) {
            throw new IllegalStateException("Server URL is empty");
        }
        if (ownerId.isEmpty()) {
            throw new IllegalStateException("Owner ID is empty");
        }

        HeartbeatService.nextHeartbeatSequence();
        return withRetry(() -> {
            JSONObject payload = new JSONObject()
                    .put("owner_id", ownerId)
                    .put("device_id", AgentConfig.getDeviceId(context))
                    .put("name", deviceName)
                    .put("type", "phone")
                    .put("platform", AgentConfig.platformLabel())
                    .put("agent", "android-agent")
                    .put("telemetry", new JSONObject(AgentTelemetry.toJson(context)));

            HttpURLConnection connection = openConnection(endpoint(serverUrl, "/api/devices/heartbeat"), "POST");
            try {
                if (!token.isEmpty()) {
                    connection.setRequestProperty("Authorization", "Bearer " + token);
                } else if (!deviceSecret.isEmpty()) {
                    connection.setRequestProperty("X-Device-Secret", deviceSecret);
                }

                return sendJson(connection, payload);
            } finally {
                connection.disconnect();
            }
        }, 2);
    }

    static RemoteCommand nextCommand(Context context, int waitSeconds) throws Exception {
        SharedPreferences prefs = AgentConfig.prefs(context);
        String serverUrl = prefs.getString(AgentConfig.KEY_SERVER_URL, "").trim();
        String ownerId = prefs.getString(AgentConfig.KEY_OWNER_ID, "").trim();
        String deviceSecret = prefs.getString(AgentConfig.KEY_DEVICE_SECRET, "").trim();

        if (serverUrl.isEmpty() || ownerId.isEmpty() || deviceSecret.isEmpty()) {
            return null;
        }

        int safeWaitSeconds = Math.max(0, Math.min(COMMAND_WAIT_SECONDS, waitSeconds));
        return withRetry(() -> {
            String endpoint = serverUrl.replaceAll("/+$", "")
                    + "/api/devices/commands/next?owner_id=" + urlEncode(ownerId)
                    + "&device_id=" + urlEncode(AgentConfig.getDeviceId(context))
                    + "&wait_seconds=" + safeWaitSeconds;

            HttpURLConnection connection = openConnection(endpoint, "GET");
            connection.setReadTimeout(Math.max(READ_TIMEOUT_MS, safeWaitSeconds * 1000 + 5000));
            JSONObject response;
            try {
                connection.setRequestProperty("X-Device-Secret", deviceSecret);
                response = new JSONObject(readSuccessfulResponse(connection));
                lastServerWaitMs = Math.max(0L, response.optLong("waited_ms", 0L));
            } finally {
                connection.disconnect();
            }
            JSONObject commandJson = response.optJSONObject("command");
            if (commandJson == null) {
                return null;
            }

            String commandId = commandJson.optString("command_id", "");
            String type = commandJson.optString("type", "");
            if (commandId.isEmpty() || type.isEmpty()) {
                return null;
            }

            JSONObject payload = commandJson.optJSONObject("payload");
            if (payload == null) {
                payload = new JSONObject();
            }
            float x = (float) payload.optDouble("x", -1d);
            float y = (float) payload.optDouble("y", -1d);
            float endX = (float) payload.optDouble("end_x", -1d);
            float endY = (float) payload.optDouble("end_y", -1d);
            String text = payload.optString("text", "");
            String url = payload.optString("url", "");
            String packageName = payload.optString("package", "");
            boolean revealBlackout = payload.optBoolean("reveal_blackout", false);
            int blackoutRevealMs = Math.max(500, Math.min(3000, payload.optInt("blackout_reveal_ms", 1400)));
            int maxSize = Math.max(360, Math.min(2160, payload.optInt("max_size", 960)));
            return new RemoteCommand(commandId, type, x, y, endX, endY, text, url, packageName, revealBlackout, blackoutRevealMs, maxSize);
        }, safeWaitSeconds > 0 ? 2 : NETWORK_ATTEMPTS);
    }

    static void completeCommand(Context context, RemoteCommand command, String status, String result) throws Exception {
        SharedPreferences prefs = AgentConfig.prefs(context);
        String serverUrl = prefs.getString(AgentConfig.KEY_SERVER_URL, "").trim();
        String ownerId = prefs.getString(AgentConfig.KEY_OWNER_ID, "").trim();
        String deviceSecret = prefs.getString(AgentConfig.KEY_DEVICE_SECRET, "").trim();
        withRetry(() -> {
            JSONObject payload = new JSONObject()
                    .put("owner_id", ownerId)
                    .put("device_id", AgentConfig.getDeviceId(context))
                    .put("command_id", command.commandId)
                    .put("status", status)
                    .put("result", truncate(result, MAX_COMMAND_RESULT_LENGTH));

            HttpURLConnection connection = openConnection(endpoint(serverUrl, "/api/devices/commands/complete"), "POST");
            try {
                connection.setRequestProperty("X-Device-Secret", deviceSecret);
                sendJson(connection, payload);
            } finally {
                connection.disconnect();
            }
            return null;
        });
    }

    static void uploadScreenFrame(Context context, byte[] jpegBytes, boolean blackFrame, float blackRatio) throws Exception {
        SharedPreferences prefs = AgentConfig.prefs(context);
        String serverUrl = prefs.getString(AgentConfig.KEY_SERVER_URL, "").trim();
        String ownerId = prefs.getString(AgentConfig.KEY_OWNER_ID, "").trim();
        String deviceSecret = prefs.getString(AgentConfig.KEY_DEVICE_SECRET, "").trim();
        String imageBase64 = Base64.encodeToString(jpegBytes, Base64.NO_WRAP);

        withRetry(() -> {
            JSONObject payload = new JSONObject()
                    .put("owner_id", ownerId)
                    .put("device_id", AgentConfig.getDeviceId(context))
                    .put("image_base64", imageBase64)
                    .put("black_frame", blackFrame)
                    .put("black_ratio", blackRatio);

            HttpURLConnection connection = openConnection(endpoint(serverUrl, "/api/devices/screen"), "POST");
            try {
                connection.setRequestProperty("X-Device-Secret", deviceSecret);
                sendJson(connection, payload);
            } finally {
                connection.disconnect();
            }
            return null;
        });
    }

    static String claimPairingCode(Context context, String pairingCode) throws Exception {
        SharedPreferences prefs = AgentConfig.prefs(context);
        String serverUrl = prefs.getString(AgentConfig.KEY_SERVER_URL, "").trim();
        String deviceName = prefs.getString(AgentConfig.KEY_DEVICE_NAME, AgentConfig.defaultDeviceName()).trim();

        if (serverUrl.isEmpty()) {
            throw new IllegalStateException("Server URL is empty");
        }
        if (pairingCode.trim().isEmpty()) {
            throw new IllegalStateException("Pairing code is empty");
        }

        JSONObject payload = new JSONObject()
                .put("pairing_code", pairingCode.trim())
                .put("device_id", AgentConfig.getDeviceId(context))
                .put("name", deviceName)
                .put("type", "phone")
                .put("platform", AgentConfig.platformLabel())
                .put("agent", "android-agent");

        HttpURLConnection connection = openConnection(endpoint(serverUrl, "/api/pair/claim"), "POST");
        String responseText;
        try {
            responseText = sendJson(connection, payload);
        } finally {
            connection.disconnect();
        }
        JSONObject response = new JSONObject(responseText);

        String ownerId = response.optString("owner_id", "");
        String deviceSecret = response.optString("device_secret", "");
        if (ownerId.isEmpty() || deviceSecret.isEmpty()) {
            throw new IllegalStateException("Pair response is missing owner_id or device_secret");
        }

        prefs.edit()
                .putString(AgentConfig.KEY_OWNER_ID, ownerId)
                .putString(AgentConfig.KEY_DEVICE_SECRET, deviceSecret)
                .putString(AgentConfig.KEY_API_TOKEN, "")
                .apply();

        return responseText;
    }

    private static String readResponse(HttpURLConnection connection) throws Exception {
        int code = connection.getResponseCode();
        InputStream stream = code >= 200 && code < 300 ? connection.getInputStream() : connection.getErrorStream();
        if (stream == null) {
            return "";
        }
        BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8));

        StringBuilder response = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            response.append(line);
        }
        return response.toString();
    }

    private static HttpURLConnection openConnection(String endpoint, String method) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(endpoint).openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
        connection.setReadTimeout(READ_TIMEOUT_MS);
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("User-Agent", "HunterAndroidAgent/" + BuildConfig.VERSION_NAME);
        if ("POST".equals(method)) {
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        }
        return connection;
    }

    private static String sendJson(HttpURLConnection connection, JSONObject payload) throws Exception {
        byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(body.length);
        try (OutputStream outputStream = connection.getOutputStream()) {
            outputStream.write(body);
        }
        return readSuccessfulResponse(connection);
    }

    private static String readSuccessfulResponse(HttpURLConnection connection) throws Exception {
        String responseText = readResponse(connection);
        int code = connection.getResponseCode();
        if (code < 200 || code >= 300) {
            throw new IllegalStateException("HTTP " + code + ": " + truncate(responseText, 500));
        }
        return responseText;
    }

    private static String endpoint(String serverUrl, String path) {
        return serverUrl.replaceAll("/+$", "") + path;
    }

    private static <T> T withRetry(NetworkCall<T> call) throws Exception {
        return withRetry(call, NETWORK_ATTEMPTS);
    }

    private static <T> T withRetry(NetworkCall<T> call, int maxAttempts) throws Exception {
        long started = System.currentTimeMillis();
        lastServerWaitMs = 0L;
        Exception lastException = null;
        int safeAttempts = Math.max(1, Math.min(NETWORK_ATTEMPTS, maxAttempts));
        for (int attempt = 0; attempt < safeAttempts; attempt++) {
            lastAttemptCount = attempt + 1;
            try {
                T result = call.run();
                long totalRequestMs = System.currentTimeMillis() - started;
                lastLongPollMs = lastServerWaitMs;
                lastRequestMs = Math.max(0L, totalRequestMs - lastServerWaitMs);
                lastServerWaitMs = 0L;
                lastRetryDelayMs = 0L;
                lastNetworkError = "";
                consecutiveNetworkFailures = 0;
                return result;
            } catch (Exception exc) {
                lastException = exc;
                if (attempt == safeAttempts - 1 || !isRetryable(exc)) {
                    lastRequestMs = System.currentTimeMillis() - started;
                    lastNetworkError = truncate(String.valueOf(exc.getMessage()), 220);
                    consecutiveNetworkFailures += 1;
                    throw exc;
                }
                long baseDelayMs = Math.min(RETRY_MAX_DELAY_MS, RETRY_BASE_DELAY_MS * (1L << attempt));
                long delayMs = Math.min(RETRY_MAX_DELAY_MS, baseDelayMs + (long) (Math.random() * baseDelayMs * 0.25));
                lastRetryDelayMs = delayMs;
                try {
                    Thread.sleep(delayMs);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    throw interrupted;
                }
            }
        }
        throw lastException == null ? new IllegalStateException("Network request failed") : lastException;
    }

    private static boolean isRetryable(Exception exc) {
        String message = exc.getMessage();
        if (message == null || !message.startsWith("HTTP ")) {
            return true;
        }
        try {
            int statusCode = Integer.parseInt(message.substring(5, 8));
            return statusCode == 408
                    || statusCode == 425
                    || statusCode == 429
                    || (statusCode >= 500 && statusCode <= 599);
        } catch (RuntimeException ignored) {
            return false;
        }
    }

    static int getLastAttemptCount() {
        return lastAttemptCount;
    }

    static int getConsecutiveNetworkFailures() {
        return consecutiveNetworkFailures;
    }

    static long getLastRequestMs() {
        return lastRequestMs;
    }

    static long getLastRetryDelayMs() {
        return lastRetryDelayMs;
    }

    static long getLastLongPollMs() {
        return lastLongPollMs;
    }

    static String getLastNetworkError() {
        return lastNetworkError;
    }

    private static String urlEncode(String value) throws Exception {
        return URLEncoder.encode(value, "UTF-8");
    }

    private static String truncate(String value, int maxLength) {
        if (value == null) {
            return "";
        }
        if (value.length() <= maxLength) {
            return value;
        }
        return value.substring(0, maxLength) + "...";
    }

    private interface NetworkCall<T> {
        T run() throws Exception;
    }

    static final class RemoteCommand {
        final String commandId;
        final String type;
        final float x;
        final float y;
        final float endX;
        final float endY;
        final String text;
        final String url;
        final String packageName;
        final boolean revealBlackout;
        final int blackoutRevealMs;
        final int maxSize;

        RemoteCommand(String commandId, String type, float x, float y, float endX, float endY, String text, String url, String packageName, boolean revealBlackout, int blackoutRevealMs, int maxSize) {
            this.commandId = commandId;
            this.type = type;
            this.x = x;
            this.y = y;
            this.endX = endX;
            this.endY = endY;
            this.text = text;
            this.url = url;
            this.packageName = packageName;
            this.revealBlackout = revealBlackout;
            this.blackoutRevealMs = blackoutRevealMs;
            this.maxSize = maxSize;
        }
    }
}
