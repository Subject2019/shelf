package com.shelf.pwa.offline;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * 离线模式的单用户进度/书签存储。
 *
 * 远程服务端用数据库保存这些状态；本机没有数据库迁移/多用户需求，
 * 用 SharedPreferences 保存单个用户的进度和书签即可，读写量很小。
 */
public final class OfflineStateStore {
    private static final String PREFS = "shelf_offline_state";
    private static final String PROGRESS_PREFIX = "progress_";
    private static final String HISTORY_PREFIX = "history_";
    private static final String BOOKMARKS = "bookmarks";
    private static final int HISTORY_LIMIT = 5;
    private static OfflineStateStore instance;

    private final SharedPreferences prefs;

    public static synchronized OfflineStateStore get(Context context) {
        if (instance == null) {
            instance = new OfflineStateStore(context.getApplicationContext());
        }
        return instance;
    }

    private OfflineStateStore(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public synchronized JSONObject progress(int bookId) {
        try {
            String raw = prefs.getString(PROGRESS_PREFIX + bookId, null);
            return raw == null ? emptyProgress(bookId) : new JSONObject(raw);
        } catch (Exception ignored) {
            return emptyProgress(bookId);
        }
    }

    /** 写入进度并追加一条回溯点；返回 ProgressPutResult 结构。 */
    public synchronized JSONObject saveProgress(int bookId, JSONObject payload) {
        try {
            long now = System.currentTimeMillis() / 1000;
            double position = Math.max(0, payload.optDouble("position_sec", 0));
            Object track = payload.has("track_id") && !payload.isNull("track_id")
                    ? payload.opt("track_id") : JSONObject.NULL;
            boolean finished = payload.optBoolean("finished", false);
            JSONObject stored = new JSONObject()
                    .put("book_id", bookId)
                    .put("position_sec", position)
                    .put("track_id", track)
                    .put("track_position_sec", 0)
                    .put("playback_rate", payload.optDouble("playback_rate", 1))
                    .put("is_finished", finished)
                    .put("device_id", payload.optString("device_id", "offline"))
                    .put("client_updated_at", payload.optLong("client_updated_at", now))
                    .put("updated_at", now);
            prefs.edit().putString(PROGRESS_PREFIX + bookId, stored.toString()).apply();
            appendHistory(bookId, stored);
            return new JSONObject()
                    .put("book_id", bookId)
                    .put("position_sec", position)
                    .put("track_id", track)
                    .put("accepted", true)
                    .put("is_finished", finished)
                    .put("updated_at", now);
        } catch (Exception ignored) {
            return emptyProgress(bookId);
        }
    }

    public synchronized JSONArray history(int bookId) {
        try {
            String raw = prefs.getString(HISTORY_PREFIX + bookId, null);
            return raw == null ? new JSONArray() : new JSONArray(raw);
        } catch (Exception ignored) {
            return new JSONArray();
        }
    }

    public synchronized JSONArray bookmarks(int bookId) {
        JSONArray all = allBookmarks();
        JSONArray result = new JSONArray();
        for (int i = 0; i < all.length(); i++) {
            JSONObject item = all.optJSONObject(i);
            if (item != null && item.optInt("book_id") == bookId) result.put(item);
        }
        return result;
    }

    public synchronized JSONObject addBookmark(int bookId, JSONObject payload) {
        JSONArray all = allBookmarks();
        long id = System.currentTimeMillis();
        for (int i = 0; i < all.length(); i++) {
            JSONObject item = all.optJSONObject(i);
            if (item != null) id = Math.max(id, item.optLong("id") + 1);
        }
        try {
            JSONObject bookmark = new JSONObject()
                    .put("id", id)
                    .put("book_id", bookId)
                    .put("position_sec", Math.max(0, payload.optDouble("position_sec", 0)))
                    .put("track_id", payload.has("track_id") && !payload.isNull("track_id")
                            ? payload.opt("track_id") : JSONObject.NULL)
                    .put("note", payload.has("note") ? payload.opt("note") : JSONObject.NULL)
                    .put("created_at", System.currentTimeMillis() / 1000);
            all.put(bookmark);
            saveBookmarks(all);
            return bookmark;
        } catch (Exception ignored) {
            return new JSONObject();
        }
    }

    public synchronized JSONObject updateBookmark(long id, JSONObject payload) {
        JSONArray all = allBookmarks();
        for (int i = 0; i < all.length(); i++) {
            JSONObject item = all.optJSONObject(i);
            if (item == null || item.optLong("id") != id) continue;
            try {
                item.put("note", payload.has("note") ? payload.opt("note") : JSONObject.NULL);
                saveBookmarks(all);
            } catch (Exception ignored) {
            }
            return item;
        }
        return new JSONObject();
    }

    public synchronized void deleteBookmark(long id) {
        JSONArray all = allBookmarks();
        JSONArray next = new JSONArray();
        for (int i = 0; i < all.length(); i++) {
            JSONObject item = all.optJSONObject(i);
            if (item == null || item.optLong("id") != id) {
                if (item != null) next.put(item);
            }
        }
        saveBookmarks(next);
    }

    private void appendHistory(int bookId, JSONObject progress) {
        try {
            JSONArray old = history(bookId);
            JSONArray next = new JSONArray();
            JSONObject point = new JSONObject()
                    .put("id", System.currentTimeMillis())
                    .put("position_sec", progress.optDouble("position_sec", 0))
                    .put("track_id", progress.opt("track_id"))
                    .put("device_id", progress.optString("device_id", "offline"))
                    .put("created_at", progress.optLong("updated_at"));
            next.put(point);
            for (int i = 0; i < old.length() && next.length() < HISTORY_LIMIT; i++) {
                JSONObject item = old.optJSONObject(i);
                if (item == null) continue;
                double diff = Math.abs(item.optDouble("position_sec", 0)
                        - point.optDouble("position_sec", 0));
                if (diff < 30) continue;
                next.put(item);
            }
            prefs.edit().putString(HISTORY_PREFIX + bookId, next.toString()).apply();
        } catch (Exception ignored) {
        }
    }

    private JSONArray allBookmarks() {
        try {
            String raw = prefs.getString(BOOKMARKS, null);
            return raw == null ? new JSONArray() : new JSONArray(raw);
        } catch (Exception ignored) {
            return new JSONArray();
        }
    }

    private void saveBookmarks(JSONArray all) {
        prefs.edit().putString(BOOKMARKS, all.toString()).apply();
    }

    private JSONObject emptyProgress(int bookId) {
        try {
            return new JSONObject()
                    .put("book_id", bookId)
                    .put("position_sec", 0)
                    .put("track_id", JSONObject.NULL)
                    .put("track_position_sec", 0)
                    .put("playback_rate", 1)
                    .put("is_finished", false)
                    .put("device_id", JSONObject.NULL)
                    .put("client_updated_at", 0)
                    .put("updated_at", 0);
        } catch (Exception ignored) {
            return new JSONObject();
        }
    }
}
