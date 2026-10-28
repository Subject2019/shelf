package com.echoshelf.app.player

import android.content.ComponentName
import android.content.Context
import androidx.core.content.ContextCompat
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.echoshelf.app.AppGraph
import com.echoshelf.app.data.BookDetail
import com.echoshelf.app.data.Chapter
import com.echoshelf.app.data.Track
import android.net.Uri
import com.google.common.util.concurrent.MoreExecutors
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class PlayerState(
    val connected: Boolean = false,
    val playing: Boolean = false,
    val bookId: Int? = null,
    val title: String = "",
    val subtitle: String = "",
    val positionSec: Double = 0.0,
    val durationSec: Double = 0.0,
    val rate: Float = 1f,
    val buffering: Boolean = false,
    val coverUrl: String? = null,
)

class PlayerController(
    private val context: Context,
    private val graph: AppGraph,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var controller: MediaController? = null
    private var detail: BookDetail? = null
    private var trackOffsets: Map<Int, Double> = emptyMap()
    private var currentTrackId: Int? = null
    private var lastReportAt = 0L

    private val _state = MutableStateFlow(PlayerState())
    val state: StateFlow<PlayerState> = _state.asStateFlow()

    private val listener = object : Player.Listener {
        override fun onIsPlayingChanged(isPlaying: Boolean) {
            refresh()
            // 暂停/停止时立刻落一次进度，别等 15 秒节流
            if (!isPlaying) reportProgress()
        }
        override fun onPlaybackStateChanged(playbackState: Int) {
            refresh()
            if (playbackState == Player.STATE_ENDED) {
                reportProgress(finished = true)
            }
        }

        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) = refresh()
    }

    init {
        val token = SessionToken(context, ComponentName(context, PlaybackService::class.java))
        val future = MediaController.Builder(context, token).buildAsync()
        future.addListener({
            controller = future.get().also { it.addListener(listener) }
            refresh()
        }, MoreExecutors.directExecutor())

        scope.launch {
            while (true) {
                delay(1_000)
                tick()
            }
        }
    }

    private fun tick() {
        val player = controller ?: return
        if (detail == null) return
        refreshPosition()
        val now = System.currentTimeMillis()
        if (player.isPlaying && now - lastReportAt >= 15_000) {
            reportProgress()
        }
    }

    private fun refresh() {
        val player = controller ?: return
        _state.value = _state.value.copy(
            connected = true,
            playing = player.isPlaying,
            durationSec = if (player.duration > 0) player.duration / 1000.0 else _state.value.durationSec,
            rate = player.playbackParameters.speed,
            buffering = player.playbackState == Player.STATE_BUFFERING,
        )
        refreshPosition()
    }

    private fun refreshPosition() {
        val player = controller ?: return
        val offset = trackOffsets[currentTrackId] ?: 0.0
        val position = offset + (player.currentPosition.coerceAtLeast(0) / 1000.0)
        _state.value = _state.value.copy(positionSec = position)
    }

    /** 播放一本书：从 [startSec]（全书绝对秒）开始；[fromBeginning] 时从 0 开始。 */
    suspend fun play(book: BookDetail, startSec: Double, fromBeginning: Boolean = false) {
        val player = controller ?: return
        detail = book
        trackOffsets = offsetsOf(book)
        val target = if (fromBeginning) 0.0 else startSec.coerceIn(0.0, book.totalDurationSec)
        val chapter = chapterAt(book, target)
        val track = trackFor(book, target, chapter) ?: return
        currentTrackId = track.id
        val offset = trackOffsets[track.id] ?: 0.0

        val streamUrl = graph.auth.absoluteUrl(track.streamUrl) ?: return
        val uri = streamUrl
        val artwork = graph.auth.absoluteUrl(book.coverUrl)
        _state.value = _state.value.copy(
            bookId = book.id,
            title = chapter?.title ?: track.title.ifBlank { book.title },
            subtitle = book.title,
            coverUrl = artwork,
        )

        val metadata = MediaMetadata.Builder()
            .setTitle(chapter?.title ?: track.title.ifBlank { book.title })
            .setArtist(book.title)
            .setAlbumTitle(book.title)
            .setArtworkUri(artwork?.let { android.net.Uri.parse(it) })
            .build()

        val item = MediaItem.Builder()
            .setUri(uri)
            .setMediaId(book.id.toString())
            .setMediaMetadata(metadata)
            .build()

        player.setMediaItem(item)
        player.prepare()
        player.seekTo(((target - offset).coerceAtLeast(0.0) * 1000).toLong())
        player.play()
        lastReportAt = System.currentTimeMillis()
        refresh()
    }

    fun toggle() {
        controller?.let { if (it.isPlaying) it.pause() else it.play() }
    }

    fun seekTo(absoluteSec: Double) {
        val player = controller ?: return
        val offset = trackOffsets[currentTrackId] ?: 0.0
        val position = (absoluteSec - offset).coerceAtLeast(0.0)
        player.seekTo((position * 1000).toLong())
        reportProgress(explicitSeek = true)
    }

    fun skip(deltaSec: Double) {
        seekTo((_state.value.positionSec + deltaSec).coerceIn(0.0, _state.value.durationSec.takeIf { it > 0 } ?: Double.MAX_VALUE))
    }

    fun setRate(rate: Float) {
        controller?.setPlaybackSpeed(rate)
        _state.value = _state.value.copy(rate = rate)
    }

    fun pause() = controller?.pause()

    fun reportProgress(finished: Boolean = false, explicitSeek: Boolean = false) {
        val book = detail ?: return
        val player = controller ?: return
        val offset = trackOffsets[currentTrackId] ?: 0.0
        val position = offset + (player.currentPosition.coerceAtLeast(0) / 1000.0)
        val rate = player.playbackParameters.speed.toDouble()
        lastReportAt = System.currentTimeMillis()
        scope.launch(Dispatchers.IO) {
            runCatching {
                graph.putProgress(
                    bookId = book.id,
                    positionSec = position,
                    rate = rate,
                    finished = finished,
                    explicitSeek = explicitSeek,
                    trackId = currentTrackId,
                )
            }
        }
    }

    private fun offsetsOf(book: BookDetail): Map<Int, Double> {
        val result = mutableMapOf<Int, Double>()
        var sum = 0.0
        book.tracks.sortedBy { it.trackNo }.forEach { track ->
            result[track.id] = sum
            sum += track.durationSec
        }
        return result
    }

    private fun chapterAt(book: BookDetail, positionSec: Double): Chapter? =
        book.chapters.firstOrNull { positionSec >= it.startSec && positionSec < it.endSec }

    private fun trackFor(book: BookDetail, positionSec: Double, chapter: Chapter?): Track? {
        if (chapter != null) {
            return book.tracks.firstOrNull { it.id == chapter.trackId }
        }
        val sorted = book.tracks.sortedBy { it.trackNo }
        var sum = 0.0
        for (track in sorted) {
            if (positionSec < sum + track.durationSec) return track
            sum += track.durationSec
        }
        return sorted.lastOrNull()
    }
}
