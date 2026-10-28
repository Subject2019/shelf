import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { Link, useSearchParams } from "react-router-dom";

import type { Book } from "../api/types";
import { api, type BookFilter, type BookSort } from "../api/endpoints";
import BookCard from "../components/shelf/BookCard";
import BookRow from "../components/shelf/BookRow";
import FilterBar from "../components/shelf/FilterBar";
import {
  SeriesFolderCard,
  SeriesFolderRow,
  SeriesShelf,
} from "../components/shelf/SeriesFolder";
import SkeletonCard from "../components/shelf/SkeletonCard";
import { Icon } from "../components/ui/Icon";
import { formatCount } from "../lib/format";
import { useDebouncedValue } from "../lib/useDebouncedValue";
import { useAuth } from "../store/auth";

const OPEN_SERIES_KEY = "echoshelf.open_series";

/** 书架格子：单独一本书，或折叠起来的系列 */
type ShelfEntry =
  | { kind: "book"; book: Book }
  | { kind: "series"; name: string; books: Book[] };

type View = "grid" | "list";

const VIEWS = [
  { value: "grid", icon: "grid", label: "网格" },
  { value: "list", icon: "list", label: "列表" },
] as const;

export default function Library() {
  const [libraryId, setLibraryId] = useState<number | undefined>(undefined);
  const [keyword, setKeyword] = useState("");
  const [filter, setFilter] = useState<BookFilter>("all");
  const [sort, setSort] = useState<BookSort>("added_desc");
  const [view, setView] = useState<View>("grid");
  // 外层网格当前列数：系列展开面板的 span 不能超过它，否则手机上会横向溢出
  const gridRef = useRef<HTMLDivElement | null>(null);
  const [gridColumns, setGridColumns] = useState(1);
  // 系列作为「虚拟文件夹」：URL 带 ?series=xxx 即可分享/刷新保持
  const [searchParams, setSearchParams] = useSearchParams();
  const series = searchParams.get("series") ?? undefined;
  // 作者也是一层「虚拟文件夹」：从 /authors 点进来带 ?author=xxx
  const author = searchParams.get("author") ?? undefined;

  const debouncedKeyword = useDebouncedValue(keyword, 300);
  // 管理员能看到被隐藏的书（带「已隐藏」角标），普通用户完全不可见
  const isAdmin = useAuth((state) => state.user?.role === "admin");

  const librariesQuery = useQuery({
    queryKey: ["libraries"],
    queryFn: api.libraries,
    staleTime: 60_000,
  });

  const seriesQuery = useQuery({
    queryKey: ["series"],
    queryFn: api.series,
    staleTime: 60_000,
  });

  const booksQuery = useInfiniteQuery({
    queryKey: [
      "books",
      "library",
      libraryId ?? null,
      debouncedKeyword,
      filter,
      sort,
      series ?? null,
      author ?? null,
      isAdmin,
    ],
    queryFn: ({ pageParam }) =>
      api.books({
        library_id: libraryId,
        q: debouncedKeyword.trim() || undefined,
        // 作者与系列互斥：从作者页进来时只按作者筛
        author,
        series: author ? undefined : series,
        filter,
        // 看某个系列时按卷号排，否则跟随用户选择
        sort: series && !author ? "series_asc" : sort,
        page: pageParam,
        page_size: 40,
        include_hidden: isAdmin || undefined,
      }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page * lastPage.page_size < lastPage.total
        ? lastPage.page + 1
        : undefined,
  });

  const books = useMemo(
    () => booksQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [booksQuery.data],
  );
  const total = booksQuery.data?.pages[0]?.total ?? 0;

  const measureColumns = useCallback(() => {
    const node = gridRef.current;
    if (!node) return;
    // span 过的条目会产生 0px 的隐式轨道，只统计有宽度的真实列
    const tracks = getComputedStyle(node)
      .gridTemplateColumns.split(" ")
      .filter((track) => Number.parseFloat(track) > 0);
    if (tracks.length > 0) setGridColumns(tracks.length);
  }, []);

  useEffect(() => {
    measureColumns();
  }, [measureColumns, books.length, view]);

  useEffect(() => {
    const node = gridRef.current;
    if (!node) return;
    const observer = new ResizeObserver(measureColumns);
    observer.observe(node);
    return () => observer.disconnect();
  }, [measureColumns, books.length, view]);

  const { hasNextPage, isFetchingNextPage, fetchNextPage } = booksQuery;
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const node = sentinelRef.current;
    if (!node || !hasNextPage) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && !isFetchingNextPage) {
          void fetchNextPage();
        }
      },
      { rootMargin: "400px 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const libraries = librariesQuery.data?.items ?? [];

  // 系列汇总只用来拿「总卷数 / 总时长 / 封面书」，不再单独占一条
  const seriesMeta = useMemo(() => {
    const map = new Map<
      string,
      { count: number; duration: number; coverUrl: string | null }
    >();
    for (const item of seriesQuery.data?.items ?? []) {
      map.set(item.name, {
        count: item.book_count,
        duration: item.total_duration_sec,
        coverUrl: item.cover_url,
      });
    }
    return map;
  }, [seriesQuery.data]);

  const [openSeries, setOpenSeries] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem(OPEN_SERIES_KEY);
      const parsed: unknown = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed)
        ? parsed.filter((item): item is string => typeof item === "string")
        : [];
    } catch {
      return [];
    }
  });

  // 收起时先播完动画再从状态里移除，避免卷卡"啪"地消失
  const [closingSeries, setClosingSeries] = useState<string | null>(null);

  function commitOpenSeries(next: string[]) {
    setOpenSeries(next);
    try {
      localStorage.setItem(OPEN_SERIES_KEY, JSON.stringify(next));
    } catch {
      // 隐私模式下写不进去就算了
    }
  }

  function toggleSeries(name: string) {
    if (closingSeries === name) return;

    if (openSeries.includes(name)) {
      setClosingSeries(name);
      window.setTimeout(() => {
        commitOpenSeries(openSeries.filter((item) => item !== name));
        setClosingSeries(null);
      }, 300);
      return;
    }
    commitOpenSeries([...openSeries, name]);
  }

  // 正在按系列/作者筛选或搜索时平铺，否则「筛出来的书又被塞回文件夹」
  const groupSeries = !series && !author && !debouncedKeyword.trim();

  const entries = useMemo<ShelfEntry[]>(() => {
    if (!groupSeries) {
      return books.map((book) => ({ kind: "book" as const, book }));
    }

    const list: ShelfEntry[] = [];
    const positions = new Map<string, number>();
    for (const book of books) {
      const name = book.series_name;
      const meta = name ? seriesMeta.get(name) : undefined;
      // 单卷系列折叠没有意义，直接平铺
      if (!name || !meta || meta.count < 2) {
        list.push({ kind: "book", book });
        continue;
      }

      const at = positions.get(name);
      if (at === undefined) {
        positions.set(name, list.length);
        list.push({ kind: "series", name, books: [book] });
      } else {
        const entry = list[at];
        if (entry.kind === "series") entry.books.push(book);
      }
    }

    // 展开后按卷号排，而不是按「最近添加」
    for (const entry of list) {
      if (entry.kind !== "series") continue;
      entry.books.sort(
        (a, b) => (a.series_index ?? 999) - (b.series_index ?? 999),
      );
    }
    return list;
  }, [books, groupSeries, seriesMeta]);

  const hasFilter =
    Boolean(libraryId) ||
    Boolean(keyword.trim()) ||
    filter !== "all" ||
    Boolean(series) ||
    Boolean(author);

  function resetFilters() {
    setLibraryId(undefined);
    setKeyword("");
    setFilter("all");
    setSearchParams({});
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">书库</h1>
          <p className="mt-1 text-sm text-zinc-500">
            {booksQuery.isLoading
              ? "正在读取书籍…"
              : `共 ${formatCount(total)} 本${hasFilter ? "（已筛选）" : ""}`}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/authors"
            className="flex items-center gap-1.5 rounded-full border border-zinc-200 px-3 py-1.5 text-xs text-zinc-600 transition hover:border-brand-400/50 hover:text-brand-500 dark:border-white/10 dark:text-zinc-300"
          >
            <Icon name="user" className="size-3.5" />
            作者
          </Link>
          <div className="flex items-center gap-1 rounded-full border border-zinc-200 p-1 dark:border-white/10">
            {VIEWS.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => setView(item.value)}
              aria-label={item.label}
              aria-pressed={view === item.value}
              className={[
                "flex size-8 items-center justify-center rounded-full transition",
                view === item.value
                  ? "bg-brand-500 text-ink-950"
                  : "text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100",
              ].join(" ")}
            >
                <Icon name={item.icon} className="size-4" />
              </button>
            ))}
          </div>
        </div>
      </header>

      {series && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-brand-500/30 bg-brand-500/10 px-3 py-2">
          <Icon name="collections" className="size-3.5 text-brand-500" />
          <span className="text-xs font-medium text-brand-500">系列：{series}</span>
          <button
            type="button"
            onClick={() => setSearchParams({})}
            className="ml-auto text-[11px] text-zinc-600 transition hover:text-brand-500 dark:text-zinc-400"
          >
            查看全部书
          </button>
        </div>
      )}

      {author && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-brand-500/30 bg-brand-500/10 px-3 py-2">
          <Icon name="user" className="size-3.5 text-brand-500" />
          <span className="text-xs font-medium text-brand-500">
            作者：{author}
          </span>
          <Link
            to="/authors"
            className="ml-auto text-[11px] text-zinc-600 transition hover:text-brand-500 dark:text-zinc-400"
          >
            返回作者列表
          </Link>
          <button
            type="button"
            onClick={() => setSearchParams({})}
            className="text-[11px] text-zinc-600 transition hover:text-brand-500 dark:text-zinc-400"
          >
            查看全部书
          </button>
        </div>
      )}

      <FilterBar
        keyword={keyword}
        onKeywordChange={setKeyword}
        libraryId={libraryId}
        onLibraryChange={setLibraryId}
        libraries={libraries}
        filter={filter}
        onFilterChange={setFilter}
        sort={sort}
        onSortChange={setSort}
      />

      {booksQuery.isError ? (
        <div className="rounded-card border border-dashed border-zinc-300 px-6 py-12 text-center dark:border-white/10">
          <p className="text-sm text-zinc-500">书籍加载失败</p>
          <button
            type="button"
            onClick={() => void booksQuery.refetch()}
            className="mt-3 inline-flex items-center gap-2 rounded-full bg-brand-500 px-4 py-2 text-xs font-medium text-ink-950 transition hover:bg-brand-400"
          >
            <Icon name="refresh" className="size-3.5" />
            重试
          </button>
        </div>
      ) : booksQuery.isLoading ? (
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(150px,1fr))]">
          {Array.from({ length: 10 }).map((_, index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      ) : books.length === 0 ? (
        <div className="rounded-card border border-dashed border-zinc-300 px-6 py-14 text-center dark:border-white/10">
          <p className="text-sm text-zinc-500">
            {hasFilter ? "没有符合条件的书" : "书架还是空的"}
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            {hasFilter ? "换个关键词或清除筛选试试" : "先在书库里登记目录并触发扫描"}
          </p>
          {hasFilter && (
            <button
              type="button"
              onClick={resetFilters}
              className="mt-3 text-xs text-brand-500 hover:underline"
            >
              清除筛选
            </button>
          )}
        </div>
      ) : view === "grid" ? (
        <div
          ref={gridRef}
          className="grid gap-5 [grid-template-columns:repeat(auto-fill,minmax(150px,1fr))]"
        >
          {entries.map((entry) => {
            if (entry.kind === "book") {
              return <BookCard key={`book-${entry.book.id}`} book={entry.book} />;
            }

            const meta = seriesMeta.get(entry.name);
            const total = meta?.count ?? entry.books.length;
            const durationSec = meta?.duration ?? 0;
            const coverUrl = meta?.coverUrl ?? null;

            // 展开时整行展示：外框把这一系列圈起来，和后面的单本彻底分开
            if (
              openSeries.includes(entry.name) ||
              closingSeries === entry.name
            ) {
              return (
                <SeriesShelf
                  key={`shelf-${entry.name}`}
                  name={entry.name}
                  books={entry.books}
                  total={total}
                  durationSec={durationSec}
                  coverUrl={coverUrl}
                  closing={closingSeries === entry.name}
                  columns={gridColumns}
                  onCollapse={() => toggleSeries(entry.name)}
                  onOpenAll={() => setSearchParams({ series: entry.name })}
                />
              );
            }

            return (
              <SeriesFolderCard
                key={`series-${entry.name}`}
                name={entry.name}
                books={entry.books}
                total={total}
                durationSec={durationSec}
                coverUrl={coverUrl}
                onToggle={() => toggleSeries(entry.name)}
                onOpenAll={() => setSearchParams({ series: entry.name })}
              />
            );
          })}
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map((entry) =>
            entry.kind === "book" ? (
              <BookRow key={`book-${entry.book.id}`} book={entry.book} />
            ) : (
              <Fragment key={`series-${entry.name}`}>
                <SeriesFolderRow
                  name={entry.name}
                  books={entry.books}
                  total={seriesMeta.get(entry.name)?.count ?? entry.books.length}
                  durationSec={seriesMeta.get(entry.name)?.duration ?? 0}
                  coverUrl={seriesMeta.get(entry.name)?.coverUrl ?? null}
                  onToggle={() => toggleSeries(entry.name)}
                  onOpenAll={() => setSearchParams({ series: entry.name })}
                />
                {(openSeries.includes(entry.name) ||
                  closingSeries === entry.name) && (
                  <div
                    className={[
                      "ml-4 border-l border-zinc-200/70 pl-3 dark:border-white/10",
                      closingSeries === entry.name
                        ? "folder-card-out"
                        : "folder-card-in",
                    ].join(" ")}
                  >
                    {entry.books.map((book, index) => (
                      <div
                        key={`book-${book.id}`}
                        className={
                          closingSeries === entry.name
                            ? "folder-card-out"
                            : "folder-card-in"
                        }
                        style={{ "--card-index": index } as CSSProperties}
                      >
                        <BookRow book={book} />
                      </div>
                    ))}
                  </div>
                )}
              </Fragment>
            ),
          )}
        </div>
      )}

      <div ref={sentinelRef} className="h-px" aria-hidden="true" />

      {isFetchingNextPage && (
        <p className="text-center text-xs text-zinc-500">正在加载更多…</p>
      )}
      {hasNextPage && !isFetchingNextPage && (
        <div className="text-center">
          <button
            type="button"
            onClick={() => void fetchNextPage()}
            className="rounded-full border border-zinc-200 px-4 py-2 text-xs text-zinc-600 transition hover:border-brand-500/40 hover:text-brand-500 dark:border-white/10 dark:text-zinc-400"
          >
            加载更多
          </button>
        </div>
      )}
      {!hasNextPage && books.length > 0 && (
        <p className="text-center text-xs text-zinc-500">已经到底了</p>
      )}
    </div>
  );
}
