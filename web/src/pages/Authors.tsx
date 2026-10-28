import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/endpoints";
import SkeletonCard from "../components/shelf/SkeletonCard";
import Cover from "../components/ui/Cover";
import { Icon } from "../components/ui/Icon";
import { formatCount, formatDuration } from "../lib/format";
import { useDebouncedValue } from "../lib/useDebouncedValue";

/**
 * 作者视图：按 `GET /authors` 聚合展示，点卡片进书库并按作者筛选。
 *
 * 与系列不同，作者没有卷号也没有「折叠文件夹」的语义，所以单独一页更直观。
 */
export default function Authors() {
  const [keyword, setKeyword] = useState("");
  const debounced = useDebouncedValue(keyword, 250);

  const authorsQuery = useQuery({
    queryKey: ["authors"],
    queryFn: api.authors,
    staleTime: 60_000,
  });

  const authors = useMemo(() => {
    const items = authorsQuery.data?.items ?? [];
    const needle = debounced.trim().toLowerCase();
    if (!needle) return items;
    return items.filter((item) => item.name.toLowerCase().includes(needle));
  }, [authorsQuery.data, debounced]);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">作者</h1>
          <p className="mt-1 text-sm text-zinc-500">
            {authorsQuery.isLoading
              ? "正在统计作者…"
              : `共 ${formatCount(authors.length)} 位作者`}
          </p>
        </div>

        <label className="flex items-center gap-2 rounded-full border border-zinc-200 px-3 py-1.5 dark:border-white/10">
          <Icon name="search" className="size-3.5 text-zinc-400" />
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="筛选作者"
            aria-label="筛选作者"
            className="w-32 bg-transparent text-xs outline-none placeholder:text-zinc-400 sm:w-40"
          />
        </label>
      </header>

      {authorsQuery.isLoading ? (
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(150px,1fr))]">
          {Array.from({ length: 8 }).map((_, index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      ) : authors.length === 0 ? (
        <div className="rounded-card border border-dashed border-zinc-300 px-6 py-12 text-center dark:border-white/10">
          <p className="text-sm text-zinc-500">
            {keyword.trim() ? "没有匹配的作者" : "还没有作者信息"}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(150px,1fr))]">
          {authors.map((item) => (
            <Link
              key={item.name}
              to={`/library?author=${encodeURIComponent(item.name)}`}
              className="group block"
            >
              <div className="relative overflow-hidden rounded-card shadow-card transition group-hover:-translate-y-0.5 group-hover:shadow-lift">
                <Cover
                  book={{
                    id: item.cover_book_id ?? 0,
                    title: item.name,
                    cover_url: item.cover_url,
                  }}
                  size="thumb"
                  className="aspect-square w-full"
                  textClassName="text-4xl"
                />
                <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent px-2 pb-1.5 pt-6 text-[10px] text-white/90">
                  {formatCount(item.book_count)} 本
                </span>
              </div>
              <p className="mt-2 truncate text-sm font-medium">{item.name}</p>
              <p className="mt-0.5 text-[11px] text-zinc-500">
                {formatDuration(item.total_duration_sec)}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
