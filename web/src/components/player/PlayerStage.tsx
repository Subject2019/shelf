import { useState, type CSSProperties } from "react";

import { formatClock } from "../../lib/format";
import {
  chapterIndexAt,
  currentPlaybackSegment,
  usePlayer,
} from "../../store/player";
import Cover from "../ui/Cover";
import { Icon } from "../ui/Icon";
import PlayerTools from "./PlayerTools";

/** 全屏播放页与 /player 共用的主体：封面、信息、进度、主控。 */
interface PlayerStageProps {
  compact?: boolean;
}

export default function PlayerStage({ compact = false }: PlayerStageProps) {
  const book = usePlayer((state) => state.book);
  const tracks = usePlayer((state) => state.tracks);
  const trackId = usePlayer((state) => state.trackId);
  const isPlaying = usePlayer((state) => state.isPlaying);
  const positionSec = usePlayer((state) => state.positionSec);
  const error = usePlayer((state) => state.error);

  const [scrub, setScrub] = useState<number | null>(null);

  if (!book) return null;

  const chapters = book.chapters ?? [];
  const chapterIndex = chapters.length > 0 ? chapterIndexAt(chapters, positionSec) : 0;
  const currentChapter = chapters[chapterIndex] ?? null;
  const trackIndex = tracks.findIndex((item) => item.id === trackId);
  const hasPrev =
    chapters.length > 0 ? chapterIndex > 0 : trackIndex > 0;
  const hasNext =
    chapters.length > 0
      ? chapterIndex < chapters.length - 1
      : trackIndex >= 0 && trackIndex < tracks.length - 1;

  const track = tracks.find((item) => item.id === trackId) ?? null;
  const segment = currentPlaybackSegment(book, tracks, trackId, positionSec);
  const segmentDuration = segment?.durationSec ?? 0;
  const segmentPosition = segment
    ? Math.max(0, Math.min(segmentDuration, positionSec - segment.startSec))
    : 0;
  const shown = scrub ?? segmentPosition;
  const percent =
    segmentDuration > 0 ? Math.min(100, (shown / segmentDuration) * 100) : 0;

  function commitScrub() {
    if (scrub === null || !segment) return;
    usePlayer.getState().seekWithUndo(segment.startSec + scrub);
    setScrub(null);
  }

  return (
    <div className="flex flex-col items-center">
      <Cover
        book={book}
        size="full"
        className={[
          "aspect-square w-full overflow-hidden rounded-[28px] shadow-glow-lg ring-1 ring-white/15",
          compact ? "max-w-[200px]" : "max-w-[240px]",
        ].join(" ")}
        textClassName={compact ? "text-5xl" : "text-6xl"}
      />

      <h1 className="mt-6 line-clamp-2 max-w-full text-center text-lg font-semibold leading-6">
        {book.title}
      </h1>
      <p className="mt-1 text-sm text-zinc-500">{book.author ?? "未知作者"}</p>
      <p className="mt-3 max-w-full truncate text-xs text-brand-500">
        {segment?.title ?? currentChapter?.title ?? track?.title ?? ""}
      </p>
      {error && <p className="mt-2 text-[11px] text-amber-500">{error}</p>}

      <div className="mt-6 w-full">
        <div className="relative">
          <input
            type="range"
            min={0}
            max={Math.max(1, Math.floor(segmentDuration))}
            step={1}
            value={Math.min(
              Math.floor(shown),
              Math.max(1, Math.floor(segmentDuration)),
            )}
            onChange={(event) => setScrub(Number(event.target.value))}
            onPointerUp={commitScrub}
            onTouchEnd={commitScrub}
            onKeyUp={commitScrub}
            onBlur={commitScrub}
            aria-label="当前单集播放进度"
            style={{ "--progress": `${percent}%` } as CSSProperties}
            className="player-range player-range--always block w-full"
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

        <div className="mt-1.5 flex justify-between text-[11px] tabular-nums text-zinc-500">
          <span>{formatClock(shown)}</span>
          <span>-{formatClock(Math.max(0, segmentDuration - shown))}</span>
        </div>
      </div>

      <div className="mt-5 flex w-full items-center justify-between">
        <button
          type="button"
          onClick={() => usePlayer.getState().prevChapter()}
          disabled={!hasPrev}
          aria-label="上一章"
          className="flex size-11 items-center justify-center rounded-full text-zinc-600 transition hover:bg-zinc-100 disabled:opacity-30 dark:text-zinc-300 dark:hover:bg-white/10"
        >
          <Icon name="skipPrev" className="size-5" />
        </button>

        <button
          type="button"
          onClick={() => usePlayer.getState().skip(-15)}
          aria-label="后退 15 秒"
          className="relative flex size-12 items-center justify-center rounded-full text-zinc-600 transition hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-white/10"
        >
          <Icon name="refresh" className="size-6 -scale-x-100" />
          <span className="absolute text-[9px] font-semibold">15</span>
        </button>

        <button
          type="button"
          onClick={() => usePlayer.getState().toggle()}
          aria-label={isPlaying ? "暂停" : "播放"}
          className="btn-gradient flex size-16 items-center justify-center rounded-full shadow-glow"
        >
          <Icon name={isPlaying ? "pause" : "play"} className="size-7" />
        </button>

        <button
          type="button"
          onClick={() => usePlayer.getState().skip(15)}
          aria-label="前进 15 秒"
          className="relative flex size-12 items-center justify-center rounded-full text-zinc-600 transition hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-white/10"
        >
          <Icon name="refresh" className="size-6" />
          <span className="absolute text-[9px] font-semibold">15</span>
        </button>

        <button
          type="button"
          onClick={() => usePlayer.getState().nextChapter()}
          disabled={!hasNext}
          aria-label="下一章"
          className="flex size-11 items-center justify-center rounded-full text-zinc-600 transition hover:bg-zinc-100 disabled:opacity-30 dark:text-zinc-300 dark:hover:bg-white/10"
        >
          <Icon name="skipNext" className="size-5" />
        </button>
      </div>

      <PlayerTools />
    </div>
  );
}
