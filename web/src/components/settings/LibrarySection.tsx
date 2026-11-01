import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "../../api/endpoints";
import type { Library, ScanStatus } from "../../api/types";
import { formatCount, formatRelative } from "../../lib/format";
import { Icon } from "../ui/Icon";

const fieldClass =
  "h-10 w-full rounded-lg border border-zinc-200 bg-white px-3 text-sm outline-none transition focus:border-brand-500 dark:border-white/10 dark:bg-ink-950";
const DEFAULT_ROOT_PATH = "/audiobooks";

export default function LibrarySection() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [rootPath, setRootPath] = useState(DEFAULT_ROOT_PATH);
  const [formError, setFormError] = useState<string | null>(null);
  const [scanningId, setScanningId] = useState<number | null>(null);
  const [scanResult, setScanResult] = useState<{
    libraryId: number;
    status: ScanStatus;
  } | null>(null);
  const [pendingDelete, setPendingDelete] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const librariesQuery = useQuery({
    queryKey: ["libraries"],
    queryFn: () => api.libraries(),
  });

  const scanQuery = useQuery({
    queryKey: ["scan", scanningId],
    queryFn: () => api.scanStatus(scanningId as number),
    enabled: scanningId !== null,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 1200;
      return data.status === "success" || data.status === "failed" ? false : 1200;
    },
  });

  useEffect(() => {
    const data = scanQuery.data;
    if (!data || scanningId === null) return;
    if (data.status === "success" || data.status === "failed") {
      const libraryId = scanningId;
      // 扫描往往一秒内结束，结果提示保留几秒，否则用户看不到任何反馈
      setScanResult({ libraryId, status: data });
      setScanningId(null);
      void queryClient.invalidateQueries({ queryKey: ["libraries"] });
      void queryClient.invalidateQueries({ queryKey: ["books"] });
      void queryClient.invalidateQueries({ queryKey: ["health"] });
      window.setTimeout(() => {
        setScanResult((current) =>
          current?.libraryId === libraryId ? null : current,
        );
      }, 6000);
    }
  }, [scanQuery.data, scanningId, queryClient]);

  const createMutation = useMutation({
    mutationFn: () => api.createLibrary({ name: name.trim(), root_path: rootPath.trim() }),
    onSuccess: () => {
      setCreating(false);
      setName("");
      setRootPath(DEFAULT_ROOT_PATH);
      setFormError(null);
      void queryClient.invalidateQueries({ queryKey: ["libraries"] });
    },
    onError: (error: unknown) => {
      setFormError(error instanceof Error ? error.message : "登记失败");
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      api.updateLibrary(id, { enabled }),
    onSuccess: () => {
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["libraries"] });
      void queryClient.invalidateQueries({ queryKey: ["health"] });
    },
    onError: (error: unknown) => {
      setActionError(error instanceof Error ? error.message : "操作失败");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteLibrary(id),
    onSuccess: () => {
      setPendingDelete(null);
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: ["libraries"] });
      void queryClient.invalidateQueries({ queryKey: ["books"] });
      void queryClient.invalidateQueries({ queryKey: ["health"] });
    },
    onError: (error: unknown) => {
      setPendingDelete(null);
      setActionError(error instanceof Error ? error.message : "删除失败");
    },
  });

  const scanMutation = useMutation({
    mutationFn: (id: number) => api.scanLibrary(id),
    onSuccess: (_data, id) => {
      setScanningId(id);
      void queryClient.invalidateQueries({ queryKey: ["libraries"] });
    },
  });

  const libraries = librariesQuery.data?.items ?? [];

  function renderRow(library: Library) {
    const scanning = scanningId === library.id;
    const status =
      (scanning ? scanQuery.data : null) ??
      (scanResult?.libraryId === library.id ? scanResult.status : null);
    const settled = status?.status === "success" || status?.status === "failed";

    return (
      <li
        key={library.id}
        className="rounded-xl border border-zinc-200/80 p-3 dark:border-white/10"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-medium">{library.name}</span>
              {!library.enabled && (
                <span className="rounded-full bg-zinc-200 px-1.5 py-0.5 text-[10px] text-zinc-600 dark:bg-white/10 dark:text-zinc-300">
                  已停用
                </span>
              )}
            </div>
            <p className="mt-0.5 truncate text-[11px] text-zinc-500" title={library.root_path}>
              {library.root_path}
            </p>
            <p className="mt-1 text-[11px] text-zinc-500">
              {formatCount(library.book_count)} 本 ·{" "}
              {library.last_scan_at
                ? `上次扫描 ${formatRelative(library.last_scan_at)}`
                : "尚未扫描"}
            </p>
          </div>

          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => scanMutation.mutate(library.id)}
              disabled={scanning || !library.enabled}
              title={library.enabled ? "扫描这个书库" : "书库已停用，启用后才能扫描"}
              aria-label="扫描这个书库"
              className="flex size-8 items-center justify-center rounded-full text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-900 disabled:opacity-40 dark:hover:bg-white/10 dark:hover:text-zinc-100"
            >
              <Icon
                name="refresh"
                className={`size-4 ${scanning ? "animate-spin" : ""}`}
              />
            </button>

            <button
              type="button"
              onClick={() =>
                toggleMutation.mutate({ id: library.id, enabled: !library.enabled })
              }
              title={library.enabled ? "停用（停用后仍会显示，可再次启用）" : "启用书库"}
              aria-label={library.enabled ? "停用书库" : "启用书库"}
              className="flex size-8 items-center justify-center rounded-full text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-white/10 dark:hover:text-zinc-100"
            >
              <Icon name="power" className="size-4" />
            </button>

            <button
              type="button"
              onClick={() =>
                setPendingDelete(pendingDelete === library.id ? null : library.id)
              }
              title="删除登记（只删索引，不动硬盘文件）"
              aria-label="删除书库"
              className="flex size-8 items-center justify-center rounded-full text-zinc-400 transition hover:bg-rose-500/10 hover:text-rose-500"
            >
              <Icon name="trash" className="size-4" />
            </button>
          </div>
        </div>

        {(scanning || status) && (
          <p
            className={`mt-2 rounded-lg px-2.5 py-1.5 text-[11px] ${
              status?.status === "failed"
                ? "bg-rose-500/10 text-rose-500"
                : settled
                  ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  : "bg-brand-500/10 text-brand-500"
            }`}
          >
            {status
              ? status.status === "running"
                ? `扫描中：已见 ${status.files_seen} 个文件`
                : `扫描${status.status === "success" ? "完成" : "失败"}：新增 ${status.books_created} 本、更新 ${status.books_updated} 本${status.error ? `（${status.error}）` : ""}`
              : "正在启动扫描…"}
          </p>
        )}

        {pendingDelete === library.id && (
          <div className="mt-2 flex items-center justify-between gap-2 rounded-lg bg-rose-500/10 px-2.5 py-1.5">
            <span className="text-[11px] text-rose-500">
              只删除索引，不会动硬盘上的文件
            </span>
            <div className="flex shrink-0 items-center gap-1">
              <button
                type="button"
                onClick={() => deleteMutation.mutate(library.id)}
                className="rounded-md bg-rose-500 px-2 py-1 text-[11px] font-medium text-white"
              >
                确认删除
              </button>
              <button
                type="button"
                onClick={() => setPendingDelete(null)}
                className="rounded-md px-2 py-1 text-[11px] text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
              >
                取消
              </button>
            </div>
          </div>
        )}
      </li>
    );
  }

  return (
    <section className="glass rounded-2xl p-5 shadow-lift sm:p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold">书库</h2>
          <p className="mt-1 text-xs text-zinc-500">
            登记容器内的有声书目录，扫描后书籍才会出现在书架。
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreating((open) => !open)}
          className="flex items-center gap-1 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-xs font-medium transition hover:border-brand-500 hover:text-brand-500 dark:border-white/10"
        >
          <Icon name={creating ? "close" : "plus"} className="size-3.5" />
          {creating ? "取消" : "登记书库"}
        </button>
      </div>

      {creating && (
        <div className="mt-4 space-y-2 rounded-xl border border-zinc-200/80 p-3 dark:border-white/10">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="名称，例如「有声书」"
            className={fieldClass}
          />
          <input
            value={rootPath}
            onChange={(event) => setRootPath(event.target.value)}
            placeholder="容器内目录，例如 /audiobooks"
            className={fieldClass}
          />
          <p className="text-[11px] leading-relaxed text-zinc-500">
            Docker 部署时，宿主机的有声书目录已在创建容器时固定挂载到{" "}
            <code className="rounded bg-zinc-100 px-1 dark:bg-white/10">{DEFAULT_ROOT_PATH}</code>
            。这里填写容器内路径：默认为整个挂载目录；填写{" "}
            <code className="rounded bg-zinc-100 px-1 dark:bg-white/10">
              {DEFAULT_ROOT_PATH}/子目录
            </code>{" "}
            可单独登记子书库。裸机部署请改成实际目录。
          </p>
          {formError && <p className="text-[11px] text-rose-500">{formError}</p>}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setCreating(false);
                setFormError(null);
              }}
              className="rounded-lg px-3 py-1.5 text-xs text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
            >
              取消
            </button>
            <button
              type="button"
              onClick={() => createMutation.mutate()}
              disabled={!name.trim() || !rootPath.trim() || createMutation.isPending}
              className="rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-medium text-ink-950 disabled:opacity-40"
            >
              {createMutation.isPending ? "登记中…" : "登记"}
            </button>
          </div>
        </div>
      )}

      {actionError && (
        <p className="mt-3 rounded-lg bg-rose-500/10 px-2.5 py-1.5 text-[11px] text-rose-500">
          {actionError}
        </p>
      )}

      <ul className="mt-4 space-y-2">
        {librariesQuery.isPending && (
          <li className="py-6 text-center text-xs text-zinc-500">加载中…</li>
        )}
        {librariesQuery.isSuccess && libraries.length === 0 && (
          <li className="rounded-xl border border-dashed border-zinc-200 px-4 py-8 text-center text-xs text-zinc-500 dark:border-white/10">
            还没有书库，点右上角「登记书库」添加
          </li>
        )}
        {libraries.map(renderRow)}
      </ul>
    </section>
  );
}
