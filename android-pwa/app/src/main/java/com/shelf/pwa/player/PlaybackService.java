package com.shelf.pwa.player;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;

import androidx.media3.common.AudioAttributes;
import androidx.media3.common.C;
import androidx.media3.common.ForwardingPlayer;
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

import java.util.ArrayList;
import java.util.List;

/**
 * 后台播放：MediaSessionService + ExoPlayer。
 * 系统媒体卡片由 media3 托管，这里做三件事：
 *   - 对外隐藏时长，去掉系统卡片的进度条；
 *   - 五个标准播放器动作：上一集、快退15、播放/暂停、快进15、下一集；
 *   - 保留封面（MediaMetadata 由 NativePlayer 写入）。
 *
 * 注意：这五个按钮必须用 playerCommand（而不是自定义 sessionCommand），
 * 否则系统会把它们归到“自定义动作”分组，导致和标准播放键之间出现大空隙。
 */
public class PlaybackService extends MediaSessionService {
    private static final String CMD_SEEK_TO = "com.shelf.pwa.SEEK_TO";
    private static final long SEEK_STEP_MS = 15_000;

    private ExoPlayer player;
    private Player sessionPlayer;
    private MediaSession session;

    @Override
    public void onCreate() {
        super.onCreate();
        setMediaNotificationProvider(new ShelfNotificationProvider(this));
        player = new ExoPlayer.Builder(this)
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

        // 只对系统会话隐藏时长；真实进度仍由 ExoPlayer / 网页各自维护。
        sessionPlayer = new NoDurationPlayer(player);

        PendingIntent sessionActivity = PendingIntent.getActivity(
                this,
                0,
                new Intent(this, MainActivity.class)
                        .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);

        session = new MediaSession.Builder(this, sessionPlayer)
                .setSessionActivity(sessionActivity)
                .setCallback(new SessionCallback())
                .setCustomLayout(buildButtons(false))
                .build();

        // 播放/暂停图标随状态切换；系统卡片和通知会一起刷新。
        player.addListener(new Player.Listener() {
            @Override
            public void onIsPlayingChanged(boolean isPlaying) {
                if (session != null) {
                    session.setCustomLayout(buildButtons(isPlaying));
                }
            }
        });
    }

    private List<CommandButton> buildButtons(boolean isPlaying) {
        List<CommandButton> buttons = new ArrayList<>();
        buttons.add(playerButton(
                "上一集", android.R.drawable.ic_media_previous,
                Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM, 0));
        buttons.add(playerButton(
                "后退15秒", android.R.drawable.ic_media_rew,
                Player.COMMAND_SEEK_BACK, -1));
        buttons.add(playPauseButton(isPlaying, 1));
        buttons.add(playerButton(
                "前进15秒", android.R.drawable.ic_media_ff,
                Player.COMMAND_SEEK_FORWARD, -1));
        buttons.add(playerButton(
                "下一集", android.R.drawable.ic_media_next,
                Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM, 2));
        return buttons;
    }

    private static CommandButton playerButton(
            String name, int iconResId, int playerCommand, int compactIndex) {
        return new CommandButton.Builder()
                .setDisplayName(name)
                .setIconResId(iconResId)
                .setPlayerCommand(playerCommand)
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
     * 系统媒体通知的按钮顺序：上一集、快退、播放/暂停、快进、下一集。
     * 全部是 playerCommand，系统按标准媒体动作等分排布。
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
                    playerButton(
                            "上一集", android.R.drawable.ic_media_previous,
                            Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM, 0),
                    playerButton(
                            "后退15秒", android.R.drawable.ic_media_rew,
                            Player.COMMAND_SEEK_BACK, -1),
                    playPauseButton(showPauseButton, 1),
                    playerButton(
                            "前进15秒", android.R.drawable.ic_media_ff,
                            Player.COMMAND_SEEK_FORWARD, -1),
                    playerButton(
                            "下一集", android.R.drawable.ic_media_next,
                            Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM, 2));
        }
    }

    private final class SessionCallback implements MediaSession.Callback {
        @Override
        public MediaSession.ConnectionResult onConnect(
                MediaSession session, MediaSession.ControllerInfo controller) {
            SessionCommands commands = new SessionCommands.Builder()
                    .add(new SessionCommand(CMD_SEEK_TO, Bundle.EMPTY))
                    .build();
            // 保留 session 的自定义布局和播放器命令；不要用 ConnectionResult.accept(...)。
            return new MediaSession.ConnectionResult.AcceptedResultBuilder(session)
                    .setAvailableSessionCommands(commands)
                    .build();
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
            return Futures.immediateFuture(
                    new SessionResult(SessionResult.RESULT_ERROR_NOT_SUPPORTED));
        }
    }

    private static ListenableFuture<SessionResult> success() {
        return Futures.immediateFuture(new SessionResult(SessionResult.RESULT_SUCCESS));
    }

    private static final class NoDurationPlayer extends ForwardingPlayer {
        NoDurationPlayer(Player player) {
            super(player);
        }

        @Override
        public long getDuration() {
            return C.TIME_UNSET;
        }

        @Override
        public Player.Commands getAvailableCommands() {
            // 只隐藏“当前项内 seek”，保留上一集/下一集/快退/快进等标准动作。
            return super.getAvailableCommands().buildUpon()
                    .removeAll(
                            Player.COMMAND_SEEK_TO_DEFAULT_POSITION,
                            Player.COMMAND_SEEK_IN_CURRENT_MEDIA_ITEM)
                    .build();
        }
    }

    @Override
    public MediaSession onGetSession(MediaSession.ControllerInfo controllerInfo) {
        return session;
    }

    @Override
    public void onTaskRemoved(Intent rootIntent) {
        // 从最近任务划掉后继续播放，不要 stopSelf
    }

    @Override
    public void onDestroy() {
        if (session != null) {
            session.release();
            session = null;
        }
        if (player != null) {
            player.release();
            player = null;
        }
        sessionPlayer = null;
        super.onDestroy();
    }
}
