import type { CSSProperties } from "react";

import type { Book } from "../../api/types";
import { formatDuration } from "../../lib/format";
import Cover from "../ui/Cover";
import { Icon } from "../ui/Icon";
import BookCard from "./BookCard";

interface BaseProps {
  name: string;
  books: Book[];
  /** 系列总卷数，取自 /series；可能大于当前已加载的卷数 */
  total: number;
  durationSec: number;
  /** 卷号最小那本的封面地址；为空表示该书的封面文件不存在 */
  coverUrl: string | null;
  onOpenAll: () => void;
}

interface FolderProps extends BaseProps {
  onToggle: () => void;
}

interface ShelfProps extends BaseProps {
  /** 收起动画播放中：整体淡出，DOM 稍后才移除 */
  closing: boolean;
  onCollapse: () => void;
  /** 外层网格当前的实际列数，用来避免 span 超过列数时撑出隐式轨道 */
  columns?: number;
}

function folderBook(name: string, coverUrl: string | null) {
  return { id: 0, title: name, cover_url: coverUrl };
}

/** 折叠态：一张带纸层的文件夹卡，占一格。 */
export function SeriesFolderCard({
  name,
  total,
  durationSec,
  coverUrl,
  onToggle,
  onOpenAll,
}: FolderProps) {
  return (
    <div className="group relative z-10 min-w-0">
      <div className="relative" data-folder-open="false">
        {/* 后面两层「纸」：向右错开、上下各缩一点，看着像一叠抽出半截的纸 */}
        <span
          aria-hidden
          className="folder-stack folder-stack--back absolute inset-y-3.5 left-0 right-0 rounded-card border border-zinc-400/60 bg-gradient-to-r from-white via-zinc-100 to-zinc-200 shadow-[9px_4px_16px_-8px_rgba(0,0,0,0.45)] dark:border-white/[0.22] dark:from-white/[0.42] dark:via-white/[0.26] dark:to-white/10 dark:shadow-[9px_5px_18px_-8px_rgba(0,0,0,0.75)]"
        />
        <span
          aria-hidden
          className="folder-stack folder-stack--mid absolute inset-y-2 left-0 right-0 rounded-card border border-zinc-300 bg-gradient-to-r from-white via-white to-zinc-100 shadow-[7px_3px_12px_-6px_rgba(0,0,0,0.38)] dark:border-white/[0.28] dark:from-white/[0.58] dark:via-white/[0.36] dark:to-white/[0.16] dark:shadow-[7px_4px_14px_-6px_rgba(0,0,0,0.65)]"
        />

        <button
          type="button"
          onClick={onToggle}
          aria-expanded={false}
          aria-label={`${name}，${total} 卷，展开`}
          title={`展开 ${total} 卷`}
          className={[
            "relative block aspect-square w-full overflow-hidden rounded-card border border-white/70 bg-white/70 text-left backdrop-blur-md transition duration-300",
            "shadow-[inset_0_1px_0_rgba(255,255,255,0.35),0_22px_40px_-24px_rgba(0,0,0,0.75)]",
            "group-hover:-translate-y-0.5 group-hover:border-brand-500/40 group-hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.4),0_26px_46px_-22px_rgba(0,0,0,0.8)]",
            "dark:border-white/10 dark:bg-white/[0.045]",
          ].join(" ")}
        >
          <Cover
            book={folderBook(name, coverUrl)}
            className="absolute inset-0 size-full"
            textClassName="text-3xl"
          />
          <span
            aria-hidden
            className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/5 to-transparent"
          />

          <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-black/50 px-2 py-0.5 text-[10px] font-medium text-white backdrop-blur">
            <Icon name="collections" className="size-3" />
            系列
          </span>

          <span className="absolute right-2 top-2 rounded-full bg-black/50 px-2 py-0.5 text-[10px] font-medium text-white backdrop-blur">
            {total} 卷
          </span>

          <span className="absolute inset-x-0 bottom-0 p-2.5 text-[11px] font-medium text-white/90">
            点击展开
          </span>
        </button>
      </div>

      <div className="mt-2 flex items-start justify-between gap-1 px-0.5">
        <div className="min-w-0">
          <p className="truncate text-[13px] font-medium">{name}</p>
          <p className="mt-0.5 truncate text-[11px] text-zinc-500">
            {total} 卷 · {formatDuration(durationSec)}
          </p>
        </div>
        <button
          type="button"
          onClick={onOpenAll}
          aria-label={`查看${name}系列的全部卷`}
          title="查看全部卷"
          className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-zinc-400 transition hover:bg-zinc-100 hover:text-brand-500 dark:hover:bg-white/10"
        >
          <Icon name="chevronRight" className="size-3.5" />
        </button>
      </div>
    </div>
  );
}

/**
 * 展开态：整个系列独占一行，外框把「哪几本是这个系列」圈起来。
 * 之前是直接往网格里插卡片，和后面的单本混在一起分不清边界。
 */
export function SeriesShelf({
  name,
  books,
  total,
  durationSec,
  coverUrl,
  closing,
  onCollapse,
  onOpenAll,
  columns,
}: ShelfProps) {
  // 宽度跟着卷数走，但不能超过当前列数：手机上只有 2 列，
  // span 4 会生成隐式轨道并把内容顶出屏幕（横向溢出）。
  const span = Math.max(
    1,
    Math.min(books.length, columns ?? books.length, 6),
  );

  return (
    <section
      style={{ gridColumn: `span ${span}` }}
      className={[
        "rounded-card border border-zinc-200/80 bg-white/60 p-3 backdrop-blur-sm dark:border-white/10 dark:bg-white/[0.035]",
        closing ? "folder-card-out" : "folder-card-in",
      ].join(" ")}
      aria-label={`${name} 系列，${total} 卷`}
    >
      <header className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1">
        <Cover
          book={folderBook(name, coverUrl)}
          className="size-8 shrink-0 overflow-hidden rounded-lg ring-1 ring-black/5 dark:ring-white/10"
          textClassName="text-xs"
        />
        <button
          type="button"
          onClick={onOpenAll}
          className="flex min-w-0 items-center gap-1 text-xs font-semibold transition hover:text-brand-500"
        >
          <span className="truncate">{name}</span>
          <Icon name="chevronRight" className="size-3 shrink-0 opacity-60" />
        </button>
        <span className="text-[11px] text-zinc-500">
          {total} 卷 · {formatDuration(durationSec)}
        </span>

        <button
          type="button"
          onClick={onCollapse}
          className="ml-auto inline-flex items-center gap-1 rounded-full border border-zinc-200 px-2.5 py-1 text-[11px] text-zinc-600 transition hover:border-brand-500/40 hover:text-brand-500 dark:border-white/10 dark:text-zinc-400"
        >
          <Icon name="chevronDown" className="size-3 rotate-180" />
          收起
        </button>
      </header>

      <div className="grid items-start gap-4 [grid-template-columns:repeat(auto-fill,minmax(120px,1fr))]">
        {books.map((book, index) => (
          <div
            key={`book-${book.id}`}
            className={closing ? "folder-card-out" : "folder-card-in"}
            style={{ "--card-index": index } as CSSProperties}
          >
            <BookCard book={book} />
          </div>
        ))}
      </div>
    </section>
  );
}

/** 列表视图里的文件夹：展开后由外层渲染 BookRow，缩进 + 竖线表示归属。 */
export function SeriesFolderRow({
  name,
  total,
  durationSec,
  coverUrl,
  onToggle,
  onOpenAll,
}: FolderProps) {
  return (
    <article className="group relative z-10 flex items-center gap-3 rounded-card border border-white/70 bg-white/70 p-2.5 backdrop-blur-md transition hover:border-brand-500/40 hover:shadow-glow-sm dark:border-white/10 dark:bg-white/[0.045]">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={false}
        aria-label={`${name}，${total} 卷，展开`}
        className="flex min-w-0 flex-1 items-center gap-3 text-left"
      >
        <div className="relative size-14 shrink-0">
          <span
            aria-hidden
            className="absolute inset-x-1.5 -top-1 h-full rounded-lg border border-white/40 bg-white/50 dark:border-white/10 dark:bg-white/[0.06]"
          />
          <Cover
            book={folderBook(name, coverUrl)}
            className="relative size-14 overflow-hidden rounded-lg"
            textClassName="text-lg"
          />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <Icon name="collections" className="size-3.5 shrink-0 text-brand-500" />
            <p className="truncate text-sm font-medium">{name}</p>
          </div>
          <p className="mt-0.5 truncate text-[11px] text-zinc-500">
            {total} 卷 · {formatDuration(durationSec)}
          </p>
        </div>

        <Icon
          name="chevronDown"
          className="size-4 shrink-0 text-zinc-400 transition group-hover:text-brand-500"
        />
      </button>

      <button
        type="button"
        onClick={onOpenAll}
        className="shrink-0 rounded-full border border-zinc-200 px-2.5 py-1 text-[11px] text-zinc-600 transition hover:border-brand-500/40 hover:text-brand-500 dark:border-white/10 dark:text-zinc-400"
      >
        查看全部
      </button>
    </article>
  );
}
