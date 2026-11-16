import { useEffect, useMemo, useState } from "react";

import { api } from "../../api/endpoints";
import type { Chapter, DownloadManifest } from "../../api/types";
import { Icon } from "../ui/Icon";
import {
  enqueueNativeDownload,
  hasNativeDownload,
  isOfflineMode,
  readDownloadSnapshot,
  removeNativeDownload,
  type NativeDownloadBookStatus,
} from "../../lib/download";

function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return "";
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(0)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function chapterDuration(chapter: Chapter): number {
  return chapter.end_sec !== null
    ? Math.max(0, chapter.end_sec - chapter.start_sec)
    : 0;
}

export default function OfflineDownload({
  bookId,
  title,
}: {
  bookId: number;
  title: string;
}) {
  const [status, setStatus] = useState<NativeDownloadBookStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [pickerBusy, setPickerBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [manifest, setManifest] = useState<DownloadManifest | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const available = hasNativeDownload();
  const offline = isOfflineMode();

  useEffect(() => {
    if (!available) return;
    const sync = () => {
      setStatus(readDownloadSnapshot()[String(bookId)] ?? null);
    };
    sync();
    const timer = window.setInterval(sync, 1000);
    return () => window.clearInterval(timer);
  }, [available, bookId]);

  const downloaded = useMemo(
    () =>
      new Set(
        (status?.chapters ?? [])
          .filter((chapter) => chapter.status === "done")
          .map((chapter) => chapter.idx),
      ),
    [status],
  );
  const bookTotal = status?.bookTotal || status?.total || 0;
  const isFullDone =
    status?.status === "done" && (bookTotal === 0 || status.total >= bookTotal);

  async function ensureManifest(): Promise<DownloadManifest | null> {
    if (manifest) return manifest;
    setPickerBusy(true);
    setError(null);
    try {
      const data = await api.downloadManifest(bookId);
      if (!data.chapters.length) {
        setError("这本书没有章节信息，暂不支持离线下载");
        return null;
      }
      setManifest(data);
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取章节清单失败");
      return null;
    } finally {
      setPickerBusy(false);
    }
  }

  async function openPicker() {
    if (busy || offline) return;
    const data = await ensureManifest();
    if (!data) return;
    const already = new Set(
      (status?.chapters ?? [])
        .filter((chapter) => chapter.status === "done")
        .map((chapter) => chapter.idx),
    );
    setSelected(
      new Set(
        data.chapters
          .filter((chapter) => !already.has(chapter.idx))
          .map((chapter) => chapter.idx),
      ),
    );
    setPickerOpen(true);
  }

  async function downloadChapters(
    chapters: Chapter[],
    knownManifest?: DownloadManifest,
  ) {
    if (chapters.length === 0) {
      setError("请至少选择一章");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const data = knownManifest ?? (await ensureManifest());
      if (!data) return;
      const ticket = await api.downloadTicket(bookId);
      const cached = new Map(data.cached.map((item) => [item.index, item.bytes]));
      const origin = window.location.origin;
      const ok = enqueueNativeDownload({
        bookId,
        title,
        ticket: ticket.token,
        bookTotal: data.chapters.length,
        allChapters: data.chapters,
        chapters: chapters.map((chapter) => ({
          idx: chapter.idx,
          title: chapter.title,
          url: `${origin}/api/v1/books/${bookId}/chapters/${chapter.idx}/audio?download=1`,
          trackId: chapter.track_id,
          startSec: chapter.start_sec,
          durationSec: chapterDuration(chapter),
          bytes: cached.get(chapter.idx) ?? 0,
        })),
      });
      if (!ok) {
        setError("当前客户端不支持离线下载");
        return;
      }
      setPickerOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建下载任务失败");
    } finally {
      setBusy(false);
    }
  }

  async function startAll() {
    if (busy) return;
    const data = await ensureManifest();
    if (data) await downloadChapters(data.chapters, data);
  }

  function toggleChapter(idx: number) {
    if (downloaded.has(idx)) return;
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  if (!available) return null;

  if (offline && status?.status !== "done") {
    return (
      <span
        title="离线模式无法创建新的下载"
        aria-disabled="true"
        className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-full border border-zinc-300 px-4 py-2.5 text-sm text-zinc-400 opacity-45 dark:border-white/10 dark:text-zinc-600"
      >
        <Icon name="download" className="size-4" />
        离线模式不可下载
      </span>
    );
  }

  if (isFullDone) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-sm text-emerald-600 dark:text-emerald-400">
          <Icon name="check" className="size-4" />
          已下载整本 {formatBytes(status.downloadedBytes)}
        </span>
        <button
          type="button"
          onClick={() => removeNativeDownload(bookId)}
          className="inline-flex items-center gap-1.5 rounded-full border border-zinc-300 px-4 py-2.5 text-sm text-zinc-600 transition hover:border-rose-400/60 hover:text-rose-500 dark:border-white/10 dark:text-zinc-300"
        >
          <Icon name="trash" className="size-4" />
          删除离线文件
        </button>
      </div>
    );
  }

  if (status?.status === "done") {
    return (
      <>
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-sm text-emerald-600 dark:text-emerald-400">
            <Icon name="check" className="size-4" />
            已下载 {status.done}/{bookTotal || status.total} 章
            {formatBytes(status.downloadedBytes) ? ` · ${formatBytes(status.downloadedBytes)}` : ""}
          </span>
          {!offline && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void openPicker()}
              className="inline-flex items-center gap-1.5 rounded-full border border-zinc-300 px-4 py-2.5 text-sm text-zinc-700 transition hover:border-brand-500/40 hover:text-brand-500 disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:text-zinc-300"
            >
              <Icon name="download" className="size-4" />
              继续选择章节
            </button>
          )}
          <button
            type="button"
            onClick={() => removeNativeDownload(bookId)}
            className="inline-flex items-center gap-1.5 rounded-full border border-zinc-300 px-4 py-2.5 text-sm text-zinc-600 transition hover:border-rose-400/60 hover:text-rose-500 dark:border-white/10 dark:text-zinc-300"
          >
            <Icon name="trash" className="size-4" />
            删除离线文件
          </button>
          {error && <span className="text-[11px] text-rose-500">{error}</span>}
        </div>
        {renderPicker()}
      </>
    );
  }

  if (status && (status.status === "running" || status.status === "queued")) {
    const percent =
      status.totalBytes > 0
        ? Math.min(100, Math.round((status.downloadedBytes / status.totalBytes) * 100))
        : 0;
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-brand-500/30 bg-brand-500/10 px-4 py-2.5 text-sm text-brand-500">
          <Icon name="download" className="size-4" />
          下载中 {percent > 0 ? `${percent}%` : ""}（{status.done}/
          {bookTotal || status.total} 章）
        </span>
        {error && <span className="text-[11px] text-rose-500">{error}</span>}
      </div>
    );
  }

  return (
    <>
      <div className="flex flex-col items-start gap-1">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => void startAll()}
            className="inline-flex items-center gap-1.5 rounded-full border border-zinc-300 px-4 py-2.5 text-sm text-zinc-700 transition hover:border-brand-500/40 hover:text-brand-500 disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:text-zinc-300"
          >
            <Icon name="download" className="size-4" />
            {busy ? "准备下载…" : status?.status === "failed" ? "重新下载整本" : "下载整本"}
          </button>
          {!offline && (
            <button
              type="button"
              disabled={busy || pickerBusy}
              onClick={() => void openPicker()}
              className="inline-flex items-center gap-1.5 rounded-full border border-zinc-300 px-4 py-2.5 text-sm text-zinc-700 transition hover:border-brand-500/40 hover:text-brand-500 disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:text-zinc-300"
            >
              <Icon name="download" className="size-4" />
              选择章节
            </button>
          )}
        </div>
        {status?.status === "failed" && (
          <span className="text-[11px] text-amber-600 dark:text-amber-400">
            上次下载中断，可重新下载或只补下缺失章节
          </span>
        )}
        {error && <span className="text-[11px] text-rose-500">{error}</span>}
      </div>
      {renderPicker()}
    </>
  );

  function renderPicker() {
    if (!pickerOpen || !manifest) return null;
    const selectable = manifest.chapters.filter(
      (chapter) => !downloaded.has(chapter.idx),
    );
    const selectedCount = selectable.filter((chapter) =>
      selected.has(chapter.idx),
    ).length;
    return (
      <div
        className="fixed inset-0 z-[80] flex items-end justify-center bg-black/45 p-4 backdrop-blur-sm sm:items-center"
        onClick={() => {
          if (!busy) setPickerOpen(false);
        }}
      >
        <div
          role="dialog"
          aria-modal="true"
          aria-label="选择下载章节"
          className="flex max-h-[80vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-2xl dark:border-white/10 dark:bg-[#1b1a18]"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-4 py-3 dark:border-white/10">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold">选择下载章节</h2>
              <p className="mt-0.5 truncate text-[11px] text-zinc-500">{title}</p>
            </div>
            <button
              type="button"
              aria-label="关闭"
              disabled={busy}
              onClick={() => setPickerOpen(false)}
              className="flex size-8 shrink-0 items-center justify-center rounded-full text-zinc-500 transition hover:bg-zinc-100 disabled:opacity-40 dark:hover:bg-white/5"
            >
              <Icon name="close" className="size-4" />
            </button>
          </div>

          <div className="flex items-center justify-between gap-2 border-b border-zinc-100 px-4 py-2 dark:border-white/5">
            <span className="text-[11px] text-zinc-500">
              全书 {manifest.chapters.length} 章，已选 {selectedCount} 章
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() =>
                  setSelected(new Set(selectable.map((chapter) => chapter.idx)))
                }
                className="text-[11px] font-medium text-brand-500 hover:text-brand-600"
              >
                全选未下载
              </button>
              <button
                type="button"
                onClick={() => setSelected(new Set())}
                className="text-[11px] text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
              >
                清空
              </button>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
            {manifest.chapters.map((chapter) => {
              const isDownloaded = downloaded.has(chapter.idx);
              const isSelected = isDownloaded || selected.has(chapter.idx);
              return (
                <label
                  key={chapter.idx}
                  className={[
                    "flex cursor-pointer items-center gap-3 rounded-xl px-2.5 py-2.5 text-sm transition",
                    isDownloaded
                      ? "cursor-default text-zinc-400"
                      : "hover:bg-brand-500/5",
                  ].join(" ")}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    disabled={isDownloaded || busy}
                    onChange={() => toggleChapter(chapter.idx)}
                    className="size-4 shrink-0 accent-[var(--brand-500)]"
                  />
                  <span className="min-w-0 flex-1 truncate">
                    {chapter.idx + 1}. {chapter.title}
                  </span>
                  {isDownloaded && (
                    <span className="shrink-0 text-[10px] text-emerald-600 dark:text-emerald-400">
                      已下载
                    </span>
                  )}
                </label>
              );
            })}
          </div>

          <div className="flex items-center justify-between gap-3 border-t border-zinc-200 px-4 py-3 dark:border-white/10">
            <span className="min-w-0 truncate text-[11px] text-rose-500">{error}</span>
            <button
              type="button"
              disabled={busy || selectedCount === 0}
              onClick={() =>
                void downloadChapters(
                  selectable.filter((chapter) => selected.has(chapter.idx)),
                )
              }
              className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-brand-500 px-4 py-2 text-xs font-medium text-white transition hover:bg-brand-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Icon name="download" className="size-3.5" />
              {busy ? "准备下载…" : `下载选中（${selectedCount} 章）`}
            </button>
          </div>
        </div>
      </div>
    );
  }
}
