import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api } from "../../api/endpoints";
import type { Chapter } from "../../api/types";
import { formatClock, formatRelative } from "../../lib/format";
import { Icon } from "../ui/Icon";

/** 章节 / 书签面板内容，抽屉（PlayerPanel）与 /player 右栏共用。 */
interface PlayerLibraryPanelProps {
  bookId: number;
  chapters: Chapter[];
  currentIndex: number;
  positionSec: number;
  onSeek: (positionSec: number) => void;
  onAddBookmark: (note: string | null) => void;
  onNavigate?: () => void;
}

export default function PlayerLibraryPanel({
  bookId,
  chapters,
  currentIndex,
  positionSec,
  onSeek,
  onAddBookmark,
  onNavigate,
}: PlayerLibraryPanelProps) {
  const [tab, setTab] = useState<"chapters" | "bookmarks" | "history">(
    "chapters",
  );
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const activeRef = useRef<HTMLButtonElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const queryClient = useQueryClient();

  const bookmarksQuery = useQuery({
    queryKey: ["bookmarks", bookId],
    queryFn: () => api.bookmarks(bookId),
  });
  const bookmarks = bookmarksQuery.data ?? [];

  const historyQuery = useQuery({
    queryKey: ["progress-history", bookId],
    queryFn: () => api.progressHistory(bookId),
    enabled: tab === "history",
  });
  const historyItems = historyQuery.data?.items ?? [];

  const updateMutation = useMutation({
    mutationFn: ({ id, note }: { id: number; note: string | null }) =>
      api.updateBookmark(id, note),
    onSuccess: () => {
      setEditingId(null);
      void queryClient.invalidateQueries({ queryKey: ["bookmarks", bookId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteBookmark(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["bookmarks", bookId] });
    },
  });

  useEffect(() => {
    if (tab !== "chapters") return;
    const container = listRef.current;
    const item = activeRef.current;
    if (!container || !item) return;
    // 只滚列表自身；用 scrollIntoView 会连带滚动 window，把页面标题顶到顶栏底下
    const target =
      item.offsetTop - container.clientHeight / 2 + item.clientHeight / 2;
    container.scrollTo({ top: Math.max(0, target) });
  }, [tab, currentIndex]);

  const chapterOf = (value: number): Chapter | null => {
    let found: Chapter | null = chapters[0] ?? null;
    for (const chapter of chapters) {
      if (chapter.start_sec <= value + 0.01) found = chapter;
      else break;
    }
    return found;
  };

  const tabButton = (
    key: "chapters" | "bookmarks" | "history",
    label: string,
    count: number,
  ) => {
    const active = tab === key;
    return (
      <button
        key={key}
        type="button"
        onClick={() => setTab(key)}
        className={[
          "-mb-px flex-1 border-b-2 px-4 py-2.5 text-xs font-medium transition",
          active
            ? "border-brand-500 text-brand-500"
            : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200",
        ].join(" ")}
      >
        {label}
        <span className="ml-1 text-[11px] opacity-70">{count}</span>
      </button>
    );
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex border-b border-zinc-200/80 dark:border-white/5">
        {tabButton("chapters", "章节", chapters.length)}
        {tabButton("bookmarks", "书签", bookmarks.length)}
        {tabButton("history", "进度", historyItems.length)}
      </div>

      {tab === "chapters" ? (
        <div ref={listRef} className="relative min-h-0 flex-1 overflow-y-auto py-1">
          {chapters.length === 0 && (
            <p className="px-4 py-10 text-center text-xs text-zinc-500">
              这本书没有章节信息，可拖动进度条定位
            </p>
          )}
          {chapters.map((chapter, index) => {
            const active = index === currentIndex;
            const length = (chapter.end_sec ?? chapter.start_sec) - chapter.start_sec;
            return (
              <button
                key={chapter.id}
                ref={active ? activeRef : undefined}
                type="button"
                onClick={() => {
                  onSeek(chapter.start_sec);
                  onNavigate?.();
                }}
                className={[
                  "flex w-full items-start gap-3 px-4 py-2.5 text-left transition",
                  active
                    ? "bg-brand-500/10"
                    : "hover:bg-zinc-100 dark:hover:bg-white/5",
                ].join(" ")}
              >
                <span
                  className={[
                    "mt-0.5 w-6 shrink-0 text-[11px] tabular-nums",
                    active ? "text-brand-500" : "text-zinc-400",
                  ].join(" ")}
                >
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="min-w-0 flex-1">
                  <span
                    className={[
                      "block truncate text-xs",
                      active ? "font-medium text-brand-500" : "",
                    ].join(" ")}
                  >
                    {chapter.title}
                  </span>
                  <span className="mt-0.5 block text-[11px] text-zinc-500">
                    {formatClock(chapter.start_sec)}
                    {length > 0 ? ` · ${formatClock(length)}` : ""}
                  </span>
                </span>
                {active && (
                  <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-brand-500" />
                )}
              </button>
            );
          })}
        </div>
      ) : tab === "bookmarks" ? (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <button
            type="button"
            onClick={() => onAddBookmark(null)}
            className="mx-4 mt-3 flex w-[calc(100%-2rem)] items-center justify-center gap-1.5 rounded-lg border border-dashed border-brand-500/50 py-2 text-xs font-medium text-brand-500 transition hover:bg-brand-500/10"
          >
            <Icon name="bookmark" className="size-3.5" />
            在 {formatClock(positionSec)} 添加书签
          </button>

          {bookmarks.length === 0 && !bookmarksQuery.isLoading && (
            <p className="px-4 py-10 text-center text-xs text-zinc-500">
              还没有书签。播放到想记的地方点上面的按钮。
            </p>
          )}

          <div className="py-1">
            {bookmarks.map((bookmark) => (
              <div key={bookmark.id}>
                <div className="group flex items-start gap-2 px-4 py-2.5 transition hover:bg-zinc-100 dark:hover:bg-white/5">
                  <button
                    type="button"
                    onClick={() => {
                      onSeek(bookmark.position_sec);
                      onNavigate?.();
                    }}
                    className="flex min-w-0 flex-1 items-start gap-3 text-left"
                  >
                    <span className="mt-0.5 w-12 shrink-0 text-[11px] tabular-nums text-brand-500">
                      {formatClock(bookmark.position_sec)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-xs">
                        {bookmark.note || "未命名书签"}
                      </span>
                      <span className="mt-0.5 block truncate text-[11px] text-zinc-500">
                        {chapterOf(bookmark.position_sec)?.title ?? ""}
                      </span>
                    </span>
                  </button>

                  <div className="flex shrink-0 items-center gap-0.5">
                    <button
                      type="button"
                      aria-label="编辑备注"
                      onClick={() => {
                        setEditingId(bookmark.id);
                        setDraft(bookmark.note ?? "");
                      }}
                      className="flex size-7 items-center justify-center rounded-full text-zinc-400 transition hover:bg-zinc-200 hover:text-zinc-700 dark:hover:bg-white/10 dark:hover:text-zinc-200"
                    >
                      <Icon name="edit" className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      aria-label="删除书签"
                      onClick={() => deleteMutation.mutate(bookmark.id)}
                      className="flex size-7 items-center justify-center rounded-full text-zinc-400 transition hover:bg-rose-500/10 hover:text-rose-500"
                    >
                      <Icon name="trash" className="size-3.5" />
                    </button>
                  </div>
                </div>

                {editingId === bookmark.id && (
                  <div className="flex items-center gap-2 pb-2.5 pl-[3.75rem] pr-4">
                    <input
                      autoFocus
                      value={draft}
                      onChange={(event) => setDraft(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          updateMutation.mutate({
                            id: bookmark.id,
                            note: draft.trim() || null,
                          });
                        }
                        if (event.key === "Escape") setEditingId(null);
                      }}
                      placeholder="备注"
                      className="min-w-0 flex-1 rounded-md border border-zinc-200 bg-white px-2 py-1 text-xs outline-none focus:border-brand-500 dark:border-white/10 dark:bg-ink-800"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        updateMutation.mutate({
                          id: bookmark.id,
                          note: draft.trim() || null,
                        })
                      }
                      className="rounded-md bg-brand-500 px-2 py-1 text-[11px] font-medium text-ink-950"
                    >
                      保存
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto py-1">
          <p className="px-4 pt-3 pb-2 text-[11px] leading-relaxed text-zinc-500">
            位置变化超过阈值时自动记一个点，最多保留 3 个；误拖进度条后可回到这里。
          </p>

          {historyItems.length === 0 && !historyQuery.isLoading && (
            <p className="px-4 py-8 text-center text-xs text-zinc-500">
              还没有回溯点
            </p>
          )}

          {historyItems.map((item, index) => {
            const chapter = chapterOf(item.position_sec);
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  onSeek(item.position_sec);
                  onNavigate?.();
                }}
                className="flex w-full items-start gap-3 px-4 py-2.5 text-left transition hover:bg-zinc-100 dark:hover:bg-white/5"
              >
                <span className="mt-0.5 w-12 shrink-0 text-[11px] tabular-nums text-brand-500">
                  {formatClock(item.position_sec)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-xs">
                    {chapter?.title ?? "未识别章节"}
                  </span>
                  <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-zinc-500">
                    {index === 0 && (
                      <span className="rounded-full bg-brand-500/10 px-1.5 py-px text-[10px] text-brand-500">
                        当前
                      </span>
                    )}
                    {formatRelative(item.created_at)}
                  </span>
                </span>
                <span className="mt-0.5 shrink-0 text-[10px] text-zinc-400">
                  恢复
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
