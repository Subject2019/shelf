import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import { api } from "../../api/endpoints";
import type { CollectionSummary } from "../../api/types";
import { Icon } from "../ui/Icon";

interface CollectionPickerProps {
  bookId: number;
  onClose: () => void;
}

/** 书籍详情里的「加入书单」弹层：勾选即加入，再点一次移出。 */
export default function CollectionPicker({ bookId, onClose }: CollectionPickerProps) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const collectionsQuery = useQuery({
    queryKey: ["collections", bookId],
    queryFn: () => api.collections(bookId),
  });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const toggleMutation = useMutation({
    mutationFn: async (collection: CollectionSummary) => {
      if (collection.contains_book) {
        await api.removeBookFromCollection(collection.id, bookId);
      } else {
        await api.addBookToCollection(collection.id, bookId);
      }
    },
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "操作失败，请稍后重试");
    },
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const collection = await api.createCollection(name.trim());
      await api.addBookToCollection(collection.id, bookId);
      return collection;
    },
    onSuccess: () => {
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
    <div className="fixed inset-0 z-50 flex items-end justify-center p-3 sm:items-center sm:p-6">
      <button
        type="button"
        aria-label="关闭"
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-ink-950/55 backdrop-blur-sm"
      />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="collection-picker-title"
        className="relative flex max-h-[80dvh] w-full max-w-md flex-col overflow-hidden rounded-2xl border border-white/70 bg-white shadow-lift dark:border-white/10 dark:bg-ink-950"
      >
        <header className="flex items-center justify-between border-b border-zinc-200/70 px-4 py-3 dark:border-white/10">
          <div>
            <h2 id="collection-picker-title" className="text-sm font-semibold">
              加入书单
            </h2>
            <p className="mt-0.5 text-[11px] text-zinc-500">勾选后立即生效</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="flex size-8 items-center justify-center rounded-full text-zinc-500 transition hover:bg-zinc-100 dark:hover:bg-white/5"
          >
            <Icon name="close" className="size-4" />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {collectionsQuery.isLoading ? (
            <div className="space-y-2 p-2">
              {Array.from({ length: 3 }).map((_, index) => (
                <div
                  key={index}
                  className="h-11 animate-pulse rounded-xl bg-zinc-100 dark:bg-white/5"
                />
              ))}
            </div>
          ) : collections.length === 0 ? (
            <p className="px-3 py-8 text-center text-xs text-zinc-500">
              还没有书单，在下面创建一个吧。
            </p>
          ) : (
            <ul className="space-y-1">
              {collections.map((collection) => {
                const pending =
                  toggleMutation.isPending &&
                  toggleMutation.variables?.id === collection.id;
                return (
                  <li key={collection.id}>
                    <button
                      type="button"
                      disabled={pending}
                      onClick={() => toggleMutation.mutate(collection)}
                      className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition hover:bg-zinc-100 disabled:opacity-50 dark:hover:bg-white/5"
                    >
                      <span
                        className={[
                          "flex size-5 shrink-0 items-center justify-center rounded-md border transition",
                          collection.contains_book
                            ? "border-brand-500 bg-brand-500 text-ink-950"
                            : "border-zinc-300 text-transparent dark:border-white/20",
                        ].join(" ")}
                      >
                        <Icon name="check" className="size-3.5" />
                      </span>
                      <span className="min-w-0 flex-1 truncate">{collection.name}</span>
                      <span className="text-[11px] text-zinc-500">
                        {collection.book_count} 本
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <footer className="border-t border-zinc-200/70 p-3 dark:border-white/10">
          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (name.trim()) createMutation.mutate();
            }}
          >
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={64}
              placeholder="新建书单名称"
              className="h-9 min-w-0 flex-1 rounded-lg border border-zinc-200 bg-white px-3 text-sm outline-none transition focus:border-brand-500 dark:border-white/10 dark:bg-ink-950"
            />
            <button
              type="submit"
              disabled={!name.trim() || createMutation.isPending}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand-500 px-3 text-xs font-medium text-ink-950 transition hover:bg-brand-400 disabled:opacity-40"
            >
              <Icon name="plus" className="size-3.5" />
              {createMutation.isPending ? "创建中" : "创建并加入"}
            </button>
          </form>
          {error && <p className="mt-2 text-[11px] text-rose-500">{error}</p>}
        </footer>
      </section>
    </div>
  );
}
