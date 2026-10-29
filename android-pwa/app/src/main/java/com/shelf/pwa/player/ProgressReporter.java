package com.shelf.pwa.player;

import android.content.Context;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import androidx.media3.common.C;
import androidx.media3.common.MediaItem;
import androidx.media3.common.Player;

import org.json.JSONObject;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;

/**
 * 原生进度上报：PlaybackService 在后台独立工作，不依赖 WebView 是否存活。
 *
 * - 正在播放时每 15 秒上报一次；
 * - 暂停、播放结束、seek、切轨、划掉任务、服务销毁时补报；
 * - 失败先写 ProgressStore，等网页重新下发新 token 后补传；
 * - token 不落盘，只保存在当前服务进程内。
 */
final class ProgressReporter {
    private static final String TAG = "ShelfProgress";
    private static final long REPORT_INTERVAL_MS = 15_000;
    private static final int CONNECT_TIMEOUT_MS = 5_000;
    private static final int READ_TIMEOUT_MS = 5_000;

    private final Context context;
    private final Player player;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService io = Executors.newSingleThreadExecutor();

    private volatile ContextSnapshot ctx;
    private volatile boolean authRejected;
    private volatile boolean allowPendingFlush;
    private boolean destroyed;

    private final Runnable ticker = new Runnable() {
        @Override
        public void run() {
            if (destroyed) return;
            // 即使 token 过期（authRejected），也要继续刷新本地 pending，
            // 否则后台长时间播放时，本地最后位置会停在 token 失效的那一刻。
            if (ctx != null && player.isPlaying()) {
                reportNow(false);
            }
            main.postDelayed(this, REPORT_INTERVAL_MS);
        }
    };

    ProgressReporter(Context context, Player player) {
        this.context = context.getApplicationContext();
        this.player = player;
    }

    void start() {
        main.postDelayed(ticker, REPORT_INTERVAL_MS);
    }

    void setContext(
            long bookId,
            String baseUrl,
            String token,
            String deviceId,
            boolean flushPending) {
        if (bookId <= 0 || baseUrl == null || baseUrl.trim().isEmpty()) return;
        String cleanBase = baseUrl.trim();
        while (cleanBase.endsWith("/")) {
            cleanBase = cleanBase.substring(0, cleanBase.length() - 1);
        }
        ContextSnapshot previous = ctx;
        String nextToken = token != null && !token.isEmpty()
                ? token
                : (previous == null ? "" : previous.token);
        String nextDevice = deviceId != null && !deviceId.isEmpty()
                ? deviceId
                : (previous == null ? "" : previous.deviceId);
        ctx = new ContextSnapshot(bookId, cleanBase, nextToken, nextDevice);
        authRejected = false;
        // 每次 play 都是新会话：只有恢复上次进度时才允许补传旧 pending。
        allowPendingFlush = flushPending;
        if (allowPendingFlush) {
            flushPending();
        }
    }

    /** 网页刷新 access token 后调用；不改变 book/base/device。 */
    void setToken(String token) {
        if (token == null || token.isEmpty()) return;
        ContextSnapshot previous = ctx;
        if (previous == null) return;
        ctx = new ContextSnapshot(previous.bookId, previous.baseUrl, token, previous.deviceId);
        authRejected = false;
        if (allowPendingFlush) {
            flushPending();
        }
    }

    /**
     * 立即抓一次当前位置。必须在主线程调用（PlaybackService 的监听器/Handler 都在主线程）。
     */
    void reportNow(boolean explicitSeek) {
        ContextSnapshot snapshotCtx = ctx;
        if (snapshotCtx == null || destroyed) return;
        JSONObject progress = buildProgress(snapshotCtx, explicitSeek);
        if (progress == null) return;

        // 从这里开始产生的是当前会话的真实进度，后续 token 更新可以补传它。
        allowPendingFlush = true;
        ProgressStore.save(context, snapshotCtx.bookId, progress);
        submit(snapshotCtx, progress);
    }

    void shutdown() {
        destroyed = true;
        main.removeCallbacks(ticker);
        io.shutdown();
    }

    private JSONObject buildProgress(ContextSnapshot snapshotCtx, boolean explicitSeek) {
        if (player.getPlaybackState() == Player.STATE_IDLE) return null;
        MediaItem item = player.getCurrentMediaItem();
        if (item == null) return null;

        long positionMs = player.getCurrentPosition();
        if (positionMs == C.TIME_UNSET || positionMs < 0) return null;

        int trackId = 0;
        double offsetSec = 0;
        double clipStartSec = 0;
        Bundle extras = item.mediaMetadata.extras;
        if (extras != null) {
            trackId = extras.getInt("trackId", 0);
            offsetSec = extras.getDouble("offsetSec", 0);
            clipStartSec = extras.getDouble("clipStartSec", 0);
        }
        if (trackId <= 0) {
            try {
                trackId = Integer.parseInt(item.mediaId);
            } catch (Exception ignored) {
                return null;
            }
        }

        double positionSec = offsetSec + clipStartSec + positionMs / 1000.0;
        float rate = player.getPlaybackParameters().speed;
        if (rate <= 0) rate = 1f;

        try {
            JSONObject progress = new JSONObject();
            progress.put("track_id", trackId);
            progress.put("position_sec", positionSec);
            progress.put("playback_rate", rate);
            progress.put("device_id", snapshotCtx.deviceId);
            progress.put("client_updated_at", System.currentTimeMillis() / 1000);
            progress.put("explicit_seek", explicitSeek);
            return progress;
        } catch (Exception error) {
            Log.w(TAG, "build progress failed", error);
            return null;
        }
    }

    private void flushPending() {
        if (!allowPendingFlush) return;
        ContextSnapshot snapshotCtx = ctx;
        if (snapshotCtx == null || snapshotCtx.token.isEmpty() || authRejected) return;
        JSONObject pending = ProgressStore.load(context, snapshotCtx.bookId);
        if (pending == null) return;
        submit(snapshotCtx, pending);
    }

    private void submit(ContextSnapshot snapshotCtx, JSONObject progress) {
        if (snapshotCtx.token.isEmpty() || authRejected) return;
        try {
            io.execute(() -> send(snapshotCtx, progress));
        } catch (RejectedExecutionException ignored) {
            // 服务正在销毁；本地 pending 已保留
        }
    }

    private void send(ContextSnapshot snapshotCtx, JSONObject progress) {
        if (snapshotCtx.token.isEmpty() || authRejected) return;

        HttpURLConnection connection = null;
        try {
            URL url = new URL(snapshotCtx.baseUrl + "/api/v1/progress/" + snapshotCtx.bookId);
            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("PUT");
            connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
            connection.setReadTimeout(READ_TIMEOUT_MS);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setRequestProperty("Accept", "application/json");
            connection.setRequestProperty("Authorization", "Bearer " + snapshotCtx.token);

            byte[] body = progress.toString().getBytes(StandardCharsets.UTF_8);
            connection.setFixedLengthStreamingMode(body.length);
            try (OutputStream output = connection.getOutputStream()) {
                output.write(body);
            }

            int code = connection.getResponseCode();
            if (code >= 200 && code < 300) {
                ProgressStore.clearIfUnchanged(
                        context,
                        snapshotCtx.bookId,
                        progress.optLong("client_updated_at", 0),
                        progress.optDouble("position_sec", 0));
                ContextSnapshot current = ctx;
                if (current != null && current.token.equals(snapshotCtx.token)) {
                    authRejected = false;
                }
                Log.d(TAG, "progress ok book=" + snapshotCtx.bookId
                        + " pos=" + progress.optDouble("position_sec", 0));
            } else if (code == 401 || code == 403) {
                // access token 过期；保留 pending，等网页下次把新 token 推进来。
                ContextSnapshot current = ctx;
                if (current != null && current.token.equals(snapshotCtx.token)) {
                    authRejected = true;
                }
                Log.w(TAG, "progress auth rejected: " + code);
            } else {
                Log.w(TAG, "progress report failed: HTTP " + code);
            }
        } catch (Exception error) {
            Log.w(TAG, "progress report error: " + error.getMessage());
        } finally {
            if (connection != null) {
                try {
                    InputStream errorStream = connection.getErrorStream();
                    if (errorStream != null) errorStream.close();
                } catch (Exception ignored) {
                }
                connection.disconnect();
            }
        }
    }

    private static final class ContextSnapshot {
        final long bookId;
        final String baseUrl;
        final String token;
        final String deviceId;

        ContextSnapshot(long bookId, String baseUrl, String token, String deviceId) {
            this.bookId = bookId;
            this.baseUrl = baseUrl;
            this.token = token;
            this.deviceId = deviceId;
        }
    }
}
