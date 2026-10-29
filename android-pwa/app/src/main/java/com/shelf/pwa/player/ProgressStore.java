package com.shelf.pwa.player;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONObject;

/**
 * 原生侧最后一条尚未确认写入服务器的进度。
 *
 * 只存最近一条，按 bookId 分开；token 不落盘。网页重新连上后会把新 token
 * 通过 PROGRESS_CONTEXT 命令交给服务，服务再把这里的内容补传一次。
 */
final class ProgressStore {
    private static final String PREFS = "shelf_native_progress";
    private static final String KEY_PREFIX = "pending_";

    private ProgressStore() {
    }

    static JSONObject load(Context context, long bookId) {
        String raw = prefs(context).getString(KEY_PREFIX + bookId, null);
        if (raw == null || raw.isEmpty()) return null;
        try {
            return new JSONObject(raw);
        } catch (Exception ignored) {
            return null;
        }
    }

    static void save(Context context, long bookId, JSONObject progress) {
        if (bookId <= 0 || progress == null) return;
        prefs(context).edit()
                .putString(KEY_PREFIX + bookId, progress.toString())
                .apply();
    }

    /**
     * 只有当前存储的仍是刚发出去的那条时才删除；如果请求期间又写了更新的位置，
     * 保留新的，等下一轮继续上报。
     */
    static void clearIfUnchanged(
            Context context, long bookId, long sentUpdatedAt, double sentPositionSec) {
        JSONObject current = load(context, bookId);
        if (current == null) return;
        long currentUpdatedAt = current.optLong("client_updated_at", 0);
        double currentPosition = current.optDouble("position_sec", 0);
        if (currentUpdatedAt < sentUpdatedAt
                || (currentUpdatedAt == sentUpdatedAt && currentPosition <= sentPositionSec)) {
            prefs(context).edit().remove(KEY_PREFIX + bookId).apply();
        }
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}
