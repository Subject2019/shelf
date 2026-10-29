import { chapterIndexAt, usePlayer } from "../../store/player";
import { Icon } from "../ui/Icon";
import PlayerStage from "./PlayerStage";

const RATES = [0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3];

interface FullPlayerProps {
  open: boolean;
  onClose: () => void;
  onOpenPanel: () => void;
  onAddBookmark: () => void;
  bookmarkAdded: boolean;
}

export default function FullPlayer({
  open,
  onClose,
  onOpenPanel,
  onAddBookmark,
  bookmarkAdded,
}: FullPlayerProps) {
  const book = usePlayer((state) => state.book);
  const tracks = usePlayer((state) => state.tracks);
  const trackId = usePlayer((state) => state.trackId);
  const positionSec = usePlayer((state) => state.positionSec);
  const rate = usePlayer((state) => state.rate);

  if (!open || !book) return null;

  const chapters = book.chapters ?? [];
  const chapterIndex =
    chapters.length > 0 ? chapterIndexAt(chapters, positionSec) : 0;
  const trackIndex = tracks.findIndex((track) => track.id === trackId);

  function cycleRate() {
    const index = RATES.indexOf(rate);
    usePlayer.getState().setRate(RATES[(index + 1) % RATES.length] ?? 1);
  }

  return (
    <div className="fixed inset-0 z-40 flex flex-col overflow-hidden bg-gradient-to-b from-white via-white to-zinc-100 dark:from-ink-900 dark:via-ink-950 dark:to-black">
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 size-[28rem] -translate-x-1/2 rounded-full bg-brand-500/20 blur-[110px] dark:bg-brand-500/25"
      />

      <header className="relative flex items-center justify-between px-4 pt-4">
        <button
          type="button"
          onClick={onClose}
          aria-label="收起播放页"
          className="flex size-9 items-center justify-center rounded-full text-zinc-500 transition hover:bg-zinc-100 dark:hover:bg-white/10"
        >
          <Icon name="chevronDown" className="size-5" />
        </button>

        <div className="text-center">
          <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">
            正在播放
          </p>
          <p className="mt-0.5 text-xs text-zinc-500">
            {chapters.length > 0
              ? `第 ${chapterIndex + 1} / ${chapters.length} 章`
              : tracks.length > 1
                ? `第 ${Math.max(1, trackIndex + 1)} / ${tracks.length} 集`
                : "单轨音频"}
          </p>
        </div>

        <button
          type="button"
          onClick={onOpenPanel}
          aria-label="章节目录"
          className="flex size-9 items-center justify-center rounded-full text-zinc-500 transition hover:bg-zinc-100 dark:hover:bg-white/10"
        >
          <Icon name="list" className="size-5" />
        </button>
      </header>

      <div className="relative flex flex-1 flex-col justify-center px-6">
        <PlayerStage />
      </div>

      <div className="relative px-6 pb-[calc(1.25rem+env(safe-area-inset-bottom))]">
        <div className="flex items-center justify-center gap-8 text-[11px] text-zinc-500">
          <button
            type="button"
            onClick={onAddBookmark}
            className={`flex flex-col items-center gap-1 transition ${
              bookmarkAdded ? "text-emerald-500" : "hover:text-brand-500"
            }`}
          >
            <Icon
              name={bookmarkAdded ? "check" : "bookmark"}
              className="size-4"
            />
            书签
          </button>

          <button
            type="button"
            onClick={cycleRate}
            className="flex flex-col items-center gap-1 transition hover:text-brand-500"
          >
            <span className="text-[13px] font-semibold leading-4">{rate}×</span>
            倍速
          </button>

          <button
            type="button"
            onClick={() => usePlayer.getState().close()}
            className="flex flex-col items-center gap-1 transition hover:text-rose-500"
          >
            <Icon name="close" className="size-4" />
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
