import { Link } from "react-router-dom";

import type { Book } from "../../api/types";
import { formatDuration } from "../../lib/format";
import { usePlayer } from "../../store/player";
import Cover from "../ui/Cover";
import { Icon } from "../ui/Icon";

interface BookCardProps {
  book: Book;
}

export default function BookCard({ book }: BookCardProps) {
  const percent = book.progress && !book.progress.is_finished ? book.progress.percent : 0;

  return (
    <article className="group relative flex h-full flex-col overflow-hidden rounded-card border border-white/70 bg-white/70 backdrop-blur-md transition duration-300 hover:-translate-y-1 hover:border-brand-500/40 hover:shadow-glow dark:border-white/10 dark:bg-white/[0.045]">
      <div className="relative aspect-square w-full">
        <Cover
          book={book}
          className="absolute inset-0 size-full"
          textClassName="text-4xl drop-shadow-sm"
        />
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/15 via-transparent to-black/25"
        />
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 z-10 overflow-hidden opacity-0 transition-opacity duration-200 group-hover:opacity-100"
        >
          <span className="card-sweep absolute inset-y-0 -left-1/3 w-1/3 bg-gradient-to-r from-transparent via-white/35 to-transparent" />
        </span>

        {book.hidden && (
          <span className="absolute left-2 top-2 z-20 rounded-full bg-black/70 px-2 py-0.5 text-[10px] font-medium text-white backdrop-blur">
            已隐藏
          </span>
        )}

        <button
          type="button"
          onClick={() => void usePlayer.getState().open(book.id)}
          aria-label={`播放《${book.title}》`}
          className="absolute inset-0 z-20 flex items-center justify-center bg-card-fade opacity-0 transition duration-300 group-hover:opacity-100 focus-visible:opacity-100"
        >
          <span className="btn-gradient flex size-12 items-center justify-center rounded-full">
            <Icon name="play" className="size-5 translate-x-0.5" />
          </span>
        </button>

        {percent > 0 && (
          <div className="absolute inset-x-0 bottom-0 z-30 h-1 bg-black/40">
            <div
              className="h-full bg-brand-gradient"
              style={{ width: `${Math.min(100, percent)}%` }}
            />
          </div>
        )}
      </div>

      <div className="flex-1 p-3">
        <h3 className="line-clamp-2 text-balance text-sm font-medium leading-5">
          {book.title}
        </h3>
        <p className="mt-1 truncate text-xs text-zinc-500">{book.author ?? "未知作者"}</p>
        <div className="mt-2 flex items-center justify-between text-[11px] text-zinc-500">
          <span>{formatDuration(book.total_duration_sec)}</span>
          <span>{book.track_count} 轨</span>
        </div>
      </div>

      <Link
        to={`/books/${book.id}`}
        aria-label={`查看《${book.title}》详情`}
        className="absolute inset-0 z-10 rounded-card focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-500"
      />
    </article>
  );
}
