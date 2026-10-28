import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api } from "../api/endpoints";
import BookRow from "../components/shelf/BookRow";
import { Icon } from "../components/ui/Icon";
import { formatCount } from "../lib/format";
import { useDebouncedValue } from "../lib/useDebouncedValue";

const PAGE_SIZE = 50;

export default function Search() {
  const [keyword, setKeyword] = useState("");
  const debounced = useDebouncedValue(keyword, 300);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const term = debounced.trim();
  const result = useQuery({
    queryKey: ["search", term],
    queryFn: () => api.books({ q: term, page_size: PAGE_SIZE }),
    enabled: term.length > 0,
  });

  const items = result.data?.items ?? [];
  const total = result.data?.total ?? 0;

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">搜索</h1>
        <p className="mt-1 text-sm text-zinc-500">
          按书名、作者或系列查找，输入即搜。
        </p>
      </header>

      <div className="relative">
        <Icon
          name="search"
          className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-zinc-400"
        />
        <input
          ref={inputRef}
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder="书名、作者、系列…"
          aria-label="搜索书籍"
          className="h-11 w-full rounded-xl border border-white/70 bg-white/70 pl-10 pr-10 text-sm outline-none backdrop-blur-md transition focus:border-brand-500 dark:border-white/10 dark:bg-white/[0.06]"
        />
        {keyword && (
          <button
            type="button"
            onClick={() => {
              setKeyword("");
              inputRef.current?.focus();
            }}
            aria-label="清空"
            className="absolute right-2 top-1/2 flex size-7 -translate-y-1/2 items-center justify-center rounded-full text-zinc-400 transition hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-white/10 dark:hover:text-zinc-200"
          >
            <Icon name="close" className="size-3.5" />
          </button>
        )}
      </div>

      {!term && (
        <div className="rounded-2xl border border-dashed border-zinc-200 px-6 py-14 text-center dark:border-white/10">
          <Icon name="search" className="mx-auto size-6 text-zinc-400" />
          <p className="mt-3 text-sm text-zinc-500">输入关键词开始搜索</p>
          <p className="mt-1 text-xs text-zinc-400">
            支持中文书名、作者名与系列名，例如「间客」「猫腻」
          </p>
        </div>
      )}

      {term && result.isPending && (
        <p className="py-8 text-center text-sm text-zinc-500">搜索中…</p>
      )}

      {term && result.isError && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 px-4 py-3 text-sm text-rose-500">
          搜索失败，请稍后重试。
        </div>
      )}

      {term && result.isSuccess && items.length === 0 && (
        <div className="rounded-2xl border border-dashed border-zinc-200 px-6 py-14 text-center dark:border-white/10">
          <p className="text-sm text-zinc-500">没有找到与「{term}」相关的书</p>
          <p className="mt-1 text-xs text-zinc-400">换个关键词，或检查书库是否已扫描</p>
        </div>
      )}

      {term && result.isSuccess && items.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between text-xs text-zinc-500">
            <span>
              命中 <span className="text-zinc-800 dark:text-zinc-200">{formatCount(total)}</span> 本
            </span>
            {total > PAGE_SIZE && (
              <span>仅显示前 {PAGE_SIZE} 条，细化关键词可缩小范围</span>
            )}
          </div>

          <div className="space-y-2">
            {items.map((book) => (
              <BookRow key={book.id} book={book} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
