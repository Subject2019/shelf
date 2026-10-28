/** 封面：`<img>` 带不了 Authorization，用 fetch 取回后转 blob URL，并按书缓存在内存里。 */

import { useEffect, useState } from "react";

import { getAccessToken, refreshSession } from "../api/client";

export type CoverSize = "thumb" | "full";

const cache = new Map<string, string>();
const inflight = new Map<string, Promise<string | null>>();
const listeners = new Set<(bookId: number) => void>();

function keyOf(bookId: number, size: CoverSize): string {
  return `${bookId}:${size}`;
}

async function fetchBlobUrl(bookId: number, size: CoverSize): Promise<string | null> {
  const url = `/api/v1/books/${bookId}/cover?size=${size}`;
  const call = (token: string | null) =>
    fetch(url, token ? { headers: { Authorization: `Bearer ${token}` } } : {});

  let response = await call(getAccessToken());
  if (response.status === 401) {
    const refreshed = await refreshSession();
    if (refreshed) response = await call(refreshed);
  }
  if (!response.ok) return null;

  return URL.createObjectURL(await response.blob());
}

/** 取封面 blob URL；`enabled=false`（书没有封面）时不发请求。 */
export function useCoverUrl(
  bookId: number,
  size: CoverSize = "thumb",
  enabled = true,
): string | null {
  const key = keyOf(bookId, size);
  const [url, setUrl] = useState<string | null>(() => cache.get(key) ?? null);
  const [version, setVersion] = useState(0);

  useEffect(
    () =>
      onCoverInvalidated((id) => {
        if (id === bookId) setVersion((value) => value + 1);
      }),
    [bookId],
  );

  useEffect(() => {
    if (!enabled) {
      setUrl(null);
      return;
    }

    const cached = cache.get(key);
    if (cached) {
      setUrl(cached);
      return;
    }

    setUrl(null);
    let alive = true;
    let task = inflight.get(key);
    if (!task) {
      task = fetchBlobUrl(bookId, size);
      inflight.set(key, task);
    }

    void task.then((value) => {
      inflight.delete(key);
      if (!alive) return;
      if (value) {
        cache.set(key, value);
        setUrl(value);
      }
    });

    return () => {
      alive = false;
    };
  }, [bookId, size, enabled, key, version]);

  return url;
}

/** 上传/删除封面后调用：清缓存并通知所有订阅者重取。 */
export function invalidateCover(bookId: number): void {
  for (const size of ["thumb", "full"] as CoverSize[]) {
    const key = keyOf(bookId, size);
    const url = cache.get(key);
    if (url) URL.revokeObjectURL(url);
    cache.delete(key);
    inflight.delete(key);
  }
  for (const listener of listeners) listener(bookId);
}

function onCoverInvalidated(listener: (bookId: number) => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
