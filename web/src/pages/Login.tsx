import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../store/auth";

const inputClass =
  "w-full rounded-xl border border-zinc-200 bg-white px-3.5 py-2.5 text-sm outline-none transition placeholder:text-zinc-400 focus:border-brand-500/60 focus:ring-2 focus:ring-brand-500/20 dark:border-white/10 dark:bg-ink-950 dark:text-zinc-100";

const labelClass = "mb-1.5 block text-xs text-zinc-500";

export default function Login() {
  const status = useAuth((state) => state.status);
  const login = useAuth((state) => state.login);
  const passwordlessUsers = useAuth((state) => state.passwordlessUsers);
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const state = location.state as { from?: string } | null;
  const from = state?.from && state.from !== "/login" ? state.from : "/";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordMode, setPasswordMode] = useState(false);
  const [reveal, setReveal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const passwordlessMode = passwordlessUsers.length > 0 && !passwordMode;

  if (status === "authenticated") {
    return <Navigate to={from} replace />;
  }

  if (status === "loading") {
    return (
      <div className="py-24 text-center text-sm text-zinc-500">正在恢复登录状态…</div>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;

    const name = username.trim();
    setError(null);

    if (passwordlessMode) {
      if (!name) {
        setError("请选择一个免密用户");
        return;
      }
    } else if (!name || !password) {
      setError("请填写用户名和密码");
      return;
    }
    setPending(true);
    try {
      await login(name, passwordlessMode ? "" : password);
      await queryClient.invalidateQueries();
      navigate(from, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError("用户名或密码不正确");
        } else if (err.status === 429) {
          setError("尝试次数过多，请 5 分钟后再试");
        } else {
          setError(err.message);
        }
      } else {
        setError("网络异常，请确认后端服务已启动");
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-sm flex-col justify-center py-8 sm:py-16">
      <div className="flex items-center gap-2.5">
        <img src="/shelf.svg" alt="" className="size-11 dark:invert" />
        <span>
          <span className="block text-base font-semibold">shelf</span>
          <span className="block text-xs text-zinc-500">自托管有声书</span>
        </span>
      </div>

      <div className="glass mt-6 rounded-2xl p-6 shadow-lift sm:p-7">
        <h1 className="text-lg font-semibold">登录</h1>
        <p className="mt-1 text-xs leading-5 text-zinc-500">
          使用你的账号继续收听，登录状态会保持 30 天。
        </p>

        <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="username" className={labelClass}>
              {passwordlessMode ? "免密用户" : "用户名"}
            </label>
            {passwordlessMode ? (
              <>
                <select
                  id="username"
                  name="username"
                  value={username}
                  onChange={(event) => {
                    setUsername(event.target.value);
                    setError(null);
                  }}
                  className={inputClass}
                >
                  <option value="">请选择免密用户</option>
                  {passwordlessUsers.map((user) => (
                    <option key={user.username} value={user.username}>
                      {user.display_name
                        ? `${user.display_name}（${user.username}）`
                        : user.username}
                    </option>
                  ))}
                </select>
                <p className="mt-1.5 text-[11px] leading-5 text-amber-600 dark:text-amber-400">
                  {passwordlessUsers.length > 1
                    ? "当前服务器不止一个免密用户，请选择一个免密用户登录。"
                    : "请选择一个免密用户登录。"}
                </p>
              </>
            ) : (
              <input
                id="username"
                name="username"
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className={inputClass}
                placeholder="admin"
              />
            )}
          </div>

          {!passwordlessMode && (
            <div>
              <label htmlFor="password" className={labelClass}>
                密码
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={reveal ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className={`${inputClass} pr-14`}
                  placeholder="请输入密码"
                />
                <button
                  type="button"
                  onClick={() => setReveal((value) => !value)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md px-2 py-1 text-xs text-zinc-500 transition hover:text-brand-500"
                >
                  {reveal ? "隐藏" : "显示"}
                </button>
              </div>
            </div>
          )}

          {error && (
            <p
              role="alert"
              className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs leading-5 text-red-500"
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={pending}
            className="w-full rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-medium text-ink-950 transition hover:bg-brand-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {pending ? "请稍候…" : passwordlessMode ? "进入" : "登录"}
          </button>

          {passwordlessUsers.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setPasswordMode((value) => !value);
                setUsername("");
                setPassword("");
                setError(null);
              }}
              className="w-full text-center text-[11px] text-zinc-500 transition hover:text-brand-500"
            >
              {passwordMode ? "使用免密用户登录" : "使用账号密码登录"}
            </button>
          )}
        </form>

        <details className="mt-5 rounded-xl border border-zinc-200/80 bg-zinc-50 p-3 text-[11px] leading-5 text-zinc-500 dark:border-white/10 dark:bg-white/[0.03]">
          <summary className="cursor-pointer select-none text-xs text-zinc-600 dark:text-zinc-300">
            首次部署？管理员需在服务器上初始化
          </summary>
          <p className="mt-2">
            为安全起见，网页端不能创建管理员。请在部署机器上执行：
          </p>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-white p-2 text-[10px] leading-5 text-zinc-600 dark:bg-ink-950 dark:text-zinc-300">
{`# Docker
docker exec -it echoshelf python -m app.cli admin create

# 常规部署
/opt/echoshelf/bin/echoshelf admin create`}
          </pre>
          <p className="mt-2">
            忘记密码：把 <code>create</code> 换成 <code>reset-password</code>。
          </p>
        </details>

        <p className="mt-4 text-center text-[11px] text-zinc-500">
          <Link to="/" className="transition hover:text-brand-500">
            先逛逛首页
          </Link>
        </p>
      </div>
    </div>
  );
}
