import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../api/endpoints";
import BookCard from "../components/shelf/BookCard";
import ListeningCard from "../components/stats/ListeningCard";
import { Icon } from "../components/ui/Icon";
import { formatCount } from "../lib/format";
import { useAuth } from "../store/auth";

const STEPS = [
  { title: "登记书库", detail: "填一个容器内的有声书目录（Docker 默认 /audiobooks），扫描全程只读。" },
  { title: "自动入库", detail: "识别标签、CUE 与内嵌章节；重扫幂等，不会产生重复书籍。" },
  { title: "多端续听", detail: "网页与手机共享同一份进度，换设备接着上次的位置。" },
];

export default function Home() {
  const status = useAuth((state) => state.status);
  const user = useAuth((state) => state.user);

  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
    retry: 1,
  });

  const recent = useQuery({
    queryKey: ["books", "recent"],
    queryFn: () => api.books({ page_size: 8, sort: "added_desc" }),
    enabled: status === "authenticated",
  });

  const online = health.data?.status === "ok";
  const books = recent.data?.items ?? [];

  const cards = [
    {
      label: "书籍",
      value: health.data ? formatCount(health.data.books) : "—",
      hint: "已入库",
    },
    {
      label: "书库",
      value: health.data ? formatCount(health.data.libraries) : "—",
      hint: "已登记",
    },
    {
      label: "数据库",
      value: health.data?.db === "ok" ? "正常" : "—",
      hint: "SQLite · WAL",
    },
    {
      label: "音频引擎",
      value: health.data?.ffmpeg ? "可用" : "缺失",
      hint: "ffmpeg / ffprobe",
    },
  ];

  return (
    <div className="space-y-8">
      <section className="relative overflow-hidden rounded-2xl border border-white/70 bg-white/65 px-6 py-8 shadow-lift backdrop-blur-xl backdrop-saturate-150 dark:border-white/10 dark:bg-white/[0.04] sm:px-10 sm:py-12">
        <div className="pointer-events-none absolute inset-0 bg-brand-fade" aria-hidden="true" />
        <div
          className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-brand-500/20 blur-3xl"
          aria-hidden="true"
        />
        <div className="relative max-w-2xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 text-xs font-medium text-brand-500 backdrop-blur-sm">
            <span
              className={`size-1.5 rounded-full ${online ? "bg-emerald-400" : "bg-amber-400"}`}
            />
            {online ? "服务在线" : health.isLoading ? "正在连接服务" : "服务未连接"}
          </span>
          <h1 className="mt-5 text-3xl font-semibold tracking-tight sm:text-4xl">
            把有声书
            <span className="text-gradient">搬回自己的书架</span>
          </h1>
          <div className="mt-7 flex flex-wrap items-center gap-3">
            {status === "authenticated" ? (
              <Link
                to="/library"
                className="btn-gradient inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium"
              >
                进入书库
                <Icon name="arrowRight" className="size-4" />
              </Link>
            ) : (
              <Link
                to="/login"
                className="btn-gradient inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium"
              >
                登录开始
                <Icon name="arrowRight" className="size-4" />
              </Link>
            )}
            <a
              href="#status"
              className="inline-flex items-center gap-2 rounded-full border border-zinc-300 px-5 py-2.5 text-sm text-zinc-700 transition hover:border-brand-500/40 hover:text-brand-500 dark:border-white/10 dark:text-zinc-300"
            >
              查看服务状态
            </a>
          </div>
          {status === "authenticated" && user && (
            <p className="mt-4 text-xs text-zinc-500">
              已登录为 {user.display_name ?? user.username}
            </p>
          )}
        </div>
      </section>

      <section id="status" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <div
            key={card.label}
            className="glass rounded-card p-4"
          >
            <div className="text-xs text-zinc-500">{card.label}</div>
            <div className="mt-1 text-2xl font-semibold tabular-nums">{card.value}</div>
            <div className="mt-1 text-[11px] text-zinc-500">{card.hint}</div>
          </div>
        ))}
      </section>

      {status === "authenticated" && <ListeningCard enabled />}

      <section className="space-y-3">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">最近添加</h2>
            <p className="text-xs text-zinc-500">扫描入库后按添加时间倒序</p>
          </div>
          {status === "authenticated" && (
            <Link to="/library" className="text-xs text-brand-500 hover:underline">
              全部书籍
            </Link>
          )}
        </div>

        {status !== "authenticated" ? (
          <div className="rounded-card border border-dashed border-zinc-300 px-6 py-10 text-center dark:border-white/10">
            <p className="text-sm text-zinc-500">登录后查看书架与收听进度</p>
          </div>
        ) : books.length > 0 ? (
          <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(150px,1fr))]">
            {books.map((book) => (
              <BookCard key={book.id} book={book} />
            ))}
          </div>
        ) : (
          <div className="rounded-card border border-dashed border-zinc-300 px-6 py-10 text-center dark:border-white/10">
            <p className="text-sm text-zinc-500">书架还是空的</p>
            <p className="mt-1 text-xs text-zinc-500">
              在「书库」里登记一个音频目录并触发扫描即可入库。
            </p>
          </div>
        )}
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        {STEPS.map((step, index) => (
          <div
            key={step.title}
            className="glass rounded-card p-5"
          >
            <span className="text-xs font-semibold text-brand-500">0{index + 1}</span>
            <h3 className="mt-2 text-sm font-medium">{step.title}</h3>
            <p className="mt-1 text-xs leading-5 text-zinc-500">{step.detail}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
