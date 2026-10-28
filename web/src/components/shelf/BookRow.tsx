import { Link } from "react-router-dom";

import type { Book } from "../../api/types";
import { formatDuration } from "../../lib/format";
import { usePlayer } from "../../store/player";
import Cover from "../ui/Cover";
import { Icon } from "../ui/Icon";

interface BookRowProps {
  book: Book;
}

export default function BookRow({ book }: BookRowProps) {
  const percent = book.progress && !book.progress.is_finished ? book.progress.percent : 0;

  return (
    <article className="group relative flex items-center gap-3 rounded-card border border-white/70 bg-white/70 p-2.5 backdrop-blur-md transition hover:border-brand-500/40 hover:shadow-glow-sm dark:border-white/10 dark:bg-white/[0.045]">
      <Cover
        book={book}
        className="size-14 shrink-0 overflow-hidden rounded-lg"
        textClassName="text-lg"
      />

      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{book.title}</div>
        <div className="mt-0.5 truncate text-xs text-zinc-500">
          {book.author ?? "未知作者"} · {formatDuration(book.total_duration_sec)}
        </div>
        {percent > 0 && (
          <div className="mt-1.5 h-1 w-full max-w-56 overflow-hidden rounded-full bg-zinc-200 dark:bg-white/10">
            <div
              className="h-full rounded-full bg-brand-500"
              style={{ width: `${Math.min(100, percent)}%` }}
            />
          </div>
        )}
      </div>

      <span className="hidden shrink-0 text-xs text-zinc-500 sm:block">
        {book.track_count} 轨
      </span>

      <button
        type="button"
        onClick={() => void usePlayer.getState().open(book.id)}
        aria-label={`播放《${book.title}》`}
        className="relative z-20 flex size-8 shrink-0 items-center justify-center rounded-full text-zinc-400 transition hover:bg-brand-500/10 hover:text-brand-500"
      >
        <Icon name="play" className="size-4" />
      </button>

      <Link
        to={`/books/${book.id}`}
        aria-label={`查看《${book.title}》详情`}
        className="absolute inset-0 z-10 rounded-card"
      />
    </article>
  );
}
