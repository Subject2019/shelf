package com.shelf.pwa.player;

import android.content.ComponentName;
import android.content.Context;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Base64;
import android.util.Log;

import androidx.media3.common.C;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MediaMetadata;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.session.MediaController;
import androidx.media3.session.SessionCommand;
import androidx.media3.session.SessionToken;

import com.google.common.util.concurrent.ListenableFuture;
import com.google.common.util.concurrent.MoreExecutors;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * 原生播放控制器：接收 WebView 通过 ShelfPlayer 桥下发的 JSON，
 * 用 Media3 MediaController 驱动 PlaybackService，并把状态回传给网页。
 */
public class NativePlayer {
    public interface StateSink {
        void onState(String json);
    }

    private static final String TAG = "ShelfNativePlayer";
    private static final String CMD_SEEK_TO = "com.shelf.pwa.SEEK_TO";
    private static final String CMD_PROGRESS_CONTEXT = "com.shelf.pwa.PROGRESS_CONTEXT";
    private static final String CMD_PROGRESS_TOKEN = "com.shelf.pwa.PROGRESS_TOKEN";

    private final Context context;
    private final StateSink sink;
    private final Handler main = new Handler(Looper.getMainLooper());

    private MediaController controller;
    private String pendingPlay;
    private boolean released;
    private String lastError;

    private long bookId;
    private String baseUrl = "";
    private String authToken = "";
    private String deviceId = "";
    private boolean resumePending;

    private final List<TrackInfo> tracks = new ArrayList<>();

    private final Runnable ticker = new Runnable() {
        @Override
        public void run() {
            emit();
            main.postDelayed(this, 500);
        }
    };

    private final Player.Listener listener = new Player.Listener() {
        @Override
        public void onIsPlayingChanged(boolean isPlaying) {
            emit();
        }

        @Override
        public void onPlaybackStateChanged(int playbackState) {
            emit();
        }

        @Override
        public void onMediaItemTransition(MediaItem mediaItem, int reason) {
            emit();
        }

        @Override
        public void onPlayerError(PlaybackException error) {
            emitError(error.getErrorCodeName() + ": " + error.getMessage());
        }
    };

    public NativePlayer(Context context, StateSink sink) {
        this.context = context.getApplicationContext();
        this.sink = sink;
        connect();
        main.postDelayed(ticker, 500);
    }

    private void connect() {
        SessionToken token = new SessionToken(
                context, new ComponentName(context, PlaybackService.class));
        ListenableFuture<MediaController> future =
                new MediaController.Builder(context, token).buildAsync();
        future.addListener(() -> {
            if (released) return;
            try {
                controller = future.get();
                controller.addListener(listener);
                if (pendingPlay != null) {
                    String json = pendingPlay;
                    pendingPlay = null;
                    doPlay(json);
                }
            } catch (Exception error) {
                Log.e(TAG, "connect failed", error);
                emitError("无法连接播放服务：" + error.getMessage());
            }
        }, MoreExecutors.directExecutor());
    }

    public void play(String json) {
        if (controller == null) {
            pendingPlay = json;
            return;
        }
        doPlay(json);
    }

    private void doPlay(String json) {
        lastError = null;
        try {
            JSONObject root = new JSONObject(json);
            JSONArray array = root.getJSONArray("tracks");
            tracks.clear();
            List<MediaItem> items = new ArrayList<>();

            String cover = root.isNull("coverUrl") ? null : root.optString("coverUrl", null);
            Uri artwork = cover == null || cover.isEmpty() ? null : Uri.parse(cover);

            // 优先用网页内嵌的封面字节：系统媒体卡片/锁屏对 http 封面加载常失败。
            String coverData = root.isNull("coverData") ? null : root.optString("coverData", null);
            byte[] artworkData = null;
            if (coverData != null && !coverData.isEmpty()) {
                try {
                    artworkData = Base64.decode(coverData, Base64.DEFAULT);
                } catch (IllegalArgumentException ignored) {
                    artworkData = null;
                }
            }

            for (int i = 0; i < array.length(); i++) {
                JSONObject item = array.getJSONObject(i);
                TrackInfo info = new TrackInfo();
                info.id = item.getInt("id");
                info.offsetSec = item.optDouble("offsetSec", 0);
                info.clipStartSec = item.optDouble("clipStartSec", 0);
                info.durationSec = item.optDouble("durationSec", 0);
                tracks.add(info);

                long clipStartMs = Math.max(0, Math.round(info.clipStartSec * 1000));
                long clipEndMs = Math.max(0, Math.round(item.optDouble("clipEndSec", 0) * 1000));
                MediaItem.ClippingConfiguration.Builder clip =
                        new MediaItem.ClippingConfiguration.Builder()
                                .setStartPositionMs(clipStartMs);
                if (clipEndMs > clipStartMs) {
                    clip.setEndPositionMs(clipEndMs);
                }

                MediaMetadata.Builder metadata = new MediaMetadata.Builder()
                        .setTitle(item.optString("title", ""))
                        .setArtist(item.optString("artist", ""));
                if (artworkData != null) {
                    metadata.setArtworkData(artworkData, MediaMetadata.PICTURE_TYPE_FRONT_COVER);
                } else if (artwork != null) {
                    metadata.setArtworkUri(artwork);
                }
                Bundle trackExtras = new Bundle();
                trackExtras.putInt("trackId", info.id);
                trackExtras.putDouble("offsetSec", info.offsetSec);
                trackExtras.putDouble("clipStartSec", info.clipStartSec);
                trackExtras.putDouble("durationSec", info.durationSec);
                metadata.setExtras(trackExtras);

                MediaItem mediaItem = new MediaItem.Builder()
                        .setUri(item.getString("url"))
                        .setMediaId(String.valueOf(info.id))
                        .setMediaMetadata(metadata.build())
                        .setClippingConfiguration(clip.build())
                        .build();
                items.add(mediaItem);
            }

            if (items.isEmpty()) {
                emitError("这本书没有可播放的音轨");
                return;
            }

            int startIndex = Math.max(0, Math.min(root.optInt("startIndex", 0), items.size() - 1));
            double startPositionSec = root.optDouble("startPositionSec", 0);
            float rate = (float) root.optDouble("rate", 1.0);

            bookId = root.optLong("bookId", 0);
            String payloadBaseUrl = root.optString("baseUrl", "");
            if (!payloadBaseUrl.isEmpty()) baseUrl = payloadBaseUrl;
            String payloadToken = root.optString("token", "");
            if (!payloadToken.isEmpty()) authToken = payloadToken;
            String payloadDevice = root.optString("deviceId", "");
            if (!payloadDevice.isEmpty()) deviceId = payloadDevice;
            resumePending = root.optBoolean("resume", false);

            // 原生本地有更新的进度（例如 token 过期导致补传失败）时，恢复播放优先用它。
            if (resumePending && bookId > 0) {
                JSONObject pending = ProgressStore.load(context, bookId);
                if (pending != null) {
                    double pendingPosition = pending.optDouble("position_sec", 0);
                    int pendingTrackId = pending.optInt("track_id", 0);
                    int pendingIndex = indexOfTrack(pendingTrackId);
                    if (pendingPosition > startPositionSec + 1 && pendingIndex >= 0) {
                        startIndex = pendingIndex;
                        startPositionSec = pendingPosition;
                    }
                }
            }

            sendProgressContext();
            TrackInfo startTrack = tracks.get(startIndex);
            double inClip = Math.max(
                    0, startPositionSec - startTrack.offsetSec - startTrack.clipStartSec);
            long startMs = Math.round(inClip * 1000);

            controller.setMediaItems(items);
            controller.setPlaybackSpeed(rate > 0 ? rate : 1f);
            controller.prepare();
            Bundle startArgs = new Bundle();
            startArgs.putInt("index", startIndex);
            startArgs.putLong("positionMs", startMs);
            controller.sendCustomCommand(
                    new SessionCommand(CMD_SEEK_TO, Bundle.EMPTY), startArgs);
            controller.play();
            // 再发一次，确保服务在 setMediaItems 之后拿到上下文（自定义命令可能排队）。
            sendProgressContext();
        } catch (Exception error) {
            Log.e(TAG, "play failed", error);
            emitError("播放失败：" + error.getMessage());
        }
    }

    public void pause() {
        if (controller != null) controller.pause();
    }

    public void resume() {
        if (controller != null) controller.play();
    }

    public void seekTo(double absoluteSec) {
        if (controller == null) return;
        int index = indexAt(absoluteSec);
        if (index < 0) return;
        TrackInfo info = tracks.get(index);
        seekToTrack(index, absoluteSec - info.offsetSec);
    }

    public void seekToTrack(int index, double positionInTrackSec) {
        if (controller == null || index < 0 || index >= tracks.size()) return;
        TrackInfo info = tracks.get(index);
        double inClip = Math.max(0, positionInTrackSec - info.clipStartSec);
        Bundle args = new Bundle();
        args.putInt("index", index);
        args.putLong("positionMs", Math.round(inClip * 1000));
        controller.sendCustomCommand(new SessionCommand(CMD_SEEK_TO, Bundle.EMPTY), args);
    }

    public void setRate(float rate) {
        if (controller != null) controller.setPlaybackSpeed(rate);
    }

    public void setVolume(float volume) {
        if (controller != null) controller.setVolume(volume);
    }

    /** 网页刷新 access token 后调用，让后台服务继续上报。 */
    public void setAuth(String token) {
        if (token == null || token.isEmpty()) return;
        authToken = token;
        sendProgressToken();
    }

    private void sendProgressToken() {
        if (controller == null || bookId <= 0 || baseUrl.isEmpty()) return;
        Bundle args = new Bundle();
        args.putString("token", authToken);
        controller.sendCustomCommand(
                new SessionCommand(CMD_PROGRESS_TOKEN, Bundle.EMPTY), args);
    }

    private void sendProgressContext() {
        if (controller == null || bookId <= 0 || baseUrl.isEmpty()) return;
        Bundle args = new Bundle();
        args.putLong("bookId", bookId);
        args.putString("baseUrl", baseUrl);
        args.putString("token", authToken);
        args.putString("deviceId", deviceId);
        args.putBoolean("flushPending", resumePending);
        controller.sendCustomCommand(
                new SessionCommand(CMD_PROGRESS_CONTEXT, Bundle.EMPTY), args);
    }

    private int indexOfTrack(int id) {
        for (int i = 0; i < tracks.size(); i++) {
            if (tracks.get(i).id == id) return i;
        }
        return -1;
    }

    public void next() {
        if (controller != null) controller.seekToNextMediaItem();
    }

    public void previous() {
        if (controller != null) controller.seekToPreviousMediaItem();
    }

    public void stop() {
        if (controller != null) {
            controller.stop();
            controller.clearMediaItems();
        }
        lastError = null;
        tracks.clear();
        emit();
    }

    public void release() {
        released = true;
        main.removeCallbacks(ticker);
        if (controller != null) {
            controller.removeListener(listener);
            controller.release();
            controller = null;
        }
    }

    private int indexAt(double absoluteSec) {
        for (int i = 0; i < tracks.size(); i++) {
            TrackInfo info = tracks.get(i);
            double end = info.offsetSec + Math.max(info.durationSec, 0.001);
            if (absoluteSec < end || i == tracks.size() - 1) return i;
        }
        return -1;
    }

    private void emit() {
        if (controller == null || tracks.isEmpty()) return;
        try {
            int index = controller.getCurrentMediaItemIndex();
            if (index < 0 || index >= tracks.size()) index = 0;
            TrackInfo info = tracks.get(index);
            long positionMs = controller.getCurrentPosition();
            if (positionMs == C.TIME_UNSET || positionMs < 0) positionMs = 0;
            double position = info.offsetSec + info.clipStartSec + positionMs / 1000.0;

            JSONObject json = new JSONObject();
            json.put("playing", controller.isPlaying());
            json.put("buffering", controller.getPlaybackState() == Player.STATE_BUFFERING);
            json.put("trackIndex", index);
            json.put("trackId", info.id);
            json.put("positionSec", position);
            json.put("rate", controller.getPlaybackParameters().speed);
            json.put("volume", controller.getVolume());
            json.put("error", lastError == null ? JSONObject.NULL : lastError);
            sink.onState(json.toString());
        } catch (Exception error) {
            Log.w(TAG, "emit failed", error);
        }
    }

    private void emitError(String message) {
        lastError = message;
        try {
            JSONObject json = new JSONObject();
            json.put("playing", false);
            json.put("buffering", false);
            json.put("trackIndex", 0);
            json.put("trackId", 0);
            json.put("positionSec", 0);
            json.put("rate", 1.0);
            json.put("error", message);
            sink.onState(json.toString());
        } catch (Exception ignored) {
        }
    }

    private static class TrackInfo {
        int id;
        double offsetSec;
        double clipStartSec;
        double durationSec;
    }
}
