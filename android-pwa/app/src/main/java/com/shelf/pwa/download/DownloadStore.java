package com.shelf.pwa.download;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/** 离线下载的本地索引。文件放 app 私有目录，WebView 不直接接触文件系统。 */
public final class DownloadStore extends SQLiteOpenHelper {
    private static final String DB_NAME = "shelf-downloads.db";
    private static final int DB_VERSION = 4;
    private static volatile DownloadStore instance;

    public static DownloadStore get(Context context) {
        if (instance == null) {
            synchronized (DownloadStore.class) {
                if (instance == null) {
                    instance = new DownloadStore(context.getApplicationContext());
                }
            }
        }
        return instance;
    }

    private DownloadStore(Context context) {
        super(context, DB_NAME, null, DB_VERSION);
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
        db.execSQL(
                "CREATE TABLE downloads ("
                        + "book_id INTEGER NOT NULL,"
                        + "chapter_idx INTEGER NOT NULL,"
                        + "book_title TEXT NOT NULL DEFAULT '',"
                        + "book_total INTEGER NOT NULL DEFAULT 0,"
                        + "chapter_title TEXT NOT NULL DEFAULT '',"
                        + "url TEXT NOT NULL,"
                        + "ticket TEXT NOT NULL DEFAULT '',"
                        + "track_id INTEGER NOT NULL DEFAULT 0,"
                        + "start_sec REAL NOT NULL DEFAULT 0,"
                        + "duration_sec REAL NOT NULL DEFAULT 0,"
                        + "total_bytes INTEGER NOT NULL DEFAULT 0,"
                        + "downloaded_bytes INTEGER NOT NULL DEFAULT 0,"
                        + "status TEXT NOT NULL DEFAULT 'queued',"
                        + "file_path TEXT,"
                        + "error TEXT,"
                        + "updated_at INTEGER NOT NULL,"
                        + "PRIMARY KEY (book_id, chapter_idx)"
                        + ")");
        db.execSQL(
                "CREATE INDEX idx_downloads_status ON downloads(status, book_id, chapter_idx)");
        db.execSQL(
                "CREATE TABLE book_manifests ("
                        + "book_id INTEGER PRIMARY KEY,"
                        + "title TEXT NOT NULL DEFAULT '',"
                        + "chapters TEXT NOT NULL,"
                        + "updated_at INTEGER NOT NULL"
                        + ")");
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        if (oldVersion < 2) {
            db.execSQL(
                    "ALTER TABLE downloads ADD COLUMN track_id INTEGER NOT NULL DEFAULT 0");
        }
        if (oldVersion < 3) {
            db.execSQL(
                    "ALTER TABLE downloads ADD COLUMN book_total INTEGER NOT NULL DEFAULT 0");
        }
        if (oldVersion < 4) {
            db.execSQL(
                    "CREATE TABLE IF NOT EXISTS book_manifests ("
                            + "book_id INTEGER PRIMARY KEY,"
                            + "title TEXT NOT NULL DEFAULT '',"
                            + "chapters TEXT NOT NULL,"
                            + "updated_at INTEGER NOT NULL"
                            + ")");
        }
    }

    /** 把 Web 端准备的整本下载清单写入队列。已完成的章节不会重复下载。 */
    public synchronized void enqueue(JSONObject payload) throws JSONException {
        long bookId = payload.getLong("bookId");
        String bookTitle = payload.optString("title", "");
        String ticket = payload.optString("ticket", "");
        JSONArray chapters = payload.optJSONArray("chapters");
        if (bookId <= 0 || chapters == null) {
            throw new JSONException("缺少 bookId 或 chapters");
        }
        int bookTotal = payload.optInt("bookTotal", chapters.length());
        JSONArray allChapters = payload.optJSONArray("allChapters");
        if (allChapters == null || allChapters.length() == 0) {
            allChapters = chapters;
        }

        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try {
            for (int i = 0; i < chapters.length(); i++) {
                JSONObject chapter = chapters.getJSONObject(i);
                int idx = chapter.getInt("idx");
                ContentValues values = new ContentValues();
                values.put("book_id", bookId);
                values.put("chapter_idx", idx);
                values.put("book_title", bookTitle);
                values.put("book_total", bookTotal);
                values.put("chapter_title", chapter.optString("title", ""));
                values.put("url", chapter.getString("url"));
                values.put("ticket", ticket);
                values.put("track_id", chapter.optInt("trackId", 0));
                values.put("start_sec", chapter.optDouble("startSec", 0));
                values.put("duration_sec", chapter.optDouble("durationSec", 0));
                values.put("total_bytes", chapter.optLong("bytes", 0));
                values.put("downloaded_bytes", 0);
                values.put("status", "queued");
                values.putNull("file_path");
                values.putNull("error");
                values.put("updated_at", System.currentTimeMillis());

                // 已下载的章节保持原状；失败/取消的章节重新排队。
                db.insertWithOnConflict(
                        "downloads", null, values, SQLiteDatabase.CONFLICT_IGNORE);
                db.execSQL(
                        "UPDATE downloads SET ticket=?, "
                                + "status=CASE WHEN status='done' THEN status ELSE 'queued' END, "
                                + "error=CASE WHEN status='done' THEN error ELSE NULL END, "
                                + "updated_at=? WHERE book_id=? AND chapter_idx=?",
                        new Object[]{
                                ticket,
                                System.currentTimeMillis(),
                                bookId,
                                idx
                        });
            }
            ContentValues manifest = new ContentValues();
            manifest.put("book_id", bookId);
            manifest.put("title", bookTitle);
            manifest.put("chapters", allChapters.toString());
            manifest.put("updated_at", System.currentTimeMillis());
            db.insertWithOnConflict(
                    "book_manifests", null, manifest, SQLiteDatabase.CONFLICT_REPLACE);

            // 同一本书之前只下载了部分章节时，旧记录的 book_total 也要对齐。
            if (bookTotal > 0) {
                db.execSQL(
                        "UPDATE downloads SET book_total=? WHERE book_id=?",
                        new Object[]{bookTotal, bookId});
            }
            db.setTransactionSuccessful();
        } finally {
            db.endTransaction();
        }
    }

    /** 服务被系统杀掉后，上次停在 running 的章节需要重新排队。 */
    public synchronized void resetRunning() {
        ContentValues values = new ContentValues();
        values.put("status", "queued");
        values.put("updated_at", System.currentTimeMillis());
        getWritableDatabase().update(
                "downloads", values, "status='running'", null);
    }

    public synchronized DownloadRow nextQueued() {
        Cursor cursor = getReadableDatabase().query(
                "downloads",
                null,
                "status='queued'",
                null,
                null,
                null,
                "book_id, chapter_idx",
                "1");
        try {
            return cursor.moveToFirst() ? read(cursor) : null;
        } finally {
            cursor.close();
        }
    }

    public synchronized void markRunning(DownloadRow row) {
        updateStatus(row.bookId, row.chapterIdx, "running", null);
    }

    public synchronized void updateProgress(
            long bookId, int chapterIdx, long downloaded, long total) {
        ContentValues values = new ContentValues();
        values.put("downloaded_bytes", Math.max(0, downloaded));
        if (total > 0) values.put("total_bytes", total);
        values.put("updated_at", System.currentTimeMillis());
        getWritableDatabase().update(
                "downloads",
                values,
                "book_id=? AND chapter_idx=?",
                new String[]{String.valueOf(bookId), String.valueOf(chapterIdx)});
    }

    public synchronized void markDone(
            long bookId, int chapterIdx, File file, long downloaded, long total) {
        ContentValues values = new ContentValues();
        values.put("status", "done");
        values.put("file_path", file.getAbsolutePath());
        values.put("downloaded_bytes", downloaded);
        if (total > 0) values.put("total_bytes", total);
        values.putNull("error");
        values.put("updated_at", System.currentTimeMillis());
        getWritableDatabase().update(
                "downloads",
                values,
                "book_id=? AND chapter_idx=?",
                new String[]{String.valueOf(bookId), String.valueOf(chapterIdx)});
    }

    public synchronized void markFailed(long bookId, int chapterIdx, String error) {
        ContentValues values = new ContentValues();
        values.put("status", "failed");
        values.put("error", error == null ? "下载失败" : error);
        values.put("updated_at", System.currentTimeMillis());
        getWritableDatabase().update(
                "downloads",
                values,
                "book_id=? AND chapter_idx=?",
                new String[]{String.valueOf(bookId), String.valueOf(chapterIdx)});
    }

    /** 是否至少有一本已下载完成的书，用于决定启动时是否走离线流程。 */
    public synchronized boolean hasDoneBooks() {
        Cursor cursor = getReadableDatabase().rawQuery(
                "SELECT 1 FROM downloads WHERE status='done' AND file_path IS NOT NULL LIMIT 1",
                null);
        try {
            return cursor.moveToFirst();
        } finally {
            cursor.close();
        }
    }

    /** 已下载完成的章节，按章节顺序返回，供离线书架播放。 */
    public synchronized List<DownloadRow> doneChapters(long bookId) {
        List<DownloadRow> rows = new ArrayList<>();
        Cursor cursor = getReadableDatabase().query(
                "downloads",
                null,
                "book_id=? AND status='done' AND file_path IS NOT NULL",
                new String[]{String.valueOf(bookId)},
                null,
                null,
                "chapter_idx");
        try {
            while (cursor.moveToNext()) rows.add(read(cursor));
        } finally {
            cursor.close();
        }
        return rows;
    }

    public synchronized void cancelBook(long bookId) {
        ContentValues values = new ContentValues();
        values.put("status", "canceled");
        values.put("updated_at", System.currentTimeMillis());
        getWritableDatabase().update(
                "downloads", values, "book_id=?", new String[]{String.valueOf(bookId)});
    }

    public synchronized void deleteBook(long bookId) {
        getWritableDatabase().delete(
                "downloads", "book_id=?", new String[]{String.valueOf(bookId)});
    }

    /** 返回所有书的下载状态，WebView 直接轮询这个 JSON。 */
    public synchronized JSONObject snapshot() {
        JSONObject result = new JSONObject();
        JSONObject manifests = new JSONObject();
        Cursor manifestCursor = getReadableDatabase().query(
                "book_manifests",
                new String[]{"book_id", "chapters"},
                null,
                null,
                null,
                null,
                null);
        try {
            while (manifestCursor.moveToNext()) {
                try {
                    manifests.put(
                            String.valueOf(manifestCursor.getLong(0)),
                            new JSONArray(manifestCursor.getString(1)));
                } catch (JSONException ignored) {
                    // 单个坏清单不影响其他书
                }
            }
        } finally {
            manifestCursor.close();
        }
        Cursor cursor = getReadableDatabase().query(
                "downloads",
                null,
                null,
                null,
                null,
                null,
                "book_id, chapter_idx");
        try {
            while (cursor.moveToNext()) {
                DownloadRow row = read(cursor);
                String key = String.valueOf(row.bookId);
                JSONObject book = result.optJSONObject(key);
                if (book == null) {
                    book = new JSONObject();
                    try {
                        book.put("bookId", row.bookId);
                        book.put("title", row.bookTitle);
                        book.put("bookTotal", 0);
                        JSONArray allChapters = manifests.optJSONArray(key);
                        if (allChapters != null) {
                            book.put("allChapters", allChapters);
                        }
                        book.put("total", 0);
                        book.put("done", 0);
                        book.put("failed", 0);
                        book.put("downloadedBytes", 0L);
                        book.put("totalBytes", 0L);
                        book.put("status", "queued");
                        book.put("chapters", new JSONArray());
                    } catch (JSONException ignored) {
                        // JSONObject 的 put 在固定 key 下不会失败
                    }
                    try {
                        result.put(key, book);
                    } catch (JSONException ignored) {
                        // 同上
                    }
                }
                JSONArray chapters = book.optJSONArray("chapters");
                JSONObject item = new JSONObject();
                try {
                    item.put("idx", row.chapterIdx);
                    item.put("title", row.chapterTitle);
                    item.put("trackId", row.trackId);
                    item.put("startSec", row.startSec);
                    item.put("durationSec", row.durationSec);
                    item.put("status", row.status);
                    item.put("downloadedBytes", row.downloadedBytes);
                    item.put("totalBytes", row.totalBytes);
                    item.put("filePath", row.filePath == null ? "" : row.filePath);
                    item.put("error", row.error == null ? "" : row.error);
                    chapters.put(item);
                    book.put("total", chapters.length());
                    if (row.bookTotal > book.optInt("bookTotal")) {
                        book.put("bookTotal", row.bookTotal);
                    }
                    book.put("done", book.optInt("done") + ("done".equals(row.status) ? 1 : 0));
                    book.put("failed", book.optInt("failed") + ("failed".equals(row.status) ? 1 : 0));
                    book.put(
                            "downloadedBytes",
                            book.optLong("downloadedBytes") + row.downloadedBytes);
                    book.put("totalBytes", book.optLong("totalBytes") + row.totalBytes);
                    if ("running".equals(row.status)) book.put("status", "running");
                } catch (JSONException ignored) {
                    // 同上
                }
            }
            // 汇总状态：全部 done 才算 done；有 running 优先 running。
            JSONArray keys = result.names();
            if (keys != null) {
                for (int i = 0; i < keys.length(); i++) {
                    JSONObject book = result.optJSONObject(keys.optString(i));
                    if (book == null) continue;
                    int total = book.optInt("total");
                    int done = book.optInt("done");
                    int failed = book.optInt("failed");
                    try {
                        if (book.optInt("bookTotal") <= 0) {
                            JSONArray all = book.optJSONArray("allChapters");
                            book.put("bookTotal", all == null ? total : all.length());
                        }
                        if (!"running".equals(book.optString("status"))) {
                            if (total > 0 && done == total) book.put("status", "done");
                            else if (failed > 0) book.put("status", "failed");
                            else book.put("status", "queued");
                        }
                    } catch (JSONException ignored) {
                        // 同上
                    }
                }
            }
        } finally {
            cursor.close();
        }
        return result;
    }

    private void updateStatus(long bookId, int chapterIdx, String status, String error) {
        ContentValues values = new ContentValues();
        values.put("status", status);
        values.put("error", error);
        values.put("updated_at", System.currentTimeMillis());
        getWritableDatabase().update(
                "downloads",
                values,
                "book_id=? AND chapter_idx=?",
                new String[]{String.valueOf(bookId), String.valueOf(chapterIdx)});
    }

    private DownloadRow read(Cursor cursor) {
        DownloadRow row = new DownloadRow();
        row.bookId = cursor.getLong(cursor.getColumnIndexOrThrow("book_id"));
        row.chapterIdx = cursor.getInt(cursor.getColumnIndexOrThrow("chapter_idx"));
        row.bookTitle = cursor.getString(cursor.getColumnIndexOrThrow("book_title"));
        row.bookTotal = cursor.getInt(cursor.getColumnIndexOrThrow("book_total"));
        row.chapterTitle = cursor.getString(cursor.getColumnIndexOrThrow("chapter_title"));
        row.url = cursor.getString(cursor.getColumnIndexOrThrow("url"));
        row.ticket = cursor.getString(cursor.getColumnIndexOrThrow("ticket"));
        row.trackId = cursor.getInt(cursor.getColumnIndexOrThrow("track_id"));
        row.startSec = cursor.getDouble(cursor.getColumnIndexOrThrow("start_sec"));
        row.durationSec = cursor.getDouble(cursor.getColumnIndexOrThrow("duration_sec"));
        row.totalBytes = cursor.getLong(cursor.getColumnIndexOrThrow("total_bytes"));
        row.downloadedBytes = cursor.getLong(cursor.getColumnIndexOrThrow("downloaded_bytes"));
        row.status = cursor.getString(cursor.getColumnIndexOrThrow("status"));
        row.filePath = cursor.getString(cursor.getColumnIndexOrThrow("file_path"));
        row.error = cursor.getString(cursor.getColumnIndexOrThrow("error"));
        return row;
    }

    public static final class DownloadRow {
        public long bookId;
        public int chapterIdx;
        public String bookTitle;
        public int bookTotal;
        public String chapterTitle;
        public String url;
        public String ticket;
        public int trackId;
        public double startSec;
        public double durationSec;
        public long totalBytes;
        public long downloadedBytes;
        public String status;
        public String filePath;
        public String error;
    }
}
