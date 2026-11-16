package com.shelf.pwa.download;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * 原生离线下载服务。
 *
 * 队列持久化在 DownloadStore，WebView 只负责传清单和轮询状态；
 * 文件写入 app 私有目录，退出 WebView 后仍可继续。
 */
public final class DownloadService extends Service {
    private static final String TAG = "ShelfDownload";
    private static final String CHANNEL_ID = "shelf_downloads";
    private static final int NOTIFICATION_ID = 21031;
    private static final String ACTION_START = "com.shelf.pwa.download.START";

    private final AtomicBoolean running = new AtomicBoolean(false);
    private ExecutorService executor;
    private DownloadStore store;

    public static void enqueue(Context context, String payload) throws Exception {
        JSONObject json = new JSONObject(payload);
        DownloadStore.get(context).enqueue(json);
        Intent intent = new Intent(context, DownloadService.class);
        intent.setAction(ACTION_START);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        store = DownloadStore.get(this);
        store.resetRunning();
        executor = Executors.newSingleThreadExecutor();
        createChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(NOTIFICATION_ID, notification("准备下载", "正在准备下载队列"));
        startRunner();
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        if (executor != null) executor.shutdownNow();
        super.onDestroy();
    }

    private void startRunner() {
        if (!running.compareAndSet(false, true)) return;
        executor.execute(() -> {
            try {
                while (true) {
                    DownloadStore.DownloadRow row = store.nextQueued();
                    if (row == null) break;
                    store.markRunning(row);
                    notifyProgress(row, 0, row.totalBytes);
                    try {
                        download(row);
                    } catch (Exception error) {
                        Log.w(TAG, "download failed: " + row.url, error);
                        store.markFailed(
                                row.bookId,
                                row.chapterIdx,
                                error.getMessage() == null ? "下载失败" : error.getMessage());
                    }
                }
            } finally {
                running.set(false);
                // 修复“检查队列为空与停止服务之间又入队”的竞态。
                if (store.nextQueued() != null) {
                    startRunner();
                    return;
                }
                stopForeground(STOP_FOREGROUND_REMOVE);
                stopSelf();
            }
        });
    }

    private void download(DownloadStore.DownloadRow row) throws Exception {
        File folder = new File(getFilesDir(), "downloads/" + row.bookId);
        if (!folder.exists() && !folder.mkdirs()) {
            throw new IllegalStateException("无法创建下载目录");
        }
        File finalFile = new File(folder, String.format("%04d.m4a", row.chapterIdx));
        File partFile = new File(folder, finalFile.getName() + ".part");

        long existing = partFile.isFile() ? partFile.length() : 0;
        HttpURLConnection connection = null;
        try {
            URL url = new URL(row.url);
            connection = (HttpURLConnection) url.openConnection();
            connection.setConnectTimeout(20_000);
            connection.setReadTimeout(60_000);
            connection.setInstanceFollowRedirects(true);
            connection.setRequestProperty("Accept", "audio/*");
            connection.setRequestProperty("Accept-Encoding", "identity");
            connection.setRequestProperty("X-Download-Token", row.ticket);
            if (existing > 0) {
                connection.setRequestProperty("Range", "bytes=" + existing + "-");
            }

            int code = connection.getResponseCode();
            if (code == 401 || code == 403) {
                throw new IllegalStateException("下载票据已过期，请在网页重新下载");
            }
            if (code == 416 && existing > 0) {
                // 本地 .part 已经是完整文件，直接收尾。
                finishFile(row, partFile, finalFile, existing, existing);
                return;
            }
            if (code != 200 && code != 206) {
                throw new IllegalStateException("服务器返回 HTTP " + code);
            }

            boolean append = existing > 0 && code == 206;
            if (!append) {
                existing = 0;
                if (partFile.isFile() && !partFile.delete()) {
                    throw new IllegalStateException("无法覆盖旧下载文件");
                }
            }

            long total = connection.getContentLengthLong();
            if (total > 0) total += existing;
            long downloaded = existing;
            long lastNotified = 0;
            try (InputStream input = new BufferedInputStream(connection.getInputStream());
                 FileOutputStream output = new FileOutputStream(partFile, append)) {
                byte[] buffer = new byte[64 * 1024];
                int read;
                while ((read = input.read(buffer)) != -1) {
                    output.write(buffer, 0, read);
                    downloaded += read;
                    if (downloaded - lastNotified >= 512 * 1024) {
                        lastNotified = downloaded;
                        store.updateProgress(row.bookId, row.chapterIdx, downloaded, total);
                        notifyProgress(row, downloaded, total);
                    }
                }
            }

            if (total > 0 && downloaded < total) {
                throw new IllegalStateException("下载未完成");
            }
            finishFile(row, partFile, finalFile, downloaded, total);
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private void finishFile(
            DownloadStore.DownloadRow row,
            File partFile,
            File finalFile,
            long downloaded,
            long total) {
        if (finalFile.isFile() && !finalFile.delete()) {
            throw new IllegalStateException("无法替换旧文件");
        }
        if (!partFile.renameTo(finalFile)) {
            throw new IllegalStateException("无法保存下载文件");
        }
        store.markDone(row.bookId, row.chapterIdx, finalFile, downloaded, total);
    }

    private void notifyProgress(DownloadStore.DownloadRow row, long downloaded, long total) {
        String text = row.chapterTitle == null || row.chapterTitle.isEmpty()
                ? "正在下载"
                : row.chapterTitle;
        if (total > 0) {
            int percent = (int) Math.min(100, downloaded * 100 / total);
            text += "  " + percent + "%";
        }
        NotificationManager manager =
                (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.notify(NOTIFICATION_ID, notification(row.bookTitle, text));
        }
    }

    private Notification notification(String title, String text) {
        Intent open = getPackageManager().getLaunchIntentForPackage(getPackageName());
        PendingIntent pending = null;
        if (open != null) {
            open.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
            int flags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                flags |= PendingIntent.FLAG_IMMUTABLE;
            }
            pending = PendingIntent.getActivity(this, 0, open, flags);
        }

        Notification.Builder builder;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder = new Notification.Builder(this, CHANNEL_ID);
        } else {
            builder = new Notification.Builder(this);
        }
        builder.setSmallIcon(android.R.drawable.stat_sys_download)
                .setContentTitle(title == null || title.isEmpty() ? "声架离线下载" : title)
                .setContentText(text)
                .setOngoing(true)
                .setOnlyAlertOnce(true);
        if (pending != null) builder.setContentIntent(pending);
        return builder.build();
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager manager =
                (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null) return;
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, "离线下载", NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("下载有声书章节供离线播放");
        manager.createNotificationChannel(channel);
    }
}
