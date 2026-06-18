package com.apkconverter.agent;

import android.content.Context;
import android.content.SharedPreferences;

import java.io.BufferedReader;
import java.io.OutputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import android.util.Base64;

final class DeviceApiClient {
    private DeviceApiClient() {
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

        String endpoint = serverUrl.replaceAll("/+$", "") + "/api/devices/heartbeat";
        String payload = "{"
                + "\"owner_id\":\"" + escape(ownerId) + "\","
                + "\"device_id\":\"" + escape(AgentConfig.getDeviceId(context)) + "\","
                + "\"name\":\"" + escape(deviceName) + "\","
                + "\"type\":\"phone\","
                + "\"platform\":\"" + escape(AgentConfig.platformLabel()) + "\","
                + "\"agent\":\"android-agent\","
                + "\"telemetry\":" + AgentTelemetry.toJson(context)
                + "}";

        HttpURLConnection connection = (HttpURLConnection) new URL(endpoint).openConnection();
        connection.setRequestMethod("POST");
        connection.setConnectTimeout(12000);
        connection.setReadTimeout(12000);
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        if (!token.isEmpty()) {
            connection.setRequestProperty("Authorization", "Bearer " + token);
        } else if (!deviceSecret.isEmpty()) {
            connection.setRequestProperty("X-Device-Secret", deviceSecret);
        }

        byte[] body = payload.getBytes(StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(body.length);
        try (OutputStream outputStream = connection.getOutputStream()) {
            outputStream.write(body);
        }

        int code = connection.getResponseCode();
        BufferedReader reader = new BufferedReader(
                new InputStreamReader(
                        code >= 200 && code < 300 ? connection.getInputStream() : connection.getErrorStream(),
                        StandardCharsets.UTF_8
                )
        );

        StringBuilder response = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            response.append(line);
        }

        if (code < 200 || code >= 300) {
            throw new IllegalStateException("HTTP " + code + ": " + response);
        }

        return response.toString();
    }

    static RemoteCommand nextCommand(Context context) throws Exception {
        SharedPreferences prefs = AgentConfig.prefs(context);
        String serverUrl = prefs.getString(AgentConfig.KEY_SERVER_URL, "").trim();
        String ownerId = prefs.getString(AgentConfig.KEY_OWNER_ID, "").trim();
        String deviceSecret = prefs.getString(AgentConfig.KEY_DEVICE_SECRET, "").trim();

        if (serverUrl.isEmpty() || ownerId.isEmpty() || deviceSecret.isEmpty()) {
            return null;
        }

        String endpoint = serverUrl.replaceAll("/+$", "")
                + "/api/devices/commands/next?owner_id=" + urlEncode(ownerId)
                + "&device_id=" + urlEncode(AgentConfig.getDeviceId(context));

        HttpURLConnection connection = (HttpURLConnection) new URL(endpoint).openConnection();
        connection.setRequestMethod("GET");
        connection.setConnectTimeout(12000);
        connection.setReadTimeout(12000);
        connection.setRequestProperty("X-Device-Secret", deviceSecret);

        String responseText = readResponse(connection);
        if (connection.getResponseCode() < 200 || connection.getResponseCode() >= 300) {
            throw new IllegalStateException("HTTP " + connection.getResponseCode() + ": " + responseText);
        }

        String commandId = extractJsonString(responseText, "command_id");
        String type = extractJsonString(responseText, "type");
        if (commandId.isEmpty() || type.isEmpty()) {
            return null;
        }

        float x = extractJsonFloat(responseText, "x", -1f);
        float y = extractJsonFloat(responseText, "y", -1f);
        float endX = extractJsonFloat(responseText, "end_x", -1f);
        float endY = extractJsonFloat(responseText, "end_y", -1f);
        String text = extractJsonString(responseText, "text");
        return new RemoteCommand(commandId, type, x, y, endX, endY, text);
    }

    static void completeCommand(Context context, RemoteCommand command, String status, String result) throws Exception {
        SharedPreferences prefs = AgentConfig.prefs(context);
        String serverUrl = prefs.getString(AgentConfig.KEY_SERVER_URL, "").trim();
        String ownerId = prefs.getString(AgentConfig.KEY_OWNER_ID, "").trim();
        String deviceSecret = prefs.getString(AgentConfig.KEY_DEVICE_SECRET, "").trim();

        String endpoint = serverUrl.replaceAll("/+$", "") + "/api/devices/commands/complete";
        String payload = "{"
                + "\"owner_id\":\"" + escape(ownerId) + "\","
                + "\"device_id\":\"" + escape(AgentConfig.getDeviceId(context)) + "\","
                + "\"command_id\":\"" + escape(command.commandId) + "\","
                + "\"status\":\"" + escape(status) + "\","
                + "\"result\":\"" + escape(result) + "\""
                + "}";

        HttpURLConnection connection = (HttpURLConnection) new URL(endpoint).openConnection();
        connection.setRequestMethod("POST");
        connection.setConnectTimeout(12000);
        connection.setReadTimeout(12000);
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        connection.setRequestProperty("X-Device-Secret", deviceSecret);

        byte[] body = payload.getBytes(StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(body.length);
        try (OutputStream outputStream = connection.getOutputStream()) {
            outputStream.write(body);
        }

        String responseText = readResponse(connection);
        if (connection.getResponseCode() < 200 || connection.getResponseCode() >= 300) {
            throw new IllegalStateException("HTTP " + connection.getResponseCode() + ": " + responseText);
        }
    }

    static void uploadScreenFrame(Context context, byte[] jpegBytes) throws Exception {
        SharedPreferences prefs = AgentConfig.prefs(context);
        String serverUrl = prefs.getString(AgentConfig.KEY_SERVER_URL, "").trim();
        String ownerId = prefs.getString(AgentConfig.KEY_OWNER_ID, "").trim();
        String deviceSecret = prefs.getString(AgentConfig.KEY_DEVICE_SECRET, "").trim();
        String imageBase64 = Base64.encodeToString(jpegBytes, Base64.NO_WRAP);

        String endpoint = serverUrl.replaceAll("/+$", "") + "/api/devices/screen";
        String payload = "{"
                + "\"owner_id\":\"" + escape(ownerId) + "\","
                + "\"device_id\":\"" + escape(AgentConfig.getDeviceId(context)) + "\","
                + "\"image_base64\":\"" + imageBase64 + "\""
                + "}";

        HttpURLConnection connection = (HttpURLConnection) new URL(endpoint).openConnection();
        connection.setRequestMethod("POST");
        connection.setConnectTimeout(12000);
        connection.setReadTimeout(12000);
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        connection.setRequestProperty("X-Device-Secret", deviceSecret);

        byte[] body = payload.getBytes(StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(body.length);
        try (OutputStream outputStream = connection.getOutputStream()) {
            outputStream.write(body);
        }

        String responseText = readResponse(connection);
        if (connection.getResponseCode() < 200 || connection.getResponseCode() >= 300) {
            throw new IllegalStateException("HTTP " + connection.getResponseCode() + ": " + responseText);
        }
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

        String endpoint = serverUrl.replaceAll("/+$", "") + "/api/pair/claim";
        String payload = "{"
                + "\"pairing_code\":\"" + escape(pairingCode.trim()) + "\","
                + "\"device_id\":\"" + escape(AgentConfig.getDeviceId(context)) + "\","
                + "\"name\":\"" + escape(deviceName) + "\","
                + "\"type\":\"phone\","
                + "\"platform\":\"" + escape(AgentConfig.platformLabel()) + "\","
                + "\"agent\":\"android-agent\""
                + "}";

        HttpURLConnection connection = (HttpURLConnection) new URL(endpoint).openConnection();
        connection.setRequestMethod("POST");
        connection.setConnectTimeout(12000);
        connection.setReadTimeout(12000);
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");

        byte[] body = payload.getBytes(StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(body.length);
        try (OutputStream outputStream = connection.getOutputStream()) {
            outputStream.write(body);
        }

        int code = connection.getResponseCode();
        String responseText = readResponse(connection);

        if (code < 200 || code >= 300) {
            throw new IllegalStateException("HTTP " + code + ": " + responseText);
        }

        String ownerId = extractJsonString(responseText, "owner_id");
        String deviceSecret = extractJsonString(responseText, "device_secret");
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
        BufferedReader reader = new BufferedReader(
                new InputStreamReader(
                        code >= 200 && code < 300 ? connection.getInputStream() : connection.getErrorStream(),
                        StandardCharsets.UTF_8
                )
        );

        StringBuilder response = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            response.append(line);
        }
        return response.toString();
    }

    private static String urlEncode(String value) {
        return value.replace(" ", "%20");
    }

    private static String extractJsonString(String json, String key) {
        String needle = "\"" + key + "\"";
        int keyIndex = json.indexOf(needle);
        if (keyIndex < 0) {
            return "";
        }

        int colonIndex = json.indexOf(":", keyIndex + needle.length());
        int quoteStart = json.indexOf("\"", colonIndex + 1);
        int quoteEnd = json.indexOf("\"", quoteStart + 1);
        if (colonIndex < 0 || quoteStart < 0 || quoteEnd < 0) {
            return "";
        }

        return json.substring(quoteStart + 1, quoteEnd);
    }

    private static float extractJsonFloat(String json, String key, float fallback) {
        String needle = "\"" + key + "\"";
        int keyIndex = json.indexOf(needle);
        if (keyIndex < 0) {
            return fallback;
        }

        int colonIndex = json.indexOf(":", keyIndex + needle.length());
        if (colonIndex < 0) {
            return fallback;
        }

        int endIndex = colonIndex + 1;
        while (endIndex < json.length() && " \t\r\n".indexOf(json.charAt(endIndex)) >= 0) {
            endIndex++;
        }
        int startIndex = endIndex;
        while (endIndex < json.length() && "-0123456789.".indexOf(json.charAt(endIndex)) >= 0) {
            endIndex++;
        }

        try {
            return Float.parseFloat(json.substring(startIndex, endIndex));
        } catch (Exception exc) {
            return fallback;
        }
    }

    private static String escape(String value) {
        return value
                .replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r");
    }

    static final class RemoteCommand {
        final String commandId;
        final String type;
        final float x;
        final float y;
        final float endX;
        final float endY;
        final String text;

        RemoteCommand(String commandId, String type, float x, float y, float endX, float endY, String text) {
            this.commandId = commandId;
            this.type = type;
            this.x = x;
            this.y = y;
            this.endX = endX;
            this.endY = endY;
            this.text = text;
        }
    }
}
