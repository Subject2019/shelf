import type { Chapter } from "../../api/types";
import { Icon } from "../ui/Icon";
import PlayerLibraryPanel from "./PlayerLibraryPanel";

interface PlayerPanelProps {
  open: boolean;
  bookId: number;
  bookTitle: string;
  chapters: Chapter[];
  currentIndex: number;
  positionSec: number;
  onSeek: (positionSec: number) => void;
  onAddBookmark: (note: string | null) => void;
  onClose: () => void;
}

/** 右侧抽屉：内容与 /player 右栏共用 PlayerLibraryPanel。 */
export default function PlayerPanel({
  open,
  bookId,
  bookTitle,
  chapters,
  currentIndex,
  positionSec,
  onSeek,
  onAddBookmark,
  onClose,
}: PlayerPanelProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="关闭面板"
        onClick={onClose}
        className="absolute inset-0 bg-black/40"
      />

      <aside
        className="glass-panel relative flex h-full w-full max-w-sm flex-col border-l border-white/60 shadow-2xl dark:border-white/10"
        style={{ paddingTop: "var(--sat, env(safe-area-inset-top))" }}
      >
        <header className="flex items-center justify-between gap-3 px-4 pb-2 pt-3">
          <h2 className="truncate text-sm font-semibold" title={bookTitle}>
            {bookTitle}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="flex size-8 items-center justify-center rounded-full text-zinc-500 transition hover:bg-zinc-100 dark:hover:bg-white/10"
          >
            <Icon name="close" className="size-4" />
          </button>
        </header>

        <div className="min-h-0 flex-1">
          <PlayerLibraryPanel
            bookId={bookId}
            chapters={chapters}
            currentIndex={currentIndex}
            positionSec={positionSec}
            onSeek={onSeek}
            onAddBookmark={onAddBookmark}
            onNavigate={onClose}
          />
        </div>
      </aside>
    </div>
  );
}
