import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { initialOf } from "../../lib/format";
import { usePlayerHotkeys } from "../../lib/hotkeys";
import { startPresence } from "../../lib/presence";
import { useMediaSession } from "../../lib/mediaSession";
import { splashReady } from "../../lib/splash";
import { useAuth } from "../../store/auth";
import { usePlayer } from "../../store/player";
import { useUi } from "../../store/ui";
import JumpUndoToast from "../player/JumpUndoToast";
import PlayerBar from "../player/PlayerBar";
import ProgressSyncToast from "../player/ProgressSyncToast";
import { Icon, type IconName } from "../ui/Icon";

const NAV: { to: string; label: string; icon: IconName }[] = [
  { to: "/", label: "首页", icon: "home" },
  { to: "/library", label: "书库", icon: "library" },
  { to: "/player", label: "播放", icon: "play" },
  { to: "/search", label: "搜索", icon: "search" },
  { to: "/collections", label: "书单", icon: "booklist" },
  { to: "/settings", label: "设置", icon: "settings" },
];

const MOBILE_NAV = NAV;
const OFFLINE_DISABLED = new Set(["/collections"]);

function navClass(isActive: boolean): string {
  return [
    "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition",
    isActive
      ? "bg-gradient-to-r from-brand-500/20 via-brand-500/10 to-transparent text-brand-500"
      : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-white/5 dark:hover:text-zinc-100",
  ].join(" ");
}

function disabledNavClass(): string {
  return "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium text-zinc-400 opacity-45 dark:text-zinc-600";
}

export default function AppShell({ offline = false }: { offline?: boolean }) {
  const location = useLocation();
  const theme = useUi((state) => state.theme);
  const toggleTheme = useUi((state) => state.toggleTheme);
  const user = useAuth((state) => state.user);
  const status = useAuth((state) => state.status);
  const logout = useAuth((state) => state.logout);
  const bootstrap = useAuth((state) => state.bootstrap);
  const enterOffline = useAuth((state) => state.enterOffline);
  const hasPlayer = usePlayer((state) => Boolean(state.book));
  const started = useRef(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (offline) {
      enterOffline();
      return;
    }
    if (started.current) return;
    started.current = true;
    void bootstrap();
  }, [bootstrap, enterOffline, offline]);

  // 登录/重新登录完成后先重拉书架与详情，避免继续使用上一会话的旧进度。
  useEffect(() => {
    if (offline || status !== "authenticated") return;
    void queryClient.invalidateQueries();
  }, [offline, status, queryClient]);

  // 登录态确定 = 首屏路由已渲染、可交互；此时让启动屏退场。
  // 离线模式没有登录态，直接让启动屏退场。
  useEffect(() => {
    if (!offline && status === "loading") return undefined;
    const raf = requestAnimationFrame(() => splashReady());
    return () => cancelAnimationFrame(raf);
  }, [offline, status]);

  // 登录后开始上报在线状态；页面关闭 / 切后台超时会主动标记离线
  useEffect(() => {
    if (offline || !user) return;
    return startPresence();
  }, [offline, user]);

  // 回到前台 / 定时轮询时对齐账号的最新进度（一个账号一本书只有一条进度）
  useEffect(() => {
    if (offline || !user) return;

    const sync = () => {
      if (document.hidden) return;
      void usePlayer.getState().syncFromServer();
    };

    sync();
    document.addEventListener("visibilitychange", sync);
    window.addEventListener("focus", sync);
    window.addEventListener("pageshow", sync);
    const timer = window.setInterval(sync, 60_000);

    return () => {
      document.removeEventListener("visibilitychange", sync);
      window.removeEventListener("focus", sync);
      window.removeEventListener("pageshow", sync);
      window.clearInterval(timer);
    };
  }, [offline, user]);

  usePlayerHotkeys();
  useMediaSession();

  const current = NAV.find((item) => item.to === location.pathname);
  const pageTitle = location.pathname.startsWith("/books/")
    ? "书籍详情"
    : location.pathname.startsWith("/collections/")
      ? "书单"
      : current?.label ?? (offline ? "离线书架" : "shelf");

  return (
    <div className="relative isolate min-h-dvh text-zinc-900 transition-colors dark:text-zinc-100">
      {/* 背景光晕：给毛玻璃提供可模糊的底色，缓慢漂移但不随页面滚动 */}
      <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="glow-drift absolute -left-40 -top-48 size-[38rem] rounded-full bg-brand-500/30 blur-[110px] dark:bg-brand-500/[0.26]" />
        <div
          className="glow-drift glow-drift--reverse absolute -right-56 top-[16%] size-[32rem] rounded-full bg-indigo-400/20 blur-[110px] dark:bg-indigo-500/[0.18]"
          style={{ "--glow-duration": "34s", "--glow-delay": "-9s" } as React.CSSProperties}
        />
        <div
          className="glow-drift absolute -bottom-56 left-[26%] size-[30rem] rounded-full bg-rose-400/15 blur-[110px] dark:bg-fuchsia-500/[0.12]"
          style={{ "--glow-duration": "42s", "--glow-delay": "-18s" } as React.CSSProperties}
        />
      </div>

      <div className="mx-auto flex min-h-dvh w-full max-w-[1440px]">
        <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-white/60 bg-white/55 px-4 py-6 backdrop-blur-2xl backdrop-saturate-150 dark:border-white/5 dark:bg-white/[0.03] lg:flex">
          <Link to="/" className="flex items-center gap-2.5 px-2">
            <img
              src="/shelf.svg"
              alt=""
              className="size-9 shrink-0 dark:invert"
            />
            <span>
              <span className="block text-sm font-semibold tracking-wide">shelf</span>
              <span className="block text-[11px] text-zinc-500">
                {offline ? "本地离线书库" : "自托管有声书"}
              </span>
            </span>
          </Link>

          <nav className="mt-8 space-y-1">
            {NAV.map((item) =>
              offline && OFFLINE_DISABLED.has(item.to) ? (
                <span
                  key={item.to}
                  title="离线模式暂不支持"
                  aria-disabled="true"
                  className={disabledNavClass()}
                >
                  <Icon name={item.icon} />
                  {item.label}
                  <span className="ml-auto text-[10px]">离线</span>
                </span>
              ) : (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) => navClass(isActive)}
                >
                  <Icon name={item.icon} />
                  {item.label}
                </NavLink>
              ),
            )}
          </nav>

          <div className="mt-auto space-y-3 pt-6">
            <button
              type="button"
              onClick={toggleTheme}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm text-zinc-600 transition hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-white/5"
            >
              <Icon name={theme === "dark" ? "sun" : "moon"} />
              {theme === "dark" ? "切换浅色" : "切换深色"}
            </button>

            {offline ? (
              <div className="rounded-card border border-zinc-200/80 bg-white/70 p-3 dark:border-white/5 dark:bg-white/5">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <span className="flex size-8 items-center justify-center rounded-full bg-amber-500/15 text-amber-600">
                    <Icon name="download" className="size-4" />
                  </span>
                  离线模式
                </div>
                <p className="mt-2 text-[11px] leading-5 text-zinc-500">
                  搜索和设置只作用于本地离线书库；书单暂不可用。
                </p>
                <button
                  type="button"
                  onClick={() => window.ShelfApp?.retry?.()}
                  className="mt-3 w-full rounded-lg border border-zinc-200 px-3 py-1.5 text-xs text-zinc-600 transition hover:border-brand-500/40 hover:text-brand-500 dark:border-white/10 dark:text-zinc-400"
                >
                  重新连接服务器
                </button>
              </div>
            ) : status === "loading" ? (
              <div className="h-16 animate-pulse rounded-card bg-zinc-200/60 dark:bg-white/5" />
            ) : user ? (
              <div className="rounded-card border border-zinc-200/80 bg-white/70 p-3 dark:border-white/5 dark:bg-white/5">
                <div className="flex items-center gap-2.5">
                  <span className="flex size-8 items-center justify-center rounded-full bg-brand-500/15 text-sm font-semibold text-brand-500">
                    {initialOf(user.display_name ?? user.username)}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">
                      {user.display_name ?? user.username}
                    </span>
                    <span className="block text-[11px] text-zinc-500">
                      {user.role === "admin" ? "管理员" : "听众"}
                    </span>
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => void logout()}
                  className="mt-3 w-full rounded-lg border border-zinc-200 px-3 py-1.5 text-xs text-zinc-600 transition hover:border-brand-500/40 hover:text-brand-500 dark:border-white/10 dark:text-zinc-400"
                >
                  退出登录
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                className="flex items-center justify-center gap-2 rounded-card bg-brand-500 px-3 py-2 text-sm font-medium text-ink-950 transition hover:bg-brand-400"
              >
                登录
                <Icon name="arrowRight" className="size-4" />
              </Link>
            )}
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header
            className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-white/50 bg-white/60 px-4 py-3 backdrop-blur-2xl backdrop-saturate-150 dark:border-white/5 dark:bg-ink-950/55 sm:px-6 lg:px-8"
            style={{ paddingTop: "calc(var(--sat, 0px) + 0.75rem)" }}
          >
            <Link to="/" className="flex items-center gap-2 lg:hidden">
              <img src="/shelf.svg" alt="" className="size-8 dark:invert" />
              <span className="text-sm font-semibold">shelf</span>
            </Link>
            <span className="hidden text-sm text-zinc-500 lg:block">{pageTitle}</span>

            <div className="flex items-center gap-1">
              <Link
                to="/search"
                aria-label="搜索"
                className="flex size-9 items-center justify-center rounded-full text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-white/5 dark:hover:text-zinc-100"
              >
                <Icon name="search" />
              </Link>
              <button
                type="button"
                onClick={toggleTheme}
                aria-label="切换主题"
                className="flex size-9 items-center justify-center rounded-full text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-white/5 dark:hover:text-zinc-100 lg:hidden"
              >
                <Icon name={theme === "dark" ? "sun" : "moon"} />
              </button>
              {offline ? (
                <span className="ml-1 inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-600">
                  <Icon name="download" className="size-3" />
                  离线
                </span>
              ) : user ? (
                <Link
                  to="/settings"
                  className="ml-1 flex size-9 items-center justify-center rounded-full bg-brand-500/15 text-sm font-semibold text-brand-500 lg:hidden"
                >
                  {initialOf(user.display_name ?? user.username)}
                </Link>
              ) : (
                <Link
                  to="/login"
                  className="ml-1 rounded-full bg-brand-500 px-3 py-1.5 text-xs font-medium text-ink-950 lg:hidden"
                >
                  登录
                </Link>
              )}
            </div>
          </header>

          <main
            className={[
              "flex-1 px-4 pt-6 sm:px-6 lg:px-8",
              hasPlayer && location.pathname !== "/player"
                ? "pb-44 lg:pb-32"
                : "pb-24 lg:pb-12",
            ].join(" ")}
          >
            <div key={location.pathname} className="animate-page-in">
              <Outlet />
            </div>
          </main>
        </div>
      </div>

      <PlayerBar />
      <ProgressSyncToast />
      <JumpUndoToast />

      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-white/60 bg-white/75 pb-[var(--sb,0px)] backdrop-blur-2xl backdrop-saturate-150 dark:border-white/5 dark:bg-ink-950/70 lg:hidden">
        <div className="mx-auto flex max-w-md items-center justify-around px-2 py-1.5">
          {MOBILE_NAV.map((item) =>
            offline && OFFLINE_DISABLED.has(item.to) ? (
              <span
                key={item.to}
                aria-disabled="true"
                title="离线模式暂不支持"
                className="flex min-w-0 flex-1 cursor-not-allowed flex-col items-center gap-0.5 rounded-lg px-1 py-1 text-[10px] text-zinc-400 opacity-40"
              >
                <Icon name={item.icon} className="size-5" />
                {item.label}
              </span>
            ) : (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  [
                    "flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-lg px-1 py-1 text-[10px] transition",
                    isActive ? "text-brand-500" : "text-zinc-500",
                  ].join(" ")
                }
              >
                <Icon name={item.icon} className="size-5" />
                {item.label}
              </NavLink>
            ),
          )}
        </div>
      </nav>
    </div>
  );
}
