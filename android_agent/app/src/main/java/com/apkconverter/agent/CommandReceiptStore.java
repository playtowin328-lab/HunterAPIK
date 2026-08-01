package com.apkconverter.agent;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;

final class CommandReceiptStore {
    private static final String KEY_RECEIPTS = "command_receipts";
    private static final int MAX_RECEIPTS = 128;
    private static final long RECEIPT_TTL_MS = 7L * 24L * 60L * 60L * 1000L;
    private static final String INTERRUPTED_RESULT = "Command replay blocked after an interrupted execution.";

    private CommandReceiptStore() {
    }

    static synchronized Receipt find(Context context, String commandId) {
        JSONObject receipt = load(context).optJSONObject(commandId);
        if (receipt == null) {
            return null;
        }
        boolean completed = "completed".equals(receipt.optString("state", "executing"));
        return new Receipt(
                receipt.optString("status", "failed"),
                receipt.optString("result", INTERRUPTED_RESULT),
                completed
        );
    }

    static synchronized boolean markStarted(Context context, String commandId) {
        return put(context, commandId, "executing", "failed", INTERRUPTED_RESULT);
    }

    static synchronized boolean complete(Context context, String commandId, String status, String result) {
        return put(context, commandId, "completed", status, result);
    }

    static synchronized int size(Context context) {
        return load(context).length();
    }

    private static boolean put(Context context, String commandId, String state, String status, String result) {
        if (commandId == null || commandId.trim().isEmpty()) {
            return false;
        }
        try {
            JSONObject receipts = load(context);
            receipts.put(commandId, new JSONObject()
                    .put("state", state)
                    .put("status", truncate(status, 32))
                    .put("result", truncate(result, 500))
                    .put("completed_at", System.currentTimeMillis()));
            return AgentConfig.prefs(context)
                    .edit()
                    .putString(KEY_RECEIPTS, trim(receipts).toString())
                    .commit();
        } catch (Exception ignored) {
            return false;
        }
    }

    private static JSONObject load(Context context) {
        SharedPreferences prefs = AgentConfig.prefs(context);
        String raw = prefs.getString(KEY_RECEIPTS, "{}");
        JSONObject source;
        try {
            source = new JSONObject(raw == null ? "{}" : raw);
        } catch (Exception ignored) {
            source = new JSONObject();
        }

        JSONObject active = new JSONObject();
        long cutoff = System.currentTimeMillis() - RECEIPT_TTL_MS;
        Iterator<String> keys = source.keys();
        while (keys.hasNext()) {
            String commandId = keys.next();
            JSONObject receipt = source.optJSONObject(commandId);
            if (receipt == null || receipt.optLong("completed_at", 0L) < cutoff) {
                continue;
            }
            try {
                active.put(commandId, receipt);
            } catch (Exception ignored) {
            }
        }
        return trim(active);
    }

    private static JSONObject trim(JSONObject source) {
        List<String> commandIds = new ArrayList<>();
        Iterator<String> keys = source.keys();
        while (keys.hasNext()) {
            commandIds.add(keys.next());
        }
        Collections.sort(commandIds, (left, right) -> Long.compare(
                source.optJSONObject(right) == null ? 0L : source.optJSONObject(right).optLong("completed_at", 0L),
                source.optJSONObject(left) == null ? 0L : source.optJSONObject(left).optLong("completed_at", 0L)
        ));

        JSONObject trimmed = new JSONObject();
        for (int index = 0; index < Math.min(MAX_RECEIPTS, commandIds.size()); index++) {
            String commandId = commandIds.get(index);
            try {
                trimmed.put(commandId, source.optJSONObject(commandId));
            } catch (Exception ignored) {
            }
        }
        return trimmed;
    }

    private static String truncate(String value, int maxLength) {
        String safeValue = value == null ? "" : value;
        return safeValue.length() <= maxLength ? safeValue : safeValue.substring(0, maxLength);
    }

    static final class Receipt {
        final String status;
        final String result;
        final boolean completed;

        Receipt(String status, String result, boolean completed) {
            this.status = status;
            this.result = result;
            this.completed = completed;
        }
    }
}
