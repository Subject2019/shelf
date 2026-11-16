package com.shelf.pwa.download;

import android.content.Context;
import android.net.Uri;
import android.webkit.JavascriptInterface;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.List;

/** WebView 与原生下载服务之间的窄接口。文件名/路径不暴露给网页。 */
public final class DownloadBridge {
    public interface PlaybackSink {
        void play(String payload);
    }

    private final Context context;
    private final PlaybackSink playbackSink;

    public DownloadBridge(Context context, PlaybackSink playbackSink) {
        this.context = context.getApplicationContext();
        this.playbackSink = playbackSink;
    }

    @JavascriptInterface
    public void enqueue(String payload) {
        try {
            DownloadService.enqueue(context, payload);
        } catch (Exception ignored) {
            // 参数错误由 Web 端保证；原生层避免把异常抛回 WebView。
        }
    }

    @JavascriptInterface
    public String snapshot() {
        JSONObject data = DownloadStore.get(context).snapshot();
        return data.toString();
    }

    /** 离线书架直接播放整本已下载章节，不依赖服务端 WebUI。 */
    @JavascriptInterface
    public void playBook(int bookId) {
        play(bookId, 0, 0);
    }

    /** 从某一集开始播放；章节未下载时退回第一集。 */
    @JavascriptInterface
    public void playChapter(int bookId, int chapterIdx) {
        play(bookId, chapterIdx, 0);
    }

    /** 从章节内指定秒数开始，供播放页恢复上次位置。 */
    @JavascriptInterface
    public void playAt(int bookId, int chapterIdx, double positionSec) {
        play(bookId, chapterIdx, positionSec);
    }

    private void play(int bookId, int wantedChapterIdx, double positionSec) {
        List<DownloadStore.DownloadRow> rows = DownloadStore.get(context).doneChapters(bookId);
        if (rows.isEmpty() || playbackSink == null) return;
        int startIndex = 0;
        for (int i = 0; i < rows.size(); i++) {
            if (rows.get(i).chapterIdx == wantedChapterIdx) {
                startIndex = i;
                break;
            }
        }
        double startPosition = positionSec > 0 ? positionSec : rows.get(startIndex).startSec;
        try {
            JSONObject root = new JSONObject();
            JSONArray tracks = new JSONArray();
            JSONArray starts = new JSONArray();
            JSONArray ends = new JSONArray();
            for (int i = 0; i < rows.size(); i++) {
                DownloadStore.DownloadRow row = rows.get(i);
                double duration = row.durationSec > 0 ? row.durationSec : 0;
                JSONObject track = new JSONObject();
                track.put("id", -(i + 1));
                track.put("url", Uri.fromFile(new File(row.filePath)).toString());
                track.put("title", row.chapterTitle == null ? "" : row.chapterTitle);
                track.put("artist", row.bookTitle == null ? "" : row.bookTitle);
                track.put("durationSec", duration);
                track.put("offsetSec", row.startSec);
                track.put("clipStartSec", 0);
                track.put("clipEndSec", duration);
                track.put("progressTrackId", row.trackId > 0 ? row.trackId : -(i + 1));
                tracks.put(track);
                starts.put(row.startSec);
                ends.put(row.startSec + duration);
            }
            root.put("tracks", tracks);
            root.put("startIndex", startIndex);
            root.put("startPositionSec", startPosition);
            root.put("rate", 1.0);
            root.put("bookId", bookId);
            root.put("baseUrl", "");
            root.put("token", "");
            root.put("deviceId", "");
            root.put("resume", false);
            root.put("chapterStartsSec", starts);
            root.put("chapterEndsSec", ends);
            playbackSink.play(root.toString());
        } catch (Exception ignored) {
            // 离线文件损坏时保持错误页，不崩溃 WebView。
        }
    }

    @JavascriptInterface
    public void cancelBook(int bookId) {
        DownloadStore.get(context).cancelBook(bookId);
    }

    @JavascriptInterface
    public void removeBook(int bookId) {
        DownloadStore.get(context).deleteBook(bookId);
        deleteRecursively(new File(context.getFilesDir(), "downloads/" + bookId));
    }

    private void deleteRecursively(File file) {
        if (file == null || !file.exists()) return;
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) deleteRecursively(child);
            }
        }
        // 删除失败时保留文件，避免把索引和实际文件弄成不一致状态。
        file.delete();
    }
}
