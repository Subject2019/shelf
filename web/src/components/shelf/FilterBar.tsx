import type { BookFilter, BookSort } from "../../api/endpoints";
import type { Library } from "../../api/types";
import { Icon } from "../ui/Icon";

const FILTERS: { value: BookFilter; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "in_progress", label: "在听" },
  { value: "finished", label: "已听完" },
  { value: "unplayed", label: "未开始" },
];

const SORTS: { value: BookSort; label: string }[] = [
  { value: "added_desc", label: "最近添加" },
  { value: "title_asc", label: "书名" },
  { value: "author_asc", label: "作者" },
  { value: "duration_desc", label: "时长" },
  { value: "progress_desc", label: "最近收听" },
];

const selectClass =
  "h-9 appearance-none rounded-full border border-zinc-200 bg-white pl-3 pr-8 text-xs text-zinc-700 outline-none transition focus:border-brand-500/60 dark:border-white/10 dark:bg-ink-900 dark:text-zinc-200";

interface FilterBarProps {
  keyword: string;
  onKeywordChange: (value: string) => void;
  libraryId: number | undefined;
  onLibraryChange: (value: number | undefined) => void;
  libraries: Library[];
  filter: BookFilter;
  onFilterChange: (value: BookFilter) => void;
  sort: BookSort;
  onSortChange: (value: BookSort) => void;
}

export default function FilterBar({
  keyword,
  onKeywordChange,
  libraryId,
  onLibraryChange,
  libraries,
  filter,
  onFilterChange,
  sort,
  onSortChange,
}: FilterBarProps) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full min-w-0 sm:w-auto sm:max-w-xs sm:flex-1">
          <Icon
            name="search"
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-zinc-400"
          />
          <input
            value={keyword}
            onChange={(event) => onKeywordChange(event.target.value)}
            placeholder="搜索书名、作者、系列"
            className="h-9 w-full rounded-full border border-zinc-200 bg-white pl-9 pr-8 text-xs text-zinc-900 outline-none transition placeholder:text-zinc-400 focus:border-brand-500/60 dark:border-white/10 dark:bg-ink-900 dark:text-zinc-100"
          />
          {keyword && (
            <button
              type="button"
              onClick={() => onKeywordChange("")}
              aria-label="清除搜索"
              className="absolute right-2 top-1/2 flex size-5 -translate-y-1/2 items-center justify-center rounded-full text-zinc-400 transition hover:text-brand-500"
            >
              <Icon name="close" className="size-3.5" />
            </button>
          )}
        </div>

        <div className="flex w-full items-center gap-2 sm:w-auto">
          <div className="relative flex-1 sm:flex-none">
            <select
              value={libraryId ?? ""}
              onChange={(event) =>
                onLibraryChange(event.target.value ? Number(event.target.value) : undefined)
              }
              aria-label="选择书库"
              className={`${selectClass} w-full sm:w-auto`}
            >
              <option value="">全部书库</option>
              {libraries.map((library) => (
                <option key={library.id} value={library.id}>
                  {library.name}（{library.book_count}）
                </option>
              ))}
            </select>
            <Icon
              name="chevronDown"
              className="pointer-events-none absolute right-2.5 top-1/2 size-3.5 -translate-y-1/2 text-zinc-400"
            />
          </div>

          <div className="relative flex-1 sm:flex-none">
            <select
              value={sort}
              onChange={(event) => onSortChange(event.target.value as BookSort)}
              aria-label="排序方式"
              className={`${selectClass} w-full sm:w-auto`}
            >
              {SORTS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
            <Icon
              name="chevronDown"
              className="pointer-events-none absolute right-2.5 top-1/2 size-3.5 -translate-y-1/2 text-zinc-400"
            />
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        {FILTERS.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => onFilterChange(item.value)}
            aria-pressed={filter === item.value}
            className={[
              "rounded-full px-3.5 py-1.5 text-xs font-medium transition",
              filter === item.value
                ? "bg-brand-500/[0.12] text-brand-500 ring-1 ring-brand-500/30"
                : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-white/5 dark:hover:text-zinc-100",
            ].join(" ")}
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}
