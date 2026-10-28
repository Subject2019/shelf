import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { api } from "../../api/endpoints";
import type { BookmarkCreate } from "../../api/types";
import { formatClock } from "../../lib/format";
import { RATES } from "../../lib/playback";
import { bindAudioElement, chapterIndexAt, usePlayer } from "../../store/player";
import Cover from "../ui/Cover";
import { Icon } from "../ui/Icon";
import FullPlayer from "./FullPlayer";
import PlayerPanel from "./PlayerPanel";
import SleepTimer from "./SleepTimer";


const iconButton =
  "flex size-9 items-center justify-center rounded-full text-zinc-600 transition hover:bg-zinc-100 hover:text-zinc-900 disabled:opacity-30 dark:text-zinc-300 dark:hover:bg-white/10 dark:hover:text-zinc-50";

export default function PlayerBar() {
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const book = usePlayer((state) => state.book);
  const tracks = usePlayer((state) => state.tracks);
  const trackId = usePlayer((state) => state.trackId);
  const isPlaying = usePlayer((state) => state.isPlaying);
  const isLoading = usePlayer((state) => state.isLoading);
  const positionSec = usePlayer((state) => state.positionSec);
  const durationSec = usePlayer((state) => state.durationSec);
  const rate = usePlayer((state) => state.rate);
  const volume = usePlayer((state) => state.volume);
  const muted = usePlayer((state) => state.muted);
  const error = usePlayer((state) => state.error);

  const location = useLocation();
  const navigate = useNavigate();
  // /player 页已有完整控件，这里只隐藏外壳，<audio> 必须留在 DOM 里
  const onPlayerPage = location.pathname === "/player";

  const [scrub, setScrub] = useState<number | null>(null);
  const [rateOpen, setRateOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [fullOpen, setFullOpen] = useState(false);
  const [bookmarkAdded, setBookmarkAdded] = useState(false);
  const queryClient = useQueryClient();

  const addBookmark = useMutation({
    mutationFn: (payload: BookmarkCreate) => {
      if (!book) throw new Error("没有正在播放的书");
      return api.createBookmark(book.id, payload);
    },
    onSuccess: () => {
      setBookmarkAdded(true);
      window.setTimeout(() => setBookmarkAdded(false), 1600);
      void queryClient.invalidateQueries({ queryKey: ["bookmarks", book?.id] });
    },
  });

  useEffect(() => {
    bindAudioElement(audioRef.current);
    // 关闭/刷新页面前补一次进度，keepalive 保证请求发出
    const flush = () => usePlayer.getState().reportProgress(false, true);
    window.addEventListener("beforeunload", flush);
    return () => window.removeEventListener("beforeunload", flush);
  }, []);

  const track = tracks.find((item) => item.id === trackId) ?? null;
  const index = tracks.findIndex((item) => item.id === trackId);
  const shown = scrub ?? positionSec;
  const percent = durationSec > 0 ? Math.min(100, (shown / durationSec) * 100) : 0;

  const chapters = book?.chapters ?? [];
  const hasChapters = chapters.length > 0;
  const chapterIndex = hasChapters ? chapterIndexAt(chapters, shown) : 0;
  const currentChapter = chapters[chapterIndex] ?? null;

  const hasPrev = hasChapters ? chapterIndex > 0 : index > 0;
  const hasNext = hasChapters
    ? chapterIndex < chapters.length - 1
    : index >= 0 && index < tracks.length - 1;

  function commitScrub() {
    if (scrub === null) return;
    usePlayer.getState().seekWithUndo(scrub);
    setScrub(null);
  }

  function createBookmark(note: string | null) {
    addBookmark.mutate({
      position_sec: Number(positionSec.toFixed(1)),
      track_id: trackId,
      note: note ?? currentChapter?.title ?? null,
    });
  }

  return (
    <>
      <audio ref={audioRef} preload="metadata" className="hidden" />

      {book && (
        <div
          className={[
            "fixed inset-x-0 bottom-[calc(3.5rem_+_var(--sb,0px))] z-30 lg:bottom-0 lg:left-60",
            onPlayerPage ? "hidden" : "",
          ].join(" ")}
        >
          <div className="glass-bar border-t shadow-[0_-12px_34px_-20px_rgba(8,10,14,0.45)] dark:shadow-[0_-12px_34px_-12px_rgba(0,0,0,0.7)]">
            <div className="mx-auto max-w-[1440px]">
              <div className="relative">
                <input
                  type="range"
                  min={0}
                  max={Math.max(1, Math.floor(durationSec))}
                  step={1}
                  value={Math.min(Math.floor(shown), Math.max(1, Math.floor(durationSec)))}
                  onChange={(event) => setScrub(Number(event.target.value))}
                  onPointerUp={commitScrub}
                  onTouchEnd={commitScrub}
                  onKeyUp={commitScrub}
                  onBlur={commitScrub}
                  aria-label="播放进度"
                  style={{ "--progress": `${percent}%` } as CSSProperties}
                  className="player-range block w-full"
                />
                {isPlaying && percent > 2 && (
                  <span
                    aria-hidden
                    className="pointer-events-none absolute inset-y-0 left-0 flex items-center overflow-hidden rounded-full"
                    style={{ width: `${percent}%` }}
                  >
                    <span className="progress-shine block h-[3px] w-full rounded-full" />
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2 px-3 pb-2 pt-1 sm:gap-3 sm:px-4">
                <button
                  type="button"
                  onClick={() => {
                    // 非播放页点击封面 → 跳到 /player 路由；已在播放页则展开全屏播放器
                    if (onPlayerPage) setFullOpen(true);
                    else navigate("/player");
                  }}
                  aria-label="展开播放页"
                  className="size-10 shrink-0 overflow-hidden rounded-lg shadow-glow-sm ring-1 ring-white/15 transition hover:brightness-110"
                >
                  <Cover book={book} className="size-10" textClassName="text-base" />
                </button>

                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs font-medium sm:text-sm">
                    {book.title}
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-zinc-500">
                    <button
                      type="button"
                      onClick={() => hasChapters && setPanelOpen(true)}
                      disabled={!hasChapters}
                      className="flex min-w-0 items-center gap-1 text-left transition enabled:hover:text-brand-500"
                    >
                      <Icon name="list" className="size-3 shrink-0" />
                      <span className="truncate">
                        {currentChapter?.title ?? track?.title ?? `第 ${index + 1} 轨`}
                      </span>
                    </button>
                    <span className="hidden shrink-0 tabular-nums sm:inline">
                      {formatClock(shown)} / {formatClock(durationSec)}
                    </span>
                    {error && <span className="truncate text-amber-500">{error}</span>}
                  </div>
                </div>

                <div className="flex shrink-0 items-center gap-0.5 sm:gap-1">
                  <button
                    type="button"
                    onClick={() =>
                      hasChapters
                        ? usePlayer.getState().prevChapter()
                        : usePlayer.getState().prevTrack()
                    }
                    disabled={!hasPrev}
                    aria-label={hasChapters ? "上一章" : "上一轨"}
                    className={`${iconButton} hidden sm:flex`}
                  >
                    <Icon name="skipPrev" className="size-4" />
                  </button>

                  <button
                    type="button"
                    onClick={() => usePlayer.getState().skip(-15)}
                    aria-label="后退 15 秒"
                    className="hidden h-8 items-center rounded-full px-2 text-[11px] font-medium text-zinc-500 transition hover:bg-zinc-100 dark:hover:bg-white/10 sm:flex"
                  >
                    −15
                  </button>

                  <button
                    type="button"
                    onClick={() => usePlayer.getState().toggle()}
                    aria-label={isPlaying ? "暂停" : "播放"}
                    className="btn-gradient flex size-10 items-center justify-center rounded-full"
                  >
                    {isLoading ? (
                      <span className="size-4 animate-spin rounded-full border-2 border-ink-950/30 border-t-ink-950" />
                    ) : (
                      <Icon name={isPlaying ? "pause" : "play"} className="size-5" />
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => usePlayer.getState().skip(15)}
                    aria-label="前进 15 秒"
                    className="hidden h-8 items-center rounded-full px-2 text-[11px] font-medium text-zinc-500 transition hover:bg-zinc-100 dark:hover:bg-white/10 sm:flex"
                  >
                    +15
                  </button>

                  <button
                    type="button"
                    onClick={() =>
                      hasChapters
                        ? usePlayer.getState().nextChapter()
                        : usePlayer.getState().nextTrack()
                    }
                    disabled={!hasNext}
                    aria-label={hasChapters ? "下一章" : "下一轨"}
                    className={`${iconButton} hidden sm:flex`}
                  >
                    <Icon name="skipNext" className="size-4" />
                  </button>

                  <button
                    type="button"
                    onClick={() => setPanelOpen(true)}
                    aria-label="章节列表"
                    className={`${iconButton} hidden sm:flex`}
                  >
                    <Icon name="list" className="size-4" />
                  </button>

                  <button
                    type="button"
                    onClick={() => createBookmark(null)}
                    aria-label="添加书签"
                    className={`${iconButton} ${
                      bookmarkAdded ? "text-emerald-500 dark:text-emerald-400" : ""
                    }`}
                  >
                    <Icon
                      name={bookmarkAdded ? "check" : "bookmark"}
                      className="size-4"
                    />
                  </button>

                  <SleepTimer />

                  <div className="relative hidden sm:block">
                    <button
                      type="button"
                      onClick={() => setRateOpen((open) => !open)}
                      aria-label="播放速度"
                      className="h-8 rounded-full px-2 text-[11px] font-medium text-zinc-600 transition hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-white/10"
                    >
                      {rate}×
                    </button>
                    {rateOpen && (
                      <div className="absolute bottom-full right-0 mb-2 w-20 overflow-hidden rounded-xl border border-zinc-200 bg-white py-1 shadow-lg dark:border-white/10 dark:bg-ink-800">
                        {RATES.map((item) => (
                          <button
                            key={item}
                            type="button"
                            onClick={() => {
                              usePlayer.getState().setRate(item);
                              setRateOpen(false);
                            }}
                            className={[
                              "block w-full px-3 py-1.5 text-left text-xs transition hover:bg-zinc-100 dark:hover:bg-white/10",
                              item === rate
                                ? "font-semibold text-brand-500"
                                : "text-zinc-600 dark:text-zinc-300",
                            ].join(" ")}
                          >
                            {item}×
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="hidden items-center gap-1.5 lg:flex">
                    <button
                      type="button"
                      onClick={() => usePlayer.getState().toggleMute()}
                      aria-label={muted ? "取消静音" : "静音"}
                      className={iconButton}
                    >
                      <Icon
                        name={muted || volume === 0 ? "volumeMute" : "volume"}
                        className="size-4"
                      />
                    </button>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      value={muted ? 0 : volume}
                      onChange={(event) =>
                        usePlayer.getState().setVolume(Number(event.target.value))
                      }
                      aria-label="音量"
                      className="h-1 w-20 cursor-pointer accent-brand-500"
                    />
                  </div>

                  <button
                    type="button"
                    onClick={() => usePlayer.getState().close()}
                    aria-label="关闭播放器"
                    className={iconButton}
                  >
                    <Icon name="close" className="size-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {book && (
        <FullPlayer
          open={fullOpen}
          onClose={() => setFullOpen(false)}
          onOpenPanel={() => {
            setFullOpen(false);
            setPanelOpen(true);
          }}
          onAddBookmark={() => createBookmark(null)}
          bookmarkAdded={bookmarkAdded}
        />
      )}

      {book && (
        <PlayerPanel
          open={panelOpen}
          bookId={book.id}
          bookTitle={book.title}
          chapters={chapters}
          currentIndex={chapterIndex}
          positionSec={positionSec}
          onSeek={(value) => usePlayer.getState().seekTo(value)}
          onAddBookmark={(note) => createBookmark(note)}
          onClose={() => setPanelOpen(false)}
        />
      )}
    </>
  );
}
