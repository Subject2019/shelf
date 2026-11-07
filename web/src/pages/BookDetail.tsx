import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import type { BookDetail as BookDetailType, Chapter } from "../api/types";
import MetadataEditor from "../components/book/MetadataEditor";
import CollectionPicker from "../components/collections/CollectionPicker";
import Cover from "../components/ui/Cover";
import { Icon } from "../components/ui/Icon";
import { formatClock, formatCount, formatDuration } from "../lib/format";
import { invalidateCover } from "../lib/cover";
import { useAuth } from "../store/auth";
import { usePlayer } from "../store/player";

export default function BookDetail() {
  const { bookId } = useParams();
  const id = Number(bookId);
  const queryClient = useQueryClient();
  const user = useAuth((state) => state.user);
  // 管理员与上传者可以改资料、换封面；听众只读
  const canEdit = user?.role === "admin" || user?.role === "editor";
  const currentBookId = usePlayer((state) => state.book?.id);
  const isCurrent = currentBookId === id;

  const [editing, setEditing] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  const bookQuery = useQuery({
    queryKey: ["book", id],
    queryFn: () => api.bookDetail(id),
    enabled: Number.isFinite(id) && id > 0,
  });

  const toggleHidden = useMutation({
    mutationFn: (hidden: boolean) => api.updateBook(id, { hidden }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["book", id] });
      void queryClient.invalidateQueries({ queryKey: ["books"] });
      void queryClient.invalidateQueries({ queryKey: ["series"] });
    },
  });

  const resetMetadata = useMutation({
    mutationFn: () => api.resetBookMetadata(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["book", id] });
      void queryClient.invalidateQueries({ queryKey: ["books"] });
    },
  });

  if (bookQuery.isLoading) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="h-6 w-24 animate-pulse rounded bg-zinc-200/70 dark:bg-white/5" />
        <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
          <div className="aspect-square animate-pulse rounded-2xl bg-zinc-200/70 dark:bg-white/5" />
          <div className="space-y-3">
            <div className="h-7 w-2/3 animate-pulse rounded bg-zinc-200/70 dark:bg-white/5" />
            <div className="h-4 w-1/3 animate-pulse rounded bg-zinc-200/70 dark:bg-white/5" />
            <div className="h-24 animate-pulse rounded bg-zinc-200/70 dark:bg-white/5" />
          </div>
        </div>
      </div>
    );
  }

  if (bookQuery.isError || !bookQuery.data) {
    return (
      <div className="mx-auto max-w-md py-16 text-center">
        <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-brand-500/10 text-brand-500">
          <Icon name="library" />
        </div>
        <h1 className="mt-5 text-lg font-semibold">找不到这本书</h1>
        <p className="mt-2 text-sm text-zinc-500">
          {bookQuery.error instanceof ApiError ? bookQuery.error.message : "可能已被移除"}
        </p>
        <Link
          to="/library"
          className="btn-gradient mt-6 inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium"
        >
          返回书库
        </Link>
      </div>
    );
  }

  const book = bookQuery.data;
  const chapters = book.chapters ?? [];
  const progress = book.progress;
  const percent = progress && !progress.is_finished ? progress.percent : 0;

  function play(positionSec?: number) {
    // 只有章节/书签等显式位置才传 positionSec；
    // 「继续收听」交给播放器在打开前重新读取服务端最新进度，避免用详情缓存里的旧值。
    void usePlayer.getState().open(
      book.id,
      positionSec === undefined ? undefined : { positionSec },
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Link
        to="/library"
        className="inline-flex items-center gap-1.5 text-xs text-zinc-500 transition hover:text-brand-500"
      >
        <Icon name="chevronLeft" className="size-4" />
        返回书库
      </Link>

      <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
        <div className="space-y-3">
          <Cover
            book={book}
            size="full"
            className="mx-auto aspect-square w-full max-w-[220px] overflow-hidden rounded-2xl shadow-lift ring-1 ring-white/10 sm:max-w-[260px] lg:mx-0 lg:max-w-none"
            textClassName="text-6xl"
          />

          {book.cover_url === null && (
            <p className="text-[11px] leading-4 text-zinc-500">
              没有找到封面，暂用书名渐变代替。
            </p>
          )}

          {canEdit && (
            <CoverEditor
              book={book}
              canDelete={
                user?.role === "admin" ||
                (book.cover_uploaded_by !== null &&
                  book.cover_uploaded_by === user?.id)
              }
              onUpdated={(updated) => {
              queryClient.setQueryData(["book", book.id], updated);
              void queryClient.invalidateQueries({ queryKey: ["books"] });
            }} />
          )}
        </div>

        <div className="min-w-0 space-y-5">
          <div>
            <h1 className="text-2xl font-semibold leading-8">{book.title}</h1>
            {book.subtitle && (
              <p className="mt-1 text-sm text-zinc-500">{book.subtitle}</p>
            )}
            <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
              {book.author ?? "未知作者"}
              {book.narrator ? ` · 演播 ${book.narrator}` : ""}
            </p>
            {book.hidden && (
              <p className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-zinc-500/10 px-2.5 py-1 text-[11px] text-zinc-600 dark:text-zinc-300">
                <Icon name="eyeOff" className="size-3.5" />
                已隐藏：普通用户在书架和搜索中都看不到
              </p>
            )}

            {book.is_missing && (
              <p className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-amber-500/10 px-2.5 py-1 text-[11px] text-amber-600 dark:text-amber-400">
                <Icon name="warning" className="size-3.5" />
                源文件已不在原路径，重新扫描前无法播放
              </p>
            )}

            {canEdit && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setEditing(true)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 px-3 py-1.5 text-[11px] text-zinc-700 transition hover:border-brand-500/50 hover:text-brand-500 dark:border-white/15 dark:text-zinc-300"
                >
                  <Icon name="edit" className="size-3.5" />
                  编辑资料
                </button>

                {user?.role === "admin" && (
                  <button
                    type="button"
                    disabled={toggleHidden.isPending}
                    onClick={() => toggleHidden.mutate(!book.hidden)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 px-3 py-1.5 text-[11px] text-zinc-700 transition hover:border-brand-500/50 hover:text-brand-500 disabled:opacity-50 dark:border-white/15 dark:text-zinc-300"
                  >
                    <Icon name={book.hidden ? "eye" : "eyeOff"} className="size-3.5" />
                    {book.hidden ? "取消隐藏" : "在书架中隐藏"}
                  </button>
                )}

                {book.manual_override && (
                  <>
                    <span className="rounded-full bg-amber-500/10 px-2.5 py-1 text-[11px] text-amber-600 dark:text-amber-400">
                      元数据已手工修改
                    </span>
                    <button
                      type="button"
                      disabled={resetMetadata.isPending}
                      onClick={() => resetMetadata.mutate()}
                      className="text-[11px] text-zinc-500 underline decoration-dotted transition hover:text-brand-500 disabled:opacity-50"
                    >
                      恢复自动识别
                    </button>
                  </>
                )}
              </div>
            )}
          </div>

          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="总时长" value={formatDuration(book.total_duration_sec)} />
            <Stat label="音轨" value={`${book.track_count} 轨`} />
            <Stat label="章节" value={chapters.length > 0 ? `${chapters.length} 章` : "—"} />
            <Stat
              label="大小"
              value={
                book.size_bytes > 0
                  ? `${(book.size_bytes / 1024 / 1024).toFixed(0)} MB`
                  : "—"
              }
            />
          </dl>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => play()}
              className="btn-gradient inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium"
            >
              <Icon name={isCurrent ? "play" : "play"} className="size-4" />
              {progress && progress.position_sec > 5
                ? `继续收听 · ${formatClock(progress.position_sec)}`
                : "开始播放"}
            </button>
            {!book.is_missing && (
              <button
                type="button"
                onClick={() => setPickerOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-full border border-zinc-300 px-4 py-2.5 text-sm text-zinc-700 transition hover:border-brand-500/40 hover:text-brand-500 dark:border-white/10 dark:text-zinc-300"
              >
                <Icon name="booklist" className="size-4" />
                加入书单
              </button>
            )}
            {percent > 0 && (
              <span className="text-xs text-zinc-500">已听 {percent.toFixed(0)}%</span>
            )}
            {isCurrent && (
              <Link
                to="/player"
                className="rounded-full border border-zinc-300 px-4 py-2.5 text-sm text-zinc-700 transition hover:border-brand-500/40 hover:text-brand-500 dark:border-white/10 dark:text-zinc-300"
              >
                打开播放页
              </Link>
            )}
          </div>

          {percent > 0 && (
            <div className="h-1 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-white/10">
              <div
                className="h-full bg-brand-gradient"
                style={{ width: `${Math.min(100, percent)}%` }}
              />
            </div>
          )}

          <div className="flex flex-wrap gap-2 text-[11px] text-zinc-500">
            {book.series_name && (
              <Link
                to={`/library?series=${encodeURIComponent(book.series_name)}`}
                className="inline-flex items-center gap-1 rounded-full border border-brand-500/40 bg-brand-500/10 px-2.5 py-1 text-brand-500 transition hover:border-brand-500"
                title="查看同系列的其他卷"
              >
                <Icon name="collections" className="size-3" />
                {book.series_name}
                {book.series_index
                  ? ` · 第 ${Number.isInteger(book.series_index) ? book.series_index : book.series_index.toFixed(1)} 卷`
                  : ""}
              </Link>
            )}
            {book.publisher && <Tag>{book.publisher}</Tag>}
            {book.publish_year && <Tag>{book.publish_year} 年</Tag>}
            {book.language && <Tag>{book.language}</Tag>}
            {book.chapter_source && <Tag>章节：{chapterSourceLabel(book.chapter_source)}</Tag>}
            {book.rel_dir && <Tag className="font-mono">{book.rel_dir}</Tag>}
          </div>

          {book.description ? (
            <section>
              <h2 className="text-sm font-semibold">简介</h2>
              <p className="mt-2 whitespace-pre-line text-sm leading-6 text-zinc-600 dark:text-zinc-400">
                {book.description}
              </p>
            </section>
          ) : (
            <section>
              <h2 className="text-sm font-semibold">简介</h2>
              <p className="mt-2 text-sm text-zinc-500">
                音频文件里没有简介。管理员可以在「编辑资料」中补上。
              </p>
            </section>
          )}
        </div>
      </div>

      {chapters.length > 0 && (
        <ChapterSection
          chapters={chapters}
          currentPosition={isCurrent ? undefined : progress?.position_sec}
          onPick={(chapter) => play(chapter.start_sec)}
        />
      )}

      {pickerOpen && (
        <CollectionPicker bookId={book.id} onClose={() => setPickerOpen(false)} />
      )}

      {editing && (
        <MetadataEditor
          book={book}
          onClose={() => setEditing(false)}
          onSaved={(updated) => {
            queryClient.setQueryData(["book", id], updated);
            void queryClient.invalidateQueries({ queryKey: ["books"] });
          }}
        />
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass rounded-xl px-3 py-2.5">
      <dt className="text-[11px] text-zinc-500">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium tabular-nums">{value}</dd>
    </div>
  );
}

function Tag({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`rounded-full border border-zinc-200/80 px-2.5 py-1 dark:border-white/10 ${className}`}
    >
      {children}
    </span>
  );
}

function chapterSourceLabel(source: string): string {
  const labels: Record<string, string> = {
    embedded: "内嵌",
    cue: "CUE",
    track: "按轨",
    virtual: "自动切分",
  };
  return labels[source] ?? source;
}

function ChapterSection({
  chapters,
  currentPosition,
  onPick,
}: {
  chapters: Chapter[];
  currentPosition?: number;
  onPick: (chapter: Chapter) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? chapters : chapters.slice(0, 8);

  return (
    <section className="glass rounded-2xl p-4 shadow-lift sm:p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">
          章节
          <span className="ml-1.5 text-[11px] font-normal text-zinc-500">
            共 {formatCount(chapters.length)} 章
          </span>
        </h2>
        {chapters.length > 8 && (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="text-[11px] text-zinc-500 transition hover:text-brand-500"
          >
            {expanded ? "收起" : `展开全部 ${chapters.length} 章`}
          </button>
        )}
      </div>

      <div className="mt-3 grid gap-1 sm:grid-cols-2">
        {visible.map((chapter, index) => {
          const length = (chapter.end_sec ?? chapter.start_sec) - chapter.start_sec;
          const active =
            currentPosition !== undefined &&
            currentPosition >= chapter.start_sec &&
            (chapter.end_sec === null || currentPosition < chapter.end_sec);
          return (
            <button
              key={chapter.id}
              type="button"
              onClick={() => onPick(chapter)}
              className={[
                "flex items-center gap-3 rounded-lg px-2.5 py-2 text-left transition",
                active
                  ? "bg-brand-500/10 text-brand-500"
                  : "hover:bg-zinc-100 dark:hover:bg-white/5",
              ].join(" ")}
            >
              <span className="w-6 shrink-0 text-[11px] tabular-nums text-zinc-400">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="min-w-0 flex-1 truncate text-xs">{chapter.title}</span>
              <span className="shrink-0 text-[11px] tabular-nums text-zinc-500">
                {length > 0 ? formatClock(length) : formatClock(chapter.start_sec)}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function CoverEditor({
  book,
  canDelete,
  onUpdated,
}: {
  book: BookDetailType;
  /** 管理员可删任意封面，上传者只能删自己传的 */
  canDelete: boolean;
  onUpdated: (book: BookDetailType) => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [error, setError] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: (file: File) => api.uploadCover(book.id, file),
    onSuccess: (updated) => {
      setError(null);
      invalidateCover(book.id);
      onUpdated({ ...book, cover_url: updated.cover_url });
    },
    onError: (value) => {
      setError(value instanceof ApiError ? value.message : "上传失败");
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteCover(book.id),
    onSuccess: (updated) => {
      setError(null);
      invalidateCover(book.id);
      onUpdated({ ...book, cover_url: updated.cover_url });
    },
    onError: (value) => {
      setError(value instanceof ApiError ? value.message : "删除失败");
    },
  });

  const busy = upload.isPending || remove.isPending;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-dashed border-zinc-300 py-2 text-[11px] text-zinc-600 transition hover:border-brand-500/60 hover:text-brand-500 disabled:opacity-50 dark:border-white/15 dark:text-zinc-400"
        >
          <Icon name="image" className="size-3.5" />
          {upload.isPending ? "上传中…" : book.cover_url ? "更换封面" : "上传封面"}
        </button>
        {book.cover_url && canDelete && (
          <button
            type="button"
            disabled={busy}
            onClick={() => remove.mutate()}
            aria-label="删除封面"
            className="flex size-8 items-center justify-center rounded-lg border border-zinc-300 text-zinc-500 transition hover:border-rose-500/50 hover:text-rose-500 disabled:opacity-50 dark:border-white/15"
          >
            <Icon name="trash" className="size-3.5" />
          </button>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (!file) return;
          if (file.size > 5 * 1024 * 1024) {
            setError("图片不能超过 5 MB");
            return;
          }
          upload.mutate(file);
        }}
      />

      {error ? (
        <p className="text-[11px] text-rose-500">{error}</p>
      ) : (
        <p className="text-[11px] text-zinc-500">JPG / PNG / WebP，≤ 5 MB，自动转 JPEG</p>
      )}
    </div>
  );
}
