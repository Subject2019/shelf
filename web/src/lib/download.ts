/** Android WebView 原生离线下载桥。浏览器里所有方法都会安全降级为不可用。 */

import type { Chapter } from "../api/types";

export interface NativeDownloadChapter {
  idx: number;
  title: string;
  url: string;
  trackId: number;
  startSec: number;
  durationSec: number;
  bytes: number;
}

export interface NativeDownloadChapterStatus {
  idx: number;
  title: string;
  trackId: number;
  startSec: number;
  durationSec: number;
  status: "queued" | "running" | "done" | "failed" | "canceled";
  downloadedBytes: number;
  totalBytes: number;
  filePath: string;
  error: string;
}

export interface NativeDownloadBookStatus {
  bookId: number;
  title: string;
  /** 全书章节数；total 是本次入队/已选择的章节数。 */
  bookTotal: number;
  total: number;
  done: number;
  failed: number;
  downloadedBytes: number;
  totalBytes: number;
  status: "queued" | "running" | "done" | "failed" | "canceled";
  chapters: NativeDownloadChapterStatus[];
}

interface ShelfDownloadBridge {
  enqueue(payload: string): void;
  snapshot(): string;
  cancelBook(bookId: number): void;
  removeBook(bookId: number): void;
  playBook(bookId: number): void;
  playChapter(bookId: number, chapterIdx: number): void;
  playAt(bookId: number, chapterIdx: number, positionSec: number): void;
}

declare global {
  interface Window {
    ShelfDownload?: ShelfDownloadBridge;
    ShelfApp?: {
      retry?: () => void;
      openOffline?: () => void;
    };
  }
}

/** Android 内置 WebUI 用 127.0.0.1 加载；此模式下不访问远程 API。 */
export function isOfflineMode(): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  return (
    new URLSearchParams(window.location.search).get("offline") === "1" ||
    host === "127.0.0.1"
  );
}

export function hasNativeDownload(): boolean {
  return typeof window !== "undefined" && Boolean(window.ShelfDownload);
}

export function readDownloadSnapshot(): Record<string, NativeDownloadBookStatus> {
  if (!hasNativeDownload()) return {};
  try {
    return JSON.parse(window.ShelfDownload!.snapshot()) as Record<
      string,
      NativeDownloadBookStatus
    >;
  } catch {
    return {};
  }
}

export function enqueueNativeDownload(payload: {
  bookId: number;
  title: string;
  ticket: string;
  bookTotal: number;
  allChapters: Chapter[];
  chapters: NativeDownloadChapter[];
}): boolean {
  if (!hasNativeDownload()) return false;
  window.ShelfDownload!.enqueue(JSON.stringify(payload));
  return true;
}

export function removeNativeDownload(bookId: number): void {
  window.ShelfDownload?.removeBook(bookId);
}
