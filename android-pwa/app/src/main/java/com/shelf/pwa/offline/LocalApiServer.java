package com.shelf.pwa.offline;

import android.content.Context;
import android.net.Uri;

import com.shelf.pwa.download.DownloadStore;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 离线模式下的本机 HTTP 服务。
 *
 * 只绑定 127.0.0.1，同时提供两件事：
 * 1. APK 内置的 web/dist 静态资源；
 * 2. 基于 DownloadStore 的离线 /api/v1 子集。
 *
 * 这样 WebView 可以像连接远程服务器一样加载同一套 WebUI，而不是只加载
 * 静态页面后停在登录页。
 */
public final class LocalApiServer {
    private static final String HOST = "127.0.0.1";
    private static LocalApiServer instance;

    private final Context context;
    private final ExecutorService clients = Executors.newCachedThreadPool();
    private ServerSocket server;
    private Thread acceptThread;
    private volatile boolean stopped;

    public static synchronized LocalApiServer ensure(Context context) throws IOException {
        if (instance == null || instance.stopped) {
            LocalApiServer created = new LocalApiServer(context.getApplicationContext());
            created.start();
            instance = created;
        }
        return instance;
    }

    public static synchronized void stopIfRunning() {
        if (instance != null) instance.stop();
    }

    private LocalApiServer(Context context) {
        this.context = context;
    }

    public int getPort() {
        return server == null ? -1 : server.getLocalPort();
    }

    private void start() throws IOException {
        server = new ServerSocket(0, 32, InetAddress.getByName(HOST));
        server.setReuseAddress(true);
        acceptThread = new Thread(() -> {
            while (!stopped) {
                try {
                    Socket socket = server.accept();
                    clients.execute(() -> handle(socket));
                } catch (IOException error) {
                    if (!stopped) {
                        // 单次 accept 失败不退出；下次再试。
                    }
                }
            }
        }, "shelf-local-api");
        acceptThread.setDaemon(true);
        acceptThread.start();
    }

    public synchronized void stop() {
        stopped = true;
        try {
            if (server != null) server.close();
        } catch (IOException ignored) {
        }
        server = null;
        clients.shutdownNow();
        instance = null;
    }

    private void handle(Socket socket) {
        try (Socket client = socket) {
            client.setSoTimeout(10_000);
            InputStream input = client.getInputStream();
            String requestLine = readLine(input);
            if (requestLine == null || requestLine.isEmpty()) return;
            String[] request = requestLine.split(" ");
            if (request.length < 2) return;
            String method = request[0];
            String target = request[1];

            int contentLength = 0;
            String line;
            while ((line = readLine(input)) != null && !line.isEmpty()) {
                int colon = line.indexOf(':');
                if (colon > 0 && line.substring(0, colon).trim()
                        .equalsIgnoreCase("Content-Length")) {
                    try {
                        contentLength = Integer.parseInt(
                                line.substring(colon + 1).trim());
                    } catch (NumberFormatException ignored) {
                    }
                }
            }
            byte[] bodyBytes = new byte[Math.max(0, Math.min(contentLength, 1_000_000))];
            int read = 0;
            while (read < bodyBytes.length) {
                int count = input.read(bodyBytes, read, bodyBytes.length - read);
                if (count < 0) break;
                read += count;
            }
            String body = new String(bodyBytes, 0, read, StandardCharsets.UTF_8);

            Uri uri = Uri.parse(target);
            String path = uri.getPath() == null ? "/" : uri.getPath();
            OutputStream output = client.getOutputStream();
            if (path.startsWith("/api/v1/")) {
                apiResponse(output, method, path, uri, body);
            } else {
                assetResponse(output, method, path);
            }
        } catch (Exception ignored) {
            // 本机服务只服务 WebView；单次请求失败不能拖垮 App。
        }
    }

    private void apiResponse(OutputStream out, String method, String path, Uri uri, String body)
            throws IOException {
        try {
            // 离线 API 与远程接口保持同样的方法语义；写操作落到本地存储。
            String api = path.substring("/api/v1".length());
            JSONObject snapshot = DownloadStore.get(context).snapshot();
            JSONArray books = localBooks(snapshot);
            OfflineStateStore state = OfflineStateStore.get(context);

            if (api.equals("/health")) {
                writeJson(out, 200, new JSONObject()
                        .put("status", "ok")
                        .put("version", "1.0.0")
                        .put("db", "ok")
                        .put("ffmpeg", true)
                        .put("libraries", books.length() > 0 ? 1 : 0)
                        .put("books", books.length())
                        .put("uptime_sec", 0));
                return;
            }
            if (api.equals("/me")) {
                writeJson(out, 200, offlineUser());
                return;
            }
            if (api.equals("/auth/passwordless-listeners")) {
                writeJson(out, 200, new JSONObject().put("items", new JSONArray()));
                return;
            }
            if (api.equals("/auth/default-listener")) {
                writeJson(out, 200, JSONObject.NULL);
                return;
            }
            if (api.equals("/libraries")) {
                JSONArray items = new JSONArray();
                if (books.length() > 0) {
                    items.put(new JSONObject()
                            .put("id", 1)
                            .put("name", "离线书架")
                            .put("root_path", "APK 内置下载")
                            .put("enabled", true)
                            .put("book_count", books.length())
                            .put("total_duration_sec", totalDuration(books))
                            .put("last_scan_at", JSONObject.NULL)
                            .put("scan", JSONObject.NULL));
                }
                writeJson(out, 200, new JSONObject()
                        .put("items", items)
                        .put("total", items.length())
                        .put("page", 1)
                        .put("page_size", 100));
                return;
            }
            if (api.equals("/series") || api.equals("/authors")
                    || api.equals("/collections") || api.equals("/devices")
                    || api.equals("/users")) {
                writeJson(out, 200, new JSONObject().put("items", new JSONArray()));
                return;
            }
            if (api.equals("/stats")) {
                writeJson(out, 200, new JSONObject()
                        .put("today_sec", 0)
                        .put("total_sec", 0)
                        .put("streak_days", 0)
                        .put("days", new JSONArray()));
                return;
            }
            if (api.equals("/progress/recent")) {
                writeJson(out, 200, recentProgress(books, state));
                return;
            }
            if (api.equals("/books")) {
                writeJson(out, 200, bookList(books, uri));
                return;
            }
            if (api.equals("/books") || api.startsWith("/books/")) {
                int[] parsed = bookId(api, "/books/");
                if (parsed == null) {
                    writeError(out, 404, "not_found", "书籍不存在");
                    return;
                }
                int id = parsed[0];
                JSONObject book = findBook(books, id);
                if (book == null) {
                    writeError(out, 404, "not_found", "书籍不存在");
                    return;
                }
                if (parsed[1] == 0) {
                    writeJson(out, 200, bookDetail(book, state));
                    return;
                }
                String suffix = api.substring(("/books/" + id).length());
                if (suffix.equals("/chapters")) {
                    writeJson(out, 200, chapterList(book));
                    return;
                }
                if (suffix.equals("/play-token")) {
                    writeJson(out, 200, new JSONObject()
                            .put("token", "offline")
                            .put("expires_in", 86400)
                            .put("expires_at", System.currentTimeMillis() / 1000 + 86400));
                    return;
                }
                if (suffix.equals("/bookmarks")) {
                    if ("POST".equals(method)) {
                        writeJson(out, 200, state.addBookmark(id, jsonBody(body)));
                    } else {
                        writeJson(out, 200, state.bookmarks(id));
                    }
                    return;
                }
            }
            if (api.startsWith("/bookmarks/")) {
                long bookmarkId = longAfter(api);
                if ("DELETE".equals(method)) {
                    state.deleteBookmark(bookmarkId);
                    writeJson(out, 200, new JSONObject().put("ok", true));
                } else {
                    writeJson(out, 200, state.updateBookmark(bookmarkId, jsonBody(body)));
                }
                return;
            }
            if (api.startsWith("/progress/") && api.endsWith("/history")) {
                writeJson(out, 200, new JSONObject()
                        .put("items", state.history(progressBookId(api))));
                return;
            }
            if (api.startsWith("/progress/")) {
                int id = numberAfter(api);
                if ("PUT".equals(method) || "POST".equals(method)) {
                    writeJson(out, 200, state.saveProgress(id, jsonBody(body)));
                } else {
                    writeJson(out, 200, state.progress(id));
                }
                return;
            }
            // 其他离线未覆盖的接口返回空对象，页面会显示空态而不是崩溃。
            writeJson(out, 200, new JSONObject());
        } catch (Exception error) {
            writeError(out, 500, "offline_api_error", "离线接口异常");
        }
    }

    private String readLine(InputStream input) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int value;
        boolean found = false;
        while ((value = input.read()) >= 0) {
            found = true;
            if (value == '\n') break;
            if (value != '\r') out.write(value);
        }
        if (!found && out.size() == 0) return null;
        return new String(out.toByteArray(), StandardCharsets.UTF_8);
    }

    private JSONArray localBooks(JSONObject snapshot) {
        JSONArray result = new JSONArray();
        List<String> keys = new ArrayList<>();
        snapshot.keys().forEachRemaining(keys::add);
        keys.sort(Comparator.comparingInt(key -> {
            try {
                return Integer.parseInt(key);
            } catch (NumberFormatException ignored) {
                return Integer.MAX_VALUE;
            }
        }));
        for (String key : keys) {
            JSONObject book = snapshot.optJSONObject(key);
            // 只要有一章下载完成就出现在离线书架；状态可能是 done/failed/queued。
            if (book == null || book.optInt("done") <= 0) continue;
            result.put(book);
        }
        return result;
    }

    private JSONObject bookList(JSONArray books, Uri uri) throws Exception {
        String keyword = value(uri, "q").toLowerCase(Locale.ROOT);
        int page = Math.max(1, intValue(uri, "page", 1));
        int pageSize = Math.max(1, Math.min(100, intValue(uri, "page_size", 40)));
        JSONArray filtered = new JSONArray();
        for (int i = 0; i < books.length(); i++) {
            JSONObject book = books.optJSONObject(i);
            if (book == null) continue;
            String title = book.optString("title").toLowerCase(Locale.ROOT);
            if (!keyword.isEmpty() && !title.contains(keyword)) continue;
            filtered.put(bookSummary(book));
        }
        int from = Math.min(filtered.length(), (page - 1) * pageSize);
        int to = Math.min(filtered.length(), from + pageSize);
        JSONArray items = new JSONArray();
        for (int i = from; i < to; i++) items.put(filtered.opt(i));
        return new JSONObject()
                .put("items", items)
                .put("total", filtered.length())
                .put("page", page)
                .put("page_size", pageSize);
    }

    private JSONObject bookSummary(JSONObject raw) {
        JSONArray chapters = allChapters(raw);
        int count = chapters.length();
        int downloadedCount = 0;
        JSONArray downloaded = raw.optJSONArray("chapters");
        if (downloaded != null) {
            for (int i = 0; i < downloaded.length(); i++) {
                JSONObject chapter = downloaded.optJSONObject(i);
                if (chapter != null && "done".equals(chapter.optString("status"))) {
                    downloadedCount++;
                }
            }
        }
        double duration = 0;
        for (int i = 0; i < chapters.length(); i++) {
            duration += chapterDuration(chapters.optJSONObject(i));
        }
        try {
            return new JSONObject()
                    .put("id", raw.optInt("bookId"))
                    .put("library_id", 1)
                    .put("title", raw.optString("title"))
                    .put("author", JSONObject.NULL)
                    .put("narrator", JSONObject.NULL)
                    .put("series_name", JSONObject.NULL)
                    .put("series_index", JSONObject.NULL)
                    .put("language", "zh")
                    .put("cover_url", JSONObject.NULL)
                    .put("cover_uploaded_by", JSONObject.NULL)
                    .put("manual_override", false)
                    .put("hidden", false)
                    .put("total_duration_sec", duration)
                    .put("intro_sec", 0)
                    .put("outro_sec", 0)
                    .put("track_count", count)
                    .put("size_bytes", raw.optLong("downloadedBytes"))
                    .put("chapter_source", "offline")
                    .put("downloaded_chapters", downloadedCount)
                    .put("added_at", 0)
                    .put("progress", JSONObject.NULL);
        } catch (Exception ignored) {
            return new JSONObject();
        }
    }

    private JSONObject bookDetail(JSONObject raw, OfflineStateStore state) {
        JSONObject summary = bookSummary(raw);
        try {
            JSONObject progress = state.progress(raw.optInt("bookId"));
            double position = progress.optDouble("position_sec", 0);
            double total = summary.optDouble("total_duration_sec", 0);
            if (position > 0) {
                summary.put("progress", new JSONObject()
                        .put("position_sec", position)
                        .put("percent", total > 0
                                ? Math.min(100, position / total * 100) : 0)
                        .put("is_finished", progress.optBoolean("is_finished")));
            }
            summary.put("subtitle", JSONObject.NULL)
                    .put("publisher", JSONObject.NULL)
                    .put("publish_year", JSONObject.NULL)
                    .put("description", "离线模式仅缓存音频和章节信息，简介需要联网后查看。")
                    .put("rel_dir", JSONObject.NULL)
                    .put("is_missing", false)
                    .put("updated_at", 0)
                    .put("tracks", trackArray(raw))
                    .put("chapters", chapterArray(raw));
            return summary;
        } catch (Exception ignored) {
            return summary;
        }
    }

    private JSONArray chapterArray(JSONObject raw) {
        JSONArray result = new JSONArray();
        JSONArray chapters = allChapters(raw);
        JSONObject downloaded = new JSONObject();
        JSONArray downloadedChapters = raw.optJSONArray("chapters");
        if (downloadedChapters != null) {
            for (int i = 0; i < downloadedChapters.length(); i++) {
                JSONObject item = downloadedChapters.optJSONObject(i);
                if (item != null && "done".equals(item.optString("status"))) {
                    try {
                        downloaded.put(String.valueOf(item.optInt("idx")), true);
                    } catch (Exception ignored) {
                    }
                }
            }
        }
        for (int i = 0; i < chapters.length(); i++) {
            JSONObject chapter = chapters.optJSONObject(i);
            if (chapter == null) continue;
            try {
                int idx = chapter.optInt("idx");
                double start = chapterStart(chapter);
                double end = chapterEnd(chapter, start);
                result.put(new JSONObject()
                        .put("id", idx)
                        .put("idx", idx)
                        .put("title", chapter.optString("title"))
                        .put("start_sec", start)
                        .put("end_sec", end > 0 ? (Object) end : JSONObject.NULL)
                        .put("track_id", chapterTrackId(chapter))
                        .put("available", downloaded.optBoolean(String.valueOf(idx))));
            } catch (Exception ignored) {
            }
        }
        return result;
    }

    private JSONArray allChapters(JSONObject raw) {
        JSONArray all = raw.optJSONArray("allChapters");
        if (all != null && all.length() > 0) return all;
        JSONArray downloaded = raw.optJSONArray("chapters");
        if (downloaded == null) downloaded = new JSONArray();
        int total = raw.optInt("bookTotal", 0);
        if (total <= downloaded.length()) return downloaded;

        // 旧版本只存了已选章节；用 bookTotal 补齐缺失章节占位，
        // 让离线详情至少能把未下载章节显示成灰色，而不是整章消失。
        JSONObject byIndex = new JSONObject();
        for (int i = 0; i < downloaded.length(); i++) {
            JSONObject chapter = downloaded.optJSONObject(i);
            if (chapter == null) continue;
            try {
                byIndex.put(String.valueOf(chapter.optInt("idx")), chapter);
            } catch (Exception ignored) {
            }
        }
        JSONArray merged = new JSONArray();
        for (int idx = 0; idx < total; idx++) {
            JSONObject chapter = byIndex.optJSONObject(String.valueOf(idx));
            if (chapter != null) {
                merged.put(chapter);
                continue;
            }
            try {
                merged.put(new JSONObject()
                        .put("idx", idx)
                        .put("title", "第 " + (idx + 1) + " 章（未下载）")
                        .put("start_sec", 0)
                        .put("end_sec", JSONObject.NULL)
                        .put("track_id", 0));
            } catch (Exception ignored) {
            }
        }
        return merged;
    }

    private double chapterStart(JSONObject chapter) {
        return chapter.has("start_sec")
                ? chapter.optDouble("start_sec", 0)
                : chapter.optDouble("startSec", 0);
    }

    private double chapterEnd(JSONObject chapter, double start) {
        if (chapter.has("end_sec") && !chapter.isNull("end_sec")) {
            return chapter.optDouble("end_sec", 0);
        }
        double duration = chapter.optDouble("durationSec", 0);
        return duration > 0 ? start + duration : 0;
    }

    private double chapterDuration(JSONObject chapter) {
        if (chapter == null) return 0;
        double start = chapterStart(chapter);
        return Math.max(0, chapterEnd(chapter, start) - start);
    }

    private int chapterTrackId(JSONObject chapter) {
        return chapter.has("track_id")
                ? chapter.optInt("track_id")
                : chapter.optInt("trackId");
    }

    private JSONArray trackArray(JSONObject raw) {
        JSONArray result = new JSONArray();
        JSONArray chapters = raw.optJSONArray("chapters");
        if (chapters == null) return result;
        for (int i = 0; i < chapters.length(); i++) {
            JSONObject chapter = chapters.optJSONObject(i);
            if (chapter == null || !"done".equals(chapter.optString("status"))) continue;
            try {
                int idx = chapter.optInt("idx");
                double duration = chapter.optDouble("durationSec", 0);
                String path = chapter.optString("filePath");
                result.put(new JSONObject()
                        .put("id", chapter.optInt("trackId") > 0
                                ? chapter.optInt("trackId") : idx + 1)
                        .put("track_no", idx + 1)
                        .put("disc_no", 1)
                        .put("title", chapter.optString("title"))
                        .put("duration_sec", duration)
                        .put("format", "m4a")
                        .put("bitrate", JSONObject.NULL)
                        .put("stream_url", "")
                        .put("localPath", path)
                        .put("progressTrackId", chapter.optInt("trackId")));
            } catch (Exception ignored) {
            }
        }
        return result;
    }

    private JSONObject chapterList(JSONObject raw) {
        JSONArray items = chapterArray(raw);
        try {
            return new JSONObject()
                    .put("items", items)
                    .put("total", items.length())
                    .put("page", 1)
                    .put("page_size", Math.max(1, items.length()));
        } catch (Exception ignored) {
            return new JSONObject();
        }
    }

    private JSONObject offlineUser() {
        try {
            return new JSONObject()
                    .put("id", 0)
                    .put("username", "offline")
                    .put("display_name", "离线用户")
                    .put("role", "listener")
                    .put("libraries", new JSONArray().put(1))
                    .put("created_at", 0);
        } catch (Exception ignored) {
            return new JSONObject();
        }
    }

    private JSONObject findBook(JSONArray books, int id) {
        for (int i = 0; i < books.length(); i++) {
            JSONObject book = books.optJSONObject(i);
            if (book != null && book.optInt("bookId") == id) return book;
        }
        return null;
    }

    private int[] bookId(String api, String prefix) {
        if (!api.startsWith(prefix)) return null;
        String rest = api.substring(prefix.length());
        int slash = rest.indexOf('/');
        String head = slash < 0 ? rest : rest.substring(0, slash);
        try {
            int id = Integer.parseInt(head);
            return new int[]{id, slash < 0 ? 0 : 1};
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    private int numberAfter(String path) {
        int slash = path.lastIndexOf('/');
        try {
            return Integer.parseInt(path.substring(slash + 1));
        } catch (Exception ignored) {
            return 0;
        }
    }

    private int progressBookId(String path) {
        String rest = path.substring("/progress/".length());
        int slash = rest.indexOf('/');
        try {
            return Integer.parseInt(slash < 0 ? rest : rest.substring(0, slash));
        } catch (Exception ignored) {
            return 0;
        }
    }

    private long longAfter(String path) {
        int slash = path.lastIndexOf('/');
        try {
            return Long.parseLong(path.substring(slash + 1));
        } catch (Exception ignored) {
            return 0;
        }
    }

    private JSONObject jsonBody(String body) {
        try {
            return body == null || body.isEmpty() ? new JSONObject() : new JSONObject(body);
        } catch (Exception ignored) {
            return new JSONObject();
        }
    }

    private JSONObject recentProgress(JSONArray books, OfflineStateStore state) throws Exception {
        JSONArray items = new JSONArray();
        for (int i = 0; i < books.length(); i++) {
            JSONObject raw = books.optJSONObject(i);
            if (raw == null) continue;
            try {
                int id = raw.optInt("bookId");
                JSONObject progress = state.progress(id);
                if (progress.optDouble("position_sec", 0) <= 0) continue;
                JSONArray chapters = raw.optJSONArray("chapters");
                double total = 0;
                if (chapters != null) {
                    for (int j = 0; j < chapters.length(); j++) {
                        JSONObject chapter = chapters.optJSONObject(j);
                        if (chapter != null) total += chapter.optDouble("durationSec", 0);
                    }
                }
                double position = progress.optDouble("position_sec", 0);
                items.put(new JSONObject()
                        .put("book_id", id)
                        .put("title", raw.optString("title"))
                        .put("author", JSONObject.NULL)
                        .put("cover_url", JSONObject.NULL)
                        .put("position_sec", position)
                        .put("total_duration_sec", total)
                        .put("percent", total > 0 ? Math.min(100, position / total * 100) : 0)
                        .put("updated_at", progress.optLong("updated_at", 0))
                        .put("device_id", progress.optString("device_id", "offline")));
            } catch (Exception ignored) {
            }
        }
        return new JSONObject().put("items", items);
    }

    private double totalDuration(JSONArray books) {
        double total = 0;
        for (int i = 0; i < books.length(); i++) {
            JSONObject book = books.optJSONObject(i);
            if (book != null) total += book.optDouble("total_duration_sec", 0);
        }
        return total;
    }

    private String value(Uri uri, String name) {
        String value = uri.getQueryParameter(name);
        return value == null ? "" : value;
    }

    private int intValue(Uri uri, String name, int fallback) {
        try {
            return Integer.parseInt(value(uri, name));
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    private void assetResponse(OutputStream out, String method, String path) throws IOException {
        String name = path == null ? "" : path;
        while (name.startsWith("/")) name = name.substring(1);
        if (name.isEmpty() || "index.html".equals(name)) name = "index.html";
        if (name.contains("..")) {
            writeError(out, 404, "not_found", "Not found");
            return;
        }
        try {
            InputStream stream = context.getAssets().open(name);
            byte[] data = readAll(stream);
            String mime = mimeFor(name);
            write(out, 200, "OK", mime, data, method);
        } catch (IOException missing) {
            if (!name.contains(".")) {
                assetResponse(out, method, "index.html");
            } else {
                writeError(out, 404, "not_found", "Not found");
            }
        }
    }

    private byte[] readAll(InputStream stream) throws IOException {
        try (InputStream input = new BufferedInputStream(stream);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) >= 0) {
                output.write(buffer, 0, count);
            }
            return output.toByteArray();
        }
    }

    private String mimeFor(String name) {
        switch (name.substring(name.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT)) {
            case "html": return "text/html; charset=utf-8";
            case "js":
            case "mjs": return "application/javascript; charset=utf-8";
            case "css": return "text/css; charset=utf-8";
            case "json": return "application/json; charset=utf-8";
            case "svg": return "image/svg+xml";
            case "png": return "image/png";
            case "jpg":
            case "jpeg": return "image/jpeg";
            case "webp": return "image/webp";
            case "ico": return "image/x-icon";
            case "woff2": return "font/woff2";
            case "woff": return "font/woff";
            case "ttf": return "font/ttf";
            default: return "application/octet-stream";
        }
    }

    private void writeJson(OutputStream out, int status, Object json) throws IOException {
        write(out, status, status == 200 ? "OK" : "Error",
                "application/json; charset=utf-8",
                json.toString().getBytes(StandardCharsets.UTF_8), "GET");
    }

    private void writeError(OutputStream out, int status, String code, String message)
            throws IOException {
        JSONObject error = new JSONObject();
        try {
            error.put("error", new JSONObject().put("code", code).put("message", message));
        } catch (Exception ignored) {
        }
        write(out, status, "Error", "application/json; charset=utf-8",
                error.toString().getBytes(StandardCharsets.UTF_8), "GET");
    }

    private void write(OutputStream raw, int status, String reason, String mime,
                       byte[] body, String method) throws IOException {
        BufferedOutputStream out = new BufferedOutputStream(raw);
        String head = "HTTP/1.1 " + status + " " + reason + "\r\n"
                + "Content-Type: " + mime + "\r\n"
                + "Content-Length: " + body.length + "\r\n"
                + "Cache-Control: no-store\r\n"
                + "Connection: close\r\n\r\n";
        out.write(head.getBytes(StandardCharsets.UTF_8));
        if (!"HEAD".equals(method)) out.write(body);
        out.flush();
    }
}
