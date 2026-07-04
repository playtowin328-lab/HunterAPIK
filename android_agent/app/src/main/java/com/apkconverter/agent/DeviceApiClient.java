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
    private static final int CONNECT_TIMEOUT_MS = 12000;
    private static final int READ_TIMEOUT_MS = 12000;
    private static final int MAX_COMMAND_RESULT_LENGTH = 1200;
    private static final int NETWORK_ATTEMPTS = 3;
    private static final long RETRY_BASE_DELAY_MS = 750L;

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
        HttpURLConnection connection = openConnection(endpoint(serverUrl, "/api/devices/discover"), "POST");
        return sendJson(connection, payload);
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
            if (!token.isEmpty()) {
                connection.setRequestProperty("Authorization", "Bearer " + token);
            } else if (!deviceSecret.isEmpty()) {
                connection.setRequestProperty("X-Device-Secret", deviceSecret);
            }

            return sendJson(connection, payload);
        });
    }

    static RemoteCommand nextCommand(Context context) throws Exception {
        SharedPreferences prefs = AgentConfig.prefs(context);
        String serverUrl = prefs.getString(AgentConfig.KEY_SERVER_URL, "").trim();
        String ownerId = prefs.getString(AgentConfig.KEY_OWNER_ID, "").trim();
        String deviceSecret = prefs.getString(AgentConfig.KEY_DEVICE_SECRET, "").trim();

        if (serverUrl.isEmpty() || ownerId.isEmpty() || deviceSecret.isEmpty()) {
            return null;
        }

        return withRetry(() -> {
            String endpoint = serverUrl.replaceAll("/+$", "")
                    + "/api/devices/commands/next?owner_id=" + urlEncode(ownerId)
                    + "&device_id=" + urlEncode(AgentConfig.getDeviceId(context));

            HttpURLConnection connection = openConnection(endpoint, "GET");
            connection.setRequestProperty("X-Device-Secret", deviceSecret);

            JSONObject response = new JSONObject(readSuccessfulResponse(connection));
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
        });
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
            connection.setRequestProperty("X-Device-Secret", deviceSecret);

            sendJson(connection, payload);
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
            connection.setRequestProperty("X-Device-Secret", deviceSecret);

            sendJson(connection, payload);
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
        String responseText = sendJson(connection, payload);
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
        Exception lastException = null;
        for (int attempt = 0; attempt < NETWORK_ATTEMPTS; attempt++) {
            try {
                return call.run();
            } catch (Exception exc) {
                lastException = exc;
                if (attempt == NETWORK_ATTEMPTS - 1 || !isRetryable(exc)) {
                    throw exc;
                }
                try {
                    Thread.sleep(RETRY_BASE_DELAY_MS * (1L << attempt));
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
        if (message == null) {
            return true;
        }
        return !message.startsWith("HTTP 400")
                && !message.startsWith("HTTP 401")
                && !message.startsWith("HTTP 403")
                && !message.startsWith("HTTP 404");
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
