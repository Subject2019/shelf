import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import BookCard from "../components/shelf/BookCard";
import Cover from "../components/ui/Cover";
import { Icon } from "../components/ui/Icon";
import { formatCount } from "../lib/format";

export default function CollectionDetail() {
  const { collectionId } = useParams();
  const id = Number(collectionId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const collectionQuery = useQuery({
    queryKey: ["collection", id],
    queryFn: () => api.collectionDetail(id),
    enabled: Number.isFinite(id) && id > 0,
  });

  const renameMutation = useMutation({
    mutationFn: () => api.updateCollection(id, name.trim()),
    onSuccess: () => {
      setEditing(false);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["collection", id] });
      void queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "重命名失败");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteCollection(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["collections"] });
      navigate("/collections", { replace: true });
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "删除书单失败");
    },
  });

  const removeMutation = useMutation({
    mutationFn: (bookId: number) => api.removeBookFromCollection(id, bookId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["collection", id] });
      void queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "移出书单失败");
    },
  });

  if (collectionQuery.isLoading) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="h-5 w-24 animate-pulse rounded bg-zinc-200/70 dark:bg-white/5" />
        <div className="flex gap-5">
          <div className="size-28 animate-pulse rounded-2xl bg-zinc-200/70 dark:bg-white/5" />
          <div className="flex-1 space-y-3 py-2">
            <div className="h-7 w-1/2 animate-pulse rounded bg-zinc-200/70 dark:bg-white/5" />
            <div className="h-4 w-1/3 animate-pulse rounded bg-zinc-200/70 dark:bg-white/5" />
          </div>
        </div>
      </div>
    );
  }

  if (collectionQuery.isError || !collectionQuery.data) {
    return (
      <div className="mx-auto max-w-md py-16 text-center">
        <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-brand-500/10 text-brand-500">
          <Icon name="booklist" />
        </div>
        <h1 className="mt-5 text-lg font-semibold">找不到这个书单</h1>
        <p className="mt-2 text-sm text-zinc-500">
          {collectionQuery.error instanceof ApiError
            ? collectionQuery.error.message
            : "它可能已被删除"}
        </p>
        <Link
          to="/collections"
          className="btn-gradient mt-6 inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium"
        >
          返回书单
        </Link>
      </div>
    );
  }

  const collection = collectionQuery.data;

  return (
    <div className="mx-auto max-w-5xl space-y-7">
      <Link
        to="/collections"
        className="inline-flex items-center gap-1.5 text-xs text-zinc-500 transition hover:text-brand-500"
      >
        <Icon name="chevronLeft" className="size-4" />
        返回书单
      </Link>

      <header className="flex flex-col gap-5 sm:flex-row sm:items-center">
        <Cover
          book={{
            id: 0,
            title: collection.name,
            cover_url: collection.cover_url,
          }}
          className="size-28 shrink-0 overflow-hidden rounded-2xl shadow-card"
          textClassName="text-3xl"
        />

        <div className="min-w-0 flex-1">
          {editing ? (
            <form
              className="flex flex-wrap items-center gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                if (name.trim()) renameMutation.mutate();
              }}
            >
              <input
                autoFocus
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={64}
                className="h-10 min-w-0 flex-1 rounded-lg border border-zinc-200 bg-white px-3 text-lg font-semibold outline-none transition focus:border-brand-500 dark:border-white/10 dark:bg-ink-950"
              />
              <button
                type="submit"
                disabled={!name.trim() || renameMutation.isPending}
                className="h-10 rounded-lg bg-brand-500 px-4 text-sm font-medium text-ink-950 disabled:opacity-40"
              >
                保存
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditing(false);
                  setError(null);
                }}
                className="h-10 rounded-lg border border-zinc-200 px-4 text-sm text-zinc-600 dark:border-white/10 dark:text-zinc-300"
              >
                取消
              </button>
            </form>
          ) : (
            <>
              <h1 className="truncate text-2xl font-semibold tracking-tight">
                {collection.name}
              </h1>
              <p className="mt-1 text-sm text-zinc-500">
                {formatCount(collection.book_count)} 本书 · 创建于{" "}
                {new Date(collection.created_at * 1000).toLocaleDateString()}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setName(collection.name);
                    setEditing(true);
                    setError(null);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 px-3 py-1.5 text-[11px] text-zinc-700 transition hover:border-brand-500/50 hover:text-brand-500 dark:border-white/15 dark:text-zinc-300"
                >
                  <Icon name="edit" className="size-3.5" />
                  重命名
                </button>
                <button
                  type="button"
                  disabled={deleteMutation.isPending}
                  onClick={() => {
                    if (
                      window.confirm(
                        `确定删除书单「${collection.name}」吗？书籍本身不会被删除。`,
                      )
                    ) {
                      deleteMutation.mutate();
                    }
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 px-3 py-1.5 text-[11px] text-zinc-500 transition hover:border-rose-400/50 hover:text-rose-500 disabled:opacity-50 dark:border-white/15"
                >
                  <Icon name="trash" className="size-3.5" />
                  删除书单
                </button>
              </div>
            </>
          )}
          {error && <p className="mt-2 text-[11px] text-rose-500">{error}</p>}
        </div>
      </header>

      {collection.books.length === 0 ? (
        <div className="rounded-card border border-dashed border-zinc-300 px-6 py-14 text-center dark:border-white/10">
          <span className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-brand-500/10 text-brand-500">
            <Icon name="plus" />
          </span>
          <h2 className="mt-4 text-base font-semibold">书单还是空的</h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-zinc-500">
            去书库打开一本书，点「加入书单」就可以把它放进这里。
          </p>
          <Link
            to="/library"
            className="btn-gradient mt-5 inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium"
          >
            去书库挑书
            <Icon name="arrowRight" className="size-4" />
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(150px,1fr))]">
          {collection.books.map((book) => (
            <div key={book.id} className="group relative">
              <BookCard book={book} />
              <button
                type="button"
                disabled={removeMutation.isPending}
                onClick={() => removeMutation.mutate(book.id)}
                aria-label={`把《${book.title}》移出书单`}
                title="移出书单"
                className="absolute right-2 top-2 z-30 flex size-8 items-center justify-center rounded-full bg-black/55 text-white backdrop-blur transition hover:bg-rose-500 focus-visible:opacity-100 disabled:opacity-50 sm:opacity-0 sm:group-hover:opacity-100"
              >
                <Icon name="close" className="size-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
