import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import Cover from "../components/ui/Cover";
import { Icon } from "../components/ui/Icon";
import { formatCount } from "../lib/format";

export default function Collections() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const collectionsQuery = useQuery({
    queryKey: ["collections"],
    queryFn: () => api.collections(),
  });

  const createMutation = useMutation({
    mutationFn: () => api.createCollection(name.trim()),
    onSuccess: () => {
      setCreating(false);
      setName("");
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "创建书单失败");
    },
  });

  const collections = collectionsQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">书单</h1>
          <p className="mt-1 text-sm text-zinc-500">
            把想听的按主题收在一起；书单只有自己可见，播放进度仍按书籍同步。
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setCreating((value) => !value);
            setError(null);
          }}
          className="btn-gradient inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium"
        >
          <Icon name={creating ? "close" : "plus"} className="size-4" />
          {creating ? "取消" : "新建书单"}
        </button>
      </header>

      {creating && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (name.trim()) createMutation.mutate();
          }}
          className="glass flex flex-col gap-3 rounded-card p-4 sm:flex-row sm:items-center"
        >
          <input
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={64}
            placeholder="书单名称，例如：睡前推理"
            className="h-10 min-w-0 flex-1 rounded-lg border border-zinc-200 bg-white px-3 text-sm outline-none transition focus:border-brand-500 dark:border-white/10 dark:bg-ink-950"
          />
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={!name.trim() || createMutation.isPending}
              className="inline-flex h-10 items-center gap-1.5 rounded-lg bg-brand-500 px-4 text-sm font-medium text-ink-950 transition hover:bg-brand-400 disabled:opacity-40"
            >
              {createMutation.isPending ? "创建中…" : "创建"}
            </button>
            <button
              type="button"
              onClick={() => {
                setCreating(false);
                setName("");
                setError(null);
              }}
              className="h-10 rounded-lg border border-zinc-200 px-4 text-sm text-zinc-600 transition hover:border-brand-500/40 hover:text-brand-500 dark:border-white/10 dark:text-zinc-300"
            >
              取消
            </button>
          </div>
        </form>
      )}

      {error && (
        <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-500">{error}</p>
      )}

      {collectionsQuery.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div
              key={index}
              className="aspect-[4/3] animate-pulse rounded-card bg-zinc-200/70 dark:bg-white/5"
            />
          ))}
        </div>
      ) : collectionsQuery.isError ? (
        <div className="rounded-card border border-dashed border-zinc-300 px-6 py-12 text-center dark:border-white/10">
          <p className="text-sm text-zinc-500">
            {collectionsQuery.error instanceof ApiError
              ? collectionsQuery.error.message
              : "书单加载失败，请稍后重试"}
          </p>
        </div>
      ) : collections.length === 0 ? (
        <div className="glass rounded-card px-6 py-14 text-center">
          <span className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-brand-500/10 text-brand-500">
            <Icon name="booklist" />
          </span>
          <h2 className="mt-4 text-base font-semibold">还没有书单</h2>
          <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-zinc-500">
            新建一个书单，然后在书籍详情页点「加入书单」。适合整理专题、系列和待听清单。
          </p>
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="mt-5 inline-flex items-center gap-2 rounded-full border border-brand-500/40 px-4 py-2 text-sm text-brand-500 transition hover:bg-brand-500/10"
          >
            <Icon name="plus" className="size-4" />
            创建第一个书单
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {collections.map((collection) => (
            <Link
              key={collection.id}
              to={`/collections/${collection.id}`}
              className="group overflow-hidden rounded-card border border-white/70 bg-white/70 backdrop-blur-md transition duration-300 hover:-translate-y-0.5 hover:border-brand-500/40 hover:shadow-glow dark:border-white/10 dark:bg-white/[0.045]"
            >
              <div className="relative aspect-[4/3] overflow-hidden bg-gradient-to-br from-brand-500/30 via-indigo-500/20 to-fuchsia-500/20">
                <Cover
                  book={{
                    id: 0,
                    title: collection.name,
                    cover_url: collection.cover_url,
                  }}
                  className="size-full transition duration-500 group-hover:scale-[1.03]"
                  textClassName="text-5xl"
                />
                <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/65 to-transparent px-3 pb-2.5 pt-10 text-xs text-white/90">
                  {formatCount(collection.book_count)} 本书
                </span>
              </div>
              <div className="flex items-center justify-between gap-3 p-3.5">
                <div className="min-w-0">
                  <h2 className="truncate text-sm font-semibold">{collection.name}</h2>
                  <p className="mt-0.5 text-[11px] text-zinc-500">
                    创建于 {new Date(collection.created_at * 1000).toLocaleDateString()}
                  </p>
                </div>
                <Icon
                  name="chevronRight"
                  className="size-4 shrink-0 text-zinc-400 transition group-hover:translate-x-0.5 group-hover:text-brand-500"
                />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
