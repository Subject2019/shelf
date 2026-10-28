import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../api/endpoints";
import AccountSection from "../components/settings/AccountSection";
import DeviceSection from "../components/settings/DeviceSection";
import LibrarySection from "../components/settings/LibrarySection";
import PlaybackSection from "../components/settings/PlaybackSection";
import UserSection from "../components/settings/UserSection";
import { formatCount } from "../lib/format";
import { ACCENTS } from "../styles/accent";
import { useAuth } from "../store/auth";
import { useUi } from "../store/ui";

export default function Settings() {
  const theme = useUi((state) => state.theme);
  const setTheme = useUi((state) => state.setTheme);
  const accent = useUi((state) => state.accent);
  const accentHex = useUi((state) => state.accentHex);
  const setAccent = useUi((state) => state.setAccent);

  const user = useAuth((state) => state.user);
  const status = useAuth((state) => state.status);
  const logout = useAuth((state) => state.logout);

  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    staleTime: 60_000,
  });

  const activeLabel = ACCENTS.find((item) => item.id === accent)?.label ?? "自定义";

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">设置</h1>
        <p className="mt-1 text-sm text-zinc-500">
          外观与播放偏好保存在这台设备的浏览器里，不影响其他设备。
        </p>
      </header>

      <section className="glass rounded-2xl p-5 shadow-lift sm:p-6">
        <h2 className="text-sm font-semibold">外观</h2>

        <div className="mt-5 grid gap-6 sm:grid-cols-2">
          <div>
            <p className="text-xs text-zinc-500">模式</p>
            <div className="mt-2 inline-flex rounded-full border border-zinc-200 p-1 dark:border-white/10">
              {(
                [
                  { value: "dark", label: "深色" },
                  { value: "light", label: "浅色" },
                ] as const
              ).map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setTheme(item.value)}
                  className={[
                    "rounded-full px-4 py-1.5 text-xs font-medium transition",
                    theme === item.value
                      ? "bg-brand-500 text-ink-950"
                      : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100",
                  ].join(" ")}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs text-zinc-500">主题色</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {ACCENTS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  title={item.label}
                  aria-label={item.label}
                  onClick={() => setAccent(item.id)}
                  style={{ backgroundColor: item.hex }}
                  className={[
                    "size-8 rounded-full ring-2 ring-offset-2 ring-offset-white transition dark:ring-offset-ink-900",
                    accent === item.id
                      ? "ring-brand-500"
                      : "ring-transparent hover:ring-zinc-300 dark:hover:ring-white/20",
                  ].join(" ")}
                />
              ))}

              <label className="flex cursor-pointer items-center gap-2 rounded-full border border-zinc-200 px-3 py-1.5 text-xs text-zinc-600 transition hover:border-brand-500/40 hover:text-brand-500 dark:border-white/10 dark:text-zinc-400">
                <input
                  type="color"
                  value={accentHex}
                  onChange={(event) => setAccent("custom", event.target.value)}
                  className="size-5 cursor-pointer rounded-full border-0 bg-transparent p-0"
                  aria-label="自定义主题色"
                />
                自定义
              </label>
            </div>
          </div>
        </div>

        <div className="mt-6 rounded-card border border-zinc-200/70 bg-zinc-50/60 p-4 dark:border-white/5 dark:bg-white/[0.03]">
          <div className="flex items-center justify-between text-xs text-zinc-500">
            <span>预览</span>
            <span>
              {activeLabel} · {accentHex.toUpperCase()}
            </span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="rounded-full bg-brand-500 px-4 py-2 text-sm font-medium text-ink-950"
            >
              主按钮
            </button>
            <span className="rounded-full bg-brand-500/10 px-3 py-1 text-xs font-medium text-brand-500">
              标签
            </span>
            <span className="rounded-full border border-brand-500/40 px-3 py-1 text-xs text-brand-500">
              描边
            </span>
            <div className="h-1.5 w-28 overflow-hidden rounded-full bg-zinc-200 dark:bg-white/10">
              <div className="h-full w-2/3 rounded-full bg-brand-500" />
            </div>
          </div>
        </div>
      </section>

      <PlaybackSection />

      <section className="glass rounded-2xl p-5 shadow-lift sm:p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">账号</h2>
          {user && (
            <button
              type="button"
              onClick={() => void logout()}
              className="text-xs text-zinc-500 transition hover:text-brand-500"
            >
              退出登录
            </button>
          )}
        </div>

        {user ? (
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs text-zinc-500">用户名</dt>
              <dd className="mt-0.5">{user.username}</dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">显示名</dt>
              <dd className="mt-0.5">{user.display_name ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">角色</dt>
              <dd className="mt-0.5">
                {user.role === "admin"
                  ? "管理员"
                  : user.role === "editor"
                    ? "上传者"
                    : "听众"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">可见书库</dt>
              <dd className="mt-0.5">{user.libraries.length} 个</dd>
            </div>
          </dl>
        ) : (
          <p className="mt-3 text-sm text-zinc-500">
            {status === "loading" ? (
              "正在恢复登录状态…"
            ) : (
              <>
                未登录，
                <Link to="/login" className="text-brand-500 hover:underline">
                  去登录
                </Link>
              </>
            )}
          </p>
        )}
      </section>

      {user && <AccountSection />}

      <section className="glass rounded-2xl p-5 shadow-lift sm:p-6">
        <h2 className="text-sm font-semibold">服务</h2>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs text-zinc-500">版本</dt>
            <dd className="mt-0.5">{health.data?.version ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">数据库</dt>
            <dd className="mt-0.5">{health.data?.db === "ok" ? "正常" : "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">音频引擎</dt>
            <dd className="mt-0.5">{health.data?.ffmpeg ? "可用" : "缺失"}</dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">书籍数量</dt>
            <dd className="mt-0.5">
              {health.data ? `${formatCount(health.data.books)} 本` : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">作者</dt>
            <dd className="mt-0.5">subject</dd>
          </div>
        </dl>
        <p className="mt-2 text-[11px] text-zinc-400 dark:text-zinc-500">
          shelf · 作者 subject · © 2026
        </p>
      </section>

      {user && <DeviceSection />}

      {user?.role === "admin" && <UserSection />}

      {user?.role === "admin" && <LibrarySection />}
    </div>
  );
}
