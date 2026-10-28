import { useQuery } from "@tanstack/react-query";

import { api } from "../../api/endpoints";
import { formatDuration } from "../../lib/format";
import { Icon } from "../ui/Icon";

/**
 * 首页收听统计：今日 / 连续天数 / 累计 + 最近 7 天柱状。
 *
 * 数据来自 `GET /stats`，由 `PUT /progress` 的自然播放推进累积
 * （拖动进度条不计，倍速会折算成真实时长）。
 */
export default function ListeningCard({ enabled }: { enabled: boolean }) {
  const statsQuery = useQuery({
    queryKey: ["stats"],
    queryFn: () => api.stats(7),
    enabled,
    staleTime: 30_000,
  });

  const stats = statsQuery.data;
  const days = stats?.days ?? [];
  const peak = Math.max(1, ...days.map((item) => item.seconds));

  const metrics = [
    {
      label: "今日收听",
      value: stats ? formatDuration(stats.today_sec) : "—",
      hint: stats?.today_sec ? "自然播放累计" : "开始播放即开始统计",
    },
    {
      label: "连续天数",
      value: stats ? `${stats.streak_days} 天` : "—",
      hint: "今天没听也不算断签",
    },
    {
      label: "累计收听",
      value: stats ? formatDuration(stats.total_sec) : "—",
      hint: "全部书籍合计",
    },
  ];

  return (
    <section className="glass rounded-card p-5">
      <header className="flex items-center gap-2">
        <Icon name="headphones" className="size-4 text-brand-500" />
        <h2 className="text-sm font-semibold">收听统计</h2>
        {statsQuery.isError && (
          <span className="text-[11px] text-zinc-500">统计加载失败</span>
        )}
      </header>

      <div className="mt-4 grid grid-cols-3 gap-3">
        {metrics.map((item) => (
          <div key={item.label}>
            <div className="text-[11px] text-zinc-500">{item.label}</div>
            <div className="mt-1 text-xl font-semibold tabular-nums">
              {item.value}
            </div>
            <div className="mt-0.5 text-[10px] text-zinc-500">{item.hint}</div>
          </div>
        ))}
      </div>

      <div className="mt-5">
        <div className="flex items-end justify-between">
          <span className="text-[11px] text-zinc-500">最近 7 天</span>
          <span className="text-[10px] text-zinc-400">
            {days.length > 0
              ? `${days[0].day.slice(5)} — ${days[days.length - 1].day.slice(5)}`
              : ""}
          </span>
        </div>
        <div className="mt-2 flex h-16 items-end gap-1.5">
          {days.map((item) => {
            const percent = Math.round((item.seconds / peak) * 100);
            return (
              <div
                key={item.day}
                className="group flex h-full flex-1 flex-col justify-end"
                title={`${item.day} · ${formatDuration(item.seconds)}`}
              >
                <div
                  className={[
                    "w-full rounded-sm transition",
                    item.seconds > 0
                      ? "bg-brand-500/70 group-hover:bg-brand-500"
                      : "bg-zinc-500/15",
                  ].join(" ")}
                  style={{ height: `${Math.max(item.seconds > 0 ? 8 : 4, percent)}%` }}
                />
              </div>
            );
          })}
        </div>
        <div className="mt-1 flex gap-1.5">
          {days.map((item) => (
            <span
              key={item.day}
              className="flex-1 text-center text-[10px] text-zinc-400"
            >
              {item.day.slice(8)}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
