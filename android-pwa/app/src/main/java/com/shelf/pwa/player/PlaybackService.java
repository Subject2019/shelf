package com.shelf.pwa.player;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.KeyEvent;

import androidx.media3.common.AudioAttributes;
import androidx.media3.common.C;
import androidx.media3.common.MediaItem;
import androidx.media3.common.Player;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.session.CommandButton;
import androidx.media3.session.DefaultMediaNotificationProvider;
import androidx.media3.session.MediaSession;
import androidx.media3.session.MediaSessionService;
import androidx.media3.session.SessionCommand;
import androidx.media3.session.SessionCommands;
import androidx.media3.session.SessionResult;

import com.google.common.collect.ImmutableList;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import com.shelf.pwa.MainActivity;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * 后台播放：MediaSessionService + ExoPlayer。
 * 系统媒体卡片由 media3 托管，这里做三件事：
 *   - 对外暴露当前音轨的真实时长，让状态栏/锁屏显示播放进度条；
 *   - 三个媒体按钮：上一集、播放/暂停、下一集；
 *   - 保留封面（MediaMetadata 由 NativePlayer 写入）。
 *
 * 播放/暂停使用标准 playerCommand；上一集/下一集使用自定义 sessionCommand，
 * 以便单文件多章节也能按章节边界跳转，而不是依赖播放列表中的下一个 MediaItem。
 */
public class PlaybackService extends MediaSessionService {
    private static final String CMD_SEEK_TO = "com.shelf.pwa.SEEK_TO";
    private static final String CMD_PROGRESS_CONTEXT = "com.shelf.pwa.PROGRESS_CONTEXT";
    private static final String CMD_PROGRESS_TOKEN = "com.shelf.pwa.PROGRESS_TOKEN";
    static final String CMD_SLEEP_TIMER = "com.shelf.pwa.SLEEP_TIMER";
    static final String CMD_SLEEP_TIMER_CLEAR = "com.shelf.pwa.SLEEP_TIMER_CLEAR";
    static final String CMD_NEXT_UNIT = "com.shelf.pwa.NEXT_UNIT";
    static final String CMD_PREV_UNIT = "com.shelf.pwa.PREV_UNIT";
    static final String EXTRA_SLEEP_TIMER = "com.shelf.pwa.SLEEP_TIMER_STATE";
    private static final long SEEK_STEP_MS = 15_000;
    private static final long SLEEP_FADE_MS = 30_000;

    private ExoPlayer player;
    private MediaSession session;
    private ProgressReporter progressReporter;

    private final Handler sleepHandler = new Handler(Looper.getMainLooper());
    private final Runnable sleepTicker = new Runnable() {
        @Override
        public void run() {
            boolean keepRunning = tickSleepTimer();
            publishSleepState();
            if (keepRunning) {
                sleepHandler.postDelayed(this, 1000);
            }
        }
    };
    private boolean sleepTimerRunning;
    private String sleepMode = "off";
    private long sleepRemainingMs;
    private int sleepChaptersLeft;
    private boolean sleepFinishChapter;
    private boolean sleepWaitingChapterEnd;
    private int sleepUnitMark;
    private double sleepStopAtSec = -1;
    private long sleepLastTickElapsed;
    private float sleepBaseVolume = 1f;
    private double[] sleepChapterEndsSec = new double[0];
    private double[] playbackChapterStartsSec = new double[0];
    private double[] playbackChapterEndsSec = new double[0];

    @Override
    public void onCreate() {
        super.onCreate();
        setMediaNotificationProvider(new ShelfNotificationProvider(this));
        player = new ExoPlayer.Builder(this)
                // 熄屏时保持 CPU/网络唤醒，让原生睡眠定时器和网络音频继续工作。
                .setWakeMode(C.WAKE_MODE_NETWORK)
                .setAudioAttributes(
                        new AudioAttributes.Builder()
                                .setContentType(C.AUDIO_CONTENT_TYPE_SPEECH)
                                .setUsage(C.USAGE_MEDIA)
                                .build(),
                        true)
                .setHandleAudioBecomingNoisy(true)
                .setSeekBackIncrementMs(SEEK_STEP_MS)
                .setSeekForwardIncrementMs(SEEK_STEP_MS)
                .build();

        PendingIntent sessionActivity = PendingIntent.getActivity(
                this,
                0,
                new Intent(this, MainActivity.class)
                        .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);

        session = new MediaSession.Builder(this, player)
                .setSessionActivity(sessionActivity)
                .setCallback(new SessionCallback())
                .setCustomLayout(buildButtons(false))
                .build();
        publishSleepState();

        progressReporter = new ProgressReporter(this, player);
        progressReporter.start();

        // 播放/暂停图标随状态切换；系统卡片和通知会一起刷新。
        player.addListener(new Player.Listener() {
            @Override
            public void onIsPlayingChanged(boolean isPlaying) {
                if (session != null) {
                    session.setCustomLayout(buildButtons(isPlaying));
                }
                // 不管 WebView 是否还在，真正暂停/播放结束时立刻补一次进度；
                // prepare/buffering 阶段不写，避免切书瞬间把 0 写进新书。
                int playbackState = player.getPlaybackState();
                if (!isPlaying
                        && (playbackState == Player.STATE_READY
                        || playbackState == Player.STATE_ENDED)
                        && progressReporter != null) {
                    progressReporter.reportNow(false);
                }
            }

            @Override
            public void onPlaybackStateChanged(int playbackState) {
                if (playbackState == Player.STATE_ENDED && progressReporter != null) {
                    progressReporter.reportNow(false);
                }
            }

            @Override
            public void onVolumeChanged(float volume) {
                // 渐隐期间除外：用户在定时过程中调音量应成为新的恢复基准。
                if (sleepTimerRunning
                        && (!"duration".equals(sleepMode)
                        || sleepWaitingChapterEnd
                        || sleepRemainingMs > SLEEP_FADE_MS)) {
                    sleepBaseVolume = volume;
                }
            }

            @Override
            public void onPositionDiscontinuity(
                    Player.PositionInfo oldPosition,
                    Player.PositionInfo newPosition,
                    int reason) {
                if (reason == Player.DISCONTINUITY_REASON_SEEK && progressReporter != null) {
                    progressReporter.reportNow(true);
                }
            }

            @Override
            public void onMediaItemTransition(MediaItem mediaItem, int reason) {
                // 整本播放列表替换时不要上报，避免把上一本的旧位置写到新 bookId。
                if (reason != Player.MEDIA_ITEM_TRANSITION_REASON_PLAYLIST_CHANGED
                        && progressReporter != null) {
                    progressReporter.reportNow(false);
                }
            }
        });
    }

    private List<CommandButton> buildButtons(boolean isPlaying) {
        List<CommandButton> buttons = new ArrayList<>();
        buttons.add(sessionButton(
                "上一集", android.R.drawable.ic_media_previous, CMD_PREV_UNIT, 0));
        buttons.add(playPauseButton(isPlaying, 1));
        buttons.add(sessionButton(
                "下一集", android.R.drawable.ic_media_next, CMD_NEXT_UNIT, 2));
        return buttons;
    }

    private static CommandButton sessionButton(
            String name, int iconResId, String action, int compactIndex) {
        return new CommandButton.Builder()
                .setDisplayName(name)
                .setIconResId(iconResId)
                .setSessionCommand(new SessionCommand(action, Bundle.EMPTY))
                .setExtras(compactExtras(compactIndex))
                .build();
    }

    private static CommandButton playPauseButton(boolean showPauseButton, int compactIndex) {
        return new CommandButton.Builder()
                .setDisplayName(showPauseButton ? "暂停" : "播放")
                .setIconResId(showPauseButton
                        ? android.R.drawable.ic_media_pause
                        : android.R.drawable.ic_media_play)
                .setPlayerCommand(Player.COMMAND_PLAY_PAUSE)
                .setExtras(compactExtras(compactIndex))
                .build();
    }

    private static Bundle compactExtras(int index) {
        Bundle extras = new Bundle();
        extras.putInt(DefaultMediaNotificationProvider.COMMAND_KEY_COMPACT_VIEW_INDEX, index);
        return extras;
    }

    /**
     * 系统媒体通知的按钮顺序：上一集、播放/暂停、下一集。
     * 只保留章节感知的切集按钮，不再显示快退/快进 15 秒。
     */
    private static final class ShelfNotificationProvider
            extends DefaultMediaNotificationProvider {
        ShelfNotificationProvider(Context context) {
            super(context);
        }

        @Override
        protected ImmutableList<CommandButton> getMediaButtons(
                MediaSession session,
                Player.Commands playerCommands,
                ImmutableList<CommandButton> customLayout,
                boolean showPauseButton) {
            return ImmutableList.of(
                    sessionButton(
                            "上一集", android.R.drawable.ic_media_previous,
                            CMD_PREV_UNIT, 0),
                    playPauseButton(showPauseButton, 1),
                    sessionButton(
                            "下一集", android.R.drawable.ic_media_next,
                            CMD_NEXT_UNIT, 2));
        }
    }

    private final class SessionCallback implements MediaSession.Callback {
        @Override
        public MediaSession.ConnectionResult onConnect(
                MediaSession session, MediaSession.ControllerInfo controller) {
            SessionCommands commands = new SessionCommands.Builder()
                    .add(new SessionCommand(CMD_SEEK_TO, Bundle.EMPTY))
                    .add(new SessionCommand(CMD_PROGRESS_CONTEXT, Bundle.EMPTY))
                    .add(new SessionCommand(CMD_PROGRESS_TOKEN, Bundle.EMPTY))
                    .add(new SessionCommand(CMD_SLEEP_TIMER, Bundle.EMPTY))
                    .add(new SessionCommand(CMD_SLEEP_TIMER_CLEAR, Bundle.EMPTY))
                    .add(new SessionCommand(CMD_NEXT_UNIT, Bundle.EMPTY))
                    .add(new SessionCommand(CMD_PREV_UNIT, Bundle.EMPTY))
                    .build();
            // 兼容仍通过标准 seekToNext/Previous 控制的旧版车机/蓝牙控制器。
            Player.Commands playerCommands = session.getPlayer().getAvailableCommands()
                    .buildUpon()
                    .add(Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM)
                    .add(Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM)
                    // 系统媒体卡片不再显示快退/快进 15 秒，只保留上一集/下一集。
                    .remove(Player.COMMAND_SEEK_BACK)
                    .remove(Player.COMMAND_SEEK_FORWARD)
                    .build();
            // 保留 session 的自定义布局和播放器命令；不要用 ConnectionResult.accept(...)。
            // 显式把 ExoPlayer 的真实 player commands（含当前项 seek）交给系统，
            // 媒体卡片才能根据 duration/position 渲染进度条并允许拖动。
            return new MediaSession.ConnectionResult.AcceptedResultBuilder(session)
                    .setAvailableSessionCommands(commands)
                    .setAvailablePlayerCommands(playerCommands)
                    .build();
        }

        @Override
        public int onPlayerCommandRequest(
                MediaSession session,
                MediaSession.ControllerInfo controller,
                int playerCommand) {
            // Android 13+ 系统媒体卡片可能直接发标准切集命令；拦截后按章节边界执行。
            if (playerCommand == Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM) {
                seekNextUnit();
                return SessionResult.RESULT_INFO_SKIPPED;
            }
            if (playerCommand == Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM) {
                seekPreviousUnit();
                return SessionResult.RESULT_INFO_SKIPPED;
            }
            if (playerCommand == Player.COMMAND_SEEK_BACK) {
                if (player != null) player.seekBack();
                return SessionResult.RESULT_INFO_SKIPPED;
            }
            if (playerCommand == Player.COMMAND_SEEK_FORWARD) {
                if (player != null) player.seekForward();
                return SessionResult.RESULT_INFO_SKIPPED;
            }
            return SessionResult.RESULT_SUCCESS;
        }

        @Override
        public boolean onMediaButtonEvent(
                MediaSession session,
                MediaSession.ControllerInfo controller,
                Intent intent) {
            KeyEvent event = intent.getParcelableExtra(Intent.EXTRA_KEY_EVENT);
            if (event != null) {
                int keyCode = event.getKeyCode();
                boolean next = keyCode == KeyEvent.KEYCODE_MEDIA_NEXT
                        || keyCode == KeyEvent.KEYCODE_MEDIA_SKIP_FORWARD;
                boolean previous = keyCode == KeyEvent.KEYCODE_MEDIA_PREVIOUS
                        || keyCode == KeyEvent.KEYCODE_MEDIA_SKIP_BACKWARD;
                if (next || previous) {
                    if (event.getAction() == KeyEvent.ACTION_DOWN
                            && event.getRepeatCount() == 0
                            && player != null) {
                        if (next) {
                            seekNextUnit();
                        } else {
                            seekPreviousUnit();
                        }
                    }
                    // ACTION_UP 也消费掉，避免系统默认处理再切一次。
                    return true;
                }
            }
            // 其他媒体键交回 MediaSession 的默认 play/pause/seek 映射。
            return false;
        }

        @Override
        public ListenableFuture<SessionResult> onCustomCommand(
                MediaSession session,
                MediaSession.ControllerInfo controller,
                SessionCommand command,
                Bundle args) {
            if (CMD_SEEK_TO.equals(command.customAction)) {
                int index = args.getInt("index", 0);
                long positionMs = args.getLong("positionMs", 0);
                player.seekTo(index, positionMs);
                return success();
            }
            if (CMD_PROGRESS_CONTEXT.equals(command.customAction)) {
                double[] starts = args.getDoubleArray("chapterStartsSec");
                double[] ends = args.getDoubleArray("chapterEndsSec");
                if (starts != null) playbackChapterStartsSec = starts;
                if (ends != null) playbackChapterEndsSec = ends;
                if (progressReporter != null) {
                    progressReporter.setContext(
                            args.getLong("bookId", 0),
                            args.getString("baseUrl", ""),
                            args.getString("token", ""),
                            args.getString("deviceId", ""),
                            args.getBoolean("flushPending", false));
                }
                return success();
            }
            if (CMD_PROGRESS_TOKEN.equals(command.customAction)) {
                if (progressReporter != null) {
                    progressReporter.setToken(args.getString("token", ""));
                }
                return success();
            }
            if (CMD_SLEEP_TIMER.equals(command.customAction)) {
                configureSleepTimer(args);
                return success();
            }
            if (CMD_SLEEP_TIMER_CLEAR.equals(command.customAction)) {
                clearSleepTimer(true);
                return success();
            }
            if (CMD_NEXT_UNIT.equals(command.customAction)) {
                seekNextUnit();
                return success();
            }
            if (CMD_PREV_UNIT.equals(command.customAction)) {
                seekPreviousUnit();
                return success();
            }
            return Futures.immediateFuture(
                    new SessionResult(SessionResult.RESULT_ERROR_NOT_SUPPORTED));
        }
    }

    /** 从网页接收定时配置；实际倒计时和暂停都由前台服务执行。 */
    private void configureSleepTimer(Bundle args) {
        clearSleepTimer(true);
        sleepBaseVolume = player != null ? player.getVolume() : 1f;

        String mode = args.getString("mode", "off");
        if (!"duration".equals(mode) && !"chapters".equals(mode)) {
            publishSleepState();
            return;
        }

        sleepMode = mode;
        sleepRemainingMs = Math.max(0, args.getLong("durationMs", 0));
        sleepChaptersLeft = Math.max(0, args.getInt("chaptersLeft", 0));
        sleepFinishChapter = args.getBoolean("finishChapter", false);
        double[] ends = args.getDoubleArray("chapterEndsSec");
        if (ends == null || ends.length == 0) ends = playbackChapterEndsSec;
        sleepChapterEndsSec = ends == null ? new double[0] : ends;
        sleepWaitingChapterEnd = false;
        sleepStopAtSec = -1;
        sleepUnitMark = currentUnitIndex();
        sleepLastTickElapsed = SystemClock.elapsedRealtime();
        sleepTimerRunning = true;
        publishSleepState();
        sleepHandler.removeCallbacks(sleepTicker);
        sleepHandler.postDelayed(sleepTicker, 1000);
    }

    private void clearSleepTimer(boolean restoreVolume) {
        sleepHandler.removeCallbacks(sleepTicker);
        if (restoreVolume) restoreSleepVolume();
        sleepTimerRunning = false;
        sleepMode = "off";
        sleepRemainingMs = 0;
        sleepChaptersLeft = 0;
        sleepFinishChapter = false;
        sleepWaitingChapterEnd = false;
        sleepStopAtSec = -1;
        sleepUnitMark = 0;
        sleepChapterEndsSec = new double[0];
        publishSleepState();
    }

    private void restoreSleepVolume() {
        // 没有活跃定时器时不要动用户自己设置的音量。
        if (sleepTimerRunning && player != null) {
            player.setVolume(Math.max(0f, Math.min(1f, sleepBaseVolume)));
        }
    }

    private boolean tickSleepTimer() {
        if (!sleepTimerRunning || player == null) return false;
        long now = SystemClock.elapsedRealtime();
        long deltaMs = Math.max(0, now - sleepLastTickElapsed);
        sleepLastTickElapsed = now;
        // 暂停时不计时，和 Web 端「定时也会暂停」保持一致。
        if (deltaMs <= 0 || !player.isPlaying()) return true;

        if ("duration".equals(sleepMode) && !sleepWaitingChapterEnd) {
            sleepRemainingMs -= deltaMs;
            if (sleepRemainingMs > 0 && sleepRemainingMs <= SLEEP_FADE_MS) {
                float ratio = Math.max(0f, (float) sleepRemainingMs / SLEEP_FADE_MS);
                player.setVolume(Math.max(0f, Math.min(1f, sleepBaseVolume * ratio)));
            }
            if (sleepRemainingMs <= 0) {
                sleepRemainingMs = 0;
                if (sleepFinishChapter) {
                    sleepWaitingChapterEnd = true;
                    sleepStopAtSec = nextUnitEndSec();
                } else {
                    pauseForSleep();
                    return false;
                }
            }
        }

        if (sleepWaitingChapterEnd) {
            double position = currentAbsolutePositionSec();
            if (sleepStopAtSec <= 0 || position >= sleepStopAtSec - 0.2) {
                pauseForSleep();
                return false;
            }
        } else if ("chapters".equals(sleepMode)) {
            int unitIndex = currentUnitIndex();
            if (unitIndex > sleepUnitMark) {
                sleepChaptersLeft -= unitIndex - sleepUnitMark;
                sleepUnitMark = unitIndex;
                if (sleepChaptersLeft <= 0) {
                    pauseForSleep();
                    return false;
                }
            } else if (unitIndex < sleepUnitMark) {
                // 用户手动回退时不累计已播集数。
                sleepUnitMark = unitIndex;
            }
        }
        return true;
    }

    private void pauseForSleep() {
        if (player != null) player.pause();
        clearSleepTimer(true);
    }

    private double currentAbsolutePositionSec() {
        if (player == null) return 0;
        MediaItem item = player.getCurrentMediaItem();
        if (item == null) return 0;
        Bundle extras = item.mediaMetadata.extras;
        double offsetSec = extras == null ? 0 : extras.getDouble("offsetSec", 0);
        double clipStartSec = extras == null ? 0 : extras.getDouble("clipStartSec", 0);
        long positionMs = player.getCurrentPosition();
        if (positionMs < 0) positionMs = 0;
        return offsetSec + clipStartSec + positionMs / 1000.0;
    }

    private int currentUnitIndex() {
        if (sleepChapterEndsSec.length > 0) {
            double position = currentAbsolutePositionSec();
            int index = 0;
            while (index < sleepChapterEndsSec.length
                    && position >= sleepChapterEndsSec[index] - 0.2) {
                index++;
            }
            return Math.min(index, sleepChapterEndsSec.length - 1);
        }
        return player == null ? 0 : Math.max(0, player.getCurrentMediaItemIndex());
    }

    private double nextUnitEndSec() {
        double position = currentAbsolutePositionSec();
        if (sleepChapterEndsSec.length > 0) {
            for (double endSec : sleepChapterEndsSec) {
                if (endSec > position + 0.2) return endSec;
            }
            return sleepChapterEndsSec[sleepChapterEndsSec.length - 1];
        }
        if (player != null) {
            MediaItem item = player.getCurrentMediaItem();
            Bundle extras = item == null ? null : item.mediaMetadata.extras;
            if (extras != null) {
                double clipEndSec = extras.getDouble("clipEndSec", 0);
                double fullEndSec = extras.getDouble("durationSec", 0);
                double endSec = extras.getDouble("offsetSec", 0)
                        + (clipEndSec > 0 ? clipEndSec : fullEndSec);
                if (endSec > position + 0.2) return endSec;
            }
        }
        return position + 10;
    }

    /** 通过 session extras 把原生定时器状态交给 WebView，熄屏后恢复页面也能同步显示。 */
    private void publishSleepState() {
        if (session == null) return;
        try {
            JSONObject state = new JSONObject();
            state.put("mode", sleepMode);
            state.put("remainingSec", sleepTimerRunning
                    ? (int) Math.ceil(Math.max(0, sleepRemainingMs) / 1000.0)
                    : 0);
            state.put("chaptersLeft", Math.max(0, sleepChaptersLeft));
            state.put("finishChapter", sleepFinishChapter);
            state.put("waitingChapterEnd", sleepWaitingChapterEnd);
            Bundle extras = new Bundle();
            extras.putString(EXTRA_SLEEP_TIMER, state.toString());
            session.setSessionExtras(extras);
        } catch (JSONException ignored) {
        }
    }

    private static ListenableFuture<SessionResult> success() {
        return Futures.immediateFuture(new SessionResult(SessionResult.RESULT_SUCCESS));
    }

    /** 单文件多章节时按章节起点跳；多文件且无章节时才切 MediaItem。 */
    private void seekNextUnit() {
        if (player == null) return;
        if (playbackChapterStartsSec.length > 0) {
            double position = currentAbsolutePositionSec();
            for (double startSec : playbackChapterStartsSec) {
                if (startSec > position + 0.2) {
                    seekToAbsoluteSec(startSec);
                    return;
                }
            }
            return;
        }
        player.seekToNextMediaItem();
    }

    private void seekPreviousUnit() {
        if (player == null) return;
        double position = currentAbsolutePositionSec();
        if (playbackChapterStartsSec.length > 0) {
            int index = currentChapterIndex(position);
            double currentStart = playbackChapterStartsSec[index];
            if (position - currentStart > 5) {
                seekToAbsoluteSec(currentStart);
            } else if (index > 0) {
                seekToAbsoluteSec(playbackChapterStartsSec[index - 1]);
            } else {
                seekToAbsoluteSec(currentStart);
            }
            return;
        }
        int index = player.getCurrentMediaItemIndex();
        if (index < 0) return;
        if (position - currentMediaItemStartSec() > 5) {
            player.seekTo(index, 0);
        } else {
            player.seekToPreviousMediaItem();
        }
    }

    private int currentChapterIndex(double positionSec) {
        int index = 0;
        for (int i = 0; i < playbackChapterStartsSec.length; i++) {
            if (playbackChapterStartsSec[i] <= positionSec + 0.01) index = i;
            else break;
        }
        return index;
    }

    private double currentMediaItemStartSec() {
        MediaItem item = player == null ? null : player.getCurrentMediaItem();
        Bundle extras = item == null ? null : item.mediaMetadata.extras;
        if (extras == null) return 0;
        return extras.getDouble("offsetSec", 0) + extras.getDouble("clipStartSec", 0);
    }

    private void seekToAbsoluteSec(double absoluteSec) {
        if (player == null) return;
        int count = player.getMediaItemCount();
        for (int i = 0; i < count; i++) {
            MediaItem item = player.getMediaItemAt(i);
            Bundle extras = item.mediaMetadata.extras;
            if (extras == null) continue;
            double offsetSec = extras.getDouble("offsetSec", 0);
            double clipStartSec = extras.getDouble("clipStartSec", 0);
            double clipEndSec = extras.getDouble("clipEndSec", 0);
            double fullDurationSec = extras.getDouble("durationSec", 0);
            double startSec = offsetSec + clipStartSec;
            double endSec = offsetSec
                    + (clipEndSec > 0 ? clipEndSec : fullDurationSec);
            if (absoluteSec < endSec - 0.01 || i == count - 1) {
                long positionMs = Math.max(0, Math.round((absoluteSec - startSec) * 1000));
                player.seekTo(i, positionMs);
                return;
            }
        }
    }

    @Override
    public MediaSession onGetSession(MediaSession.ControllerInfo controllerInfo) {
        return session;
    }

    @Override
    public void onTaskRemoved(Intent rootIntent) {
        // 从最近任务划掉后继续播放，不要 stopSelf；但先把当前位置落一次本地并上报。
        if (progressReporter != null) {
            progressReporter.reportNow(false);
        }
    }

    @Override
    public void onDestroy() {
        clearSleepTimer(false);
        if (progressReporter != null) {
            progressReporter.reportNow(false);
            progressReporter.shutdown();
            progressReporter = null;
        }
        if (session != null) {
            session.release();
            session = null;
        }
        if (player != null) {
            player.release();
            player = null;
        }
        super.onDestroy();
    }
}
