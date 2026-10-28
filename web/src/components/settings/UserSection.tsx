import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError } from "../../api/client";
import { api } from "../../api/endpoints";
import type { UserAdmin, UserRole, UserUpdatePayload } from "../../api/types";
import { formatRelative } from "../../lib/format";
import { useAuth } from "../../store/auth";
import { Icon } from "../ui/Icon";

const fieldClass =
  "h-10 w-full rounded-lg border border-zinc-200 bg-white px-3 text-sm outline-none transition focus:border-brand-500 dark:border-white/10 dark:bg-ink-950";

const ROLE_META: Record<UserRole, { label: string; className: string }> = {
  admin: { label: "管理员", className: "bg-brand-500/15 text-brand-500" },
  editor: {
    label: "上传者",
    className: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  },
  listener: {
    label: "听众",
    className: "bg-zinc-200 text-zinc-600 dark:bg-white/10 dark:text-zinc-300",
  },
};

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "操作失败";
}

export default function UserSection() {
  const currentUser = useAuth((state) => state.user);
  const queryClient = useQueryClient();

  const [creating, setCreating] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"editor" | "listener">("listener");
  const [createError, setCreateError] = useState<string | null>(null);

  const [granting, setGranting] = useState<number | null>(null);
  const [resetting, setResetting] = useState<number | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [pendingDelete, setPendingDelete] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const usersQuery = useQuery({ queryKey: ["users"], queryFn: api.users });
  const librariesQuery = useQuery({
    queryKey: ["libraries"],
    queryFn: () => api.libraries(),
  });

  const users = usersQuery.data?.items ?? [];
  const libraries = librariesQuery.data?.items ?? [];
  const libraryName = new Map(libraries.map((item) => [item.id, item.name]));

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["users"] });
  }

  const createMutation = useMutation({
    mutationFn: () =>
      api.createUser({
        username: username.trim(),
        password,
        role,
      }),
    onSuccess: () => {
      setCreating(false);
      setUsername("");
      setPassword("");
      setRole("listener");
      setCreateError(null);
      invalidate();
    },
    onError: (error) => setCreateError(errorText(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: UserUpdatePayload }) =>
      api.updateUser(id, payload),
    onSuccess: () => {
      setActionError(null);
      setResetting(null);
      setNewPassword("");
      setGranting(null);
      invalidate();
    },
    onError: (error) => setActionError(errorText(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteUser(id),
    onSuccess: () => {
      setPendingDelete(null);
      setActionError(null);
      invalidate();
    },
    onError: (error) => setActionError(errorText(error)),
  });

  function toggleGrant(user: UserAdmin, libraryId: number) {
    const next = user.libraries.includes(libraryId)
      ? user.libraries.filter((id) => id !== libraryId)
      : [...user.libraries, libraryId];
    updateMutation.mutate({ id: user.id, payload: { library_ids: next } });
  }

  function renderUser(user: UserAdmin) {
    const isSelf = user.id === currentUser?.id;
    const grantsOpen = granting === user.id;

    return (
      <li
        key={user.id}
        className="rounded-xl border border-zinc-200/80 p-3 dark:border-white/10"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="truncate text-sm font-medium">{user.username}</span>
              {user.display_name && (
                <span className="truncate text-[11px] text-zinc-500">
                  {user.display_name}
                </span>
              )}
              <span
                className={[
                  "rounded-full px-1.5 py-0.5 text-[10px]",
                  (ROLE_META[user.role] ?? ROLE_META.listener).className,
                ].join(" ")}
              >
                {(ROLE_META[user.role] ?? ROLE_META.listener).label}
              </span>
              {!user.is_active && (
                <span className="rounded-full bg-rose-500/10 px-1.5 py-0.5 text-[10px] text-rose-500">
                  已停用
                </span>
              )}
              {isSelf && (
                <span className="rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-600 dark:text-emerald-400">
                  当前账号
                </span>
              )}
            </div>

            <p className="mt-1 text-[11px] text-zinc-500">
              {user.libraries.length > 0
                ? `${user.libraries.length} 个书库：${user.libraries
                    .map((id) => libraryName.get(id) ?? `#${id}`)
                    .join("、")}`
                : "未单独授权（公开书库仍可见）"}
            </p>
            <p className="mt-0.5 text-[11px] text-zinc-500">
              {user.last_login_at
                ? `最近登录 ${formatRelative(user.last_login_at)}`
                : "尚未登录"}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-1 sm:shrink-0 sm:justify-end">
            <button
              type="button"
              disabled={isSelf}
              onClick={() => setGranting(grantsOpen ? null : user.id)}
              aria-label="分配书库"
              title={isSelf ? "不能修改自己的授权" : "分配书库"}
              className="flex size-8 items-center justify-center rounded-full text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-900 disabled:opacity-30 dark:hover:bg-white/10 dark:hover:text-zinc-100"
            >
              <Icon name="library" className="size-4" />
            </button>
            <select
              value={user.role}
              disabled={isSelf || user.role === "admin" || updateMutation.isPending}
              onChange={(event) =>
                updateMutation.mutate({
                  id: user.id,
                  payload: { role: event.target.value as Exclude<UserRole, "admin"> },
                })
              }
              aria-label="角色"
              title={isSelf ? "不能修改自己的角色" : "角色"}
              className="h-7 rounded-lg border border-zinc-200 bg-transparent px-1.5 text-[11px] text-zinc-600 outline-none transition focus:border-brand-500 disabled:opacity-40 dark:border-white/10 dark:text-zinc-300"
            >
              <option value="listener">听众</option>
              <option value="editor">上传者</option>
              {user.role === "admin" && <option value="admin">管理员</option>}
            </select>
            <button
              type="button"
              disabled={isSelf}
              onClick={() =>
                updateMutation.mutate({
                  id: user.id,
                  payload: { is_active: !user.is_active },
                })
              }
              aria-label={user.is_active ? "停用账号" : "启用账号"}
              title={isSelf ? "不能停用自己" : user.is_active ? "停用账号" : "启用账号"}
              className="flex size-8 items-center justify-center rounded-full text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-900 disabled:opacity-30 dark:hover:bg-white/10 dark:hover:text-zinc-100"
            >
              <Icon name="power" className="size-4" />
            </button>
            <button
              type="button"
              onClick={() => {
                setResetting(resetting === user.id ? null : user.id);
                setNewPassword("");
              }}
              aria-label="重置密码"
              title="重置密码"
              className="flex size-8 items-center justify-center rounded-full text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-white/10 dark:hover:text-zinc-100"
            >
              <Icon name="spark" className="size-4" />
            </button>
            <button
              type="button"
              disabled={isSelf}
              onClick={() =>
                setPendingDelete(pendingDelete === user.id ? null : user.id)
              }
              aria-label="删除账号"
              title={isSelf ? "不能删除自己" : "删除账号"}
              className="flex size-8 items-center justify-center rounded-full text-zinc-400 transition hover:bg-rose-500/10 hover:text-rose-500 disabled:opacity-30"
            >
              <Icon name="trash" className="size-4" />
            </button>
          </div>
        </div>

        {grantsOpen && (
          <div className="mt-3 rounded-lg bg-zinc-50 p-2.5 dark:bg-white/[0.03]">
            <p className="text-[11px] text-zinc-500">
              勾选后立即生效；不勾选任何书库时，公开书库仍然可见。
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {libraries.length === 0 && (
                <span className="text-[11px] text-zinc-500">还没有书库</span>
              )}
              {libraries.map((library) => {
                const checked = user.libraries.includes(library.id);
                return (
                  <button
                    key={library.id}
                    type="button"
                    onClick={() => toggleGrant(user, library.id)}
                    className={[
                      "rounded-full border px-2.5 py-1 text-[11px] transition",
                      checked
                        ? "border-brand-500 bg-brand-500/10 text-brand-500"
                        : "border-zinc-200 text-zinc-600 hover:border-brand-500/50 dark:border-white/10 dark:text-zinc-400",
                    ].join(" ")}
                  >
                    {library.name}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {resetting === user.id && (
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-zinc-50 p-2.5 dark:bg-white/[0.03]">
            <input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              placeholder="新密码，至少 8 位"
              className={fieldClass}
            />
            <button
              type="button"
              disabled={newPassword.length < 8 || updateMutation.isPending}
              onClick={() =>
                updateMutation.mutate({
                  id: user.id,
                  payload: { password: newPassword },
                })
              }
              className="shrink-0 rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-medium text-ink-950 disabled:opacity-40"
            >
              保存
            </button>
          </div>
        )}

        {pendingDelete === user.id && (
          <div className="mt-3 flex items-center justify-between gap-2 rounded-lg bg-rose-500/10 px-2.5 py-1.5">
            <span className="text-[11px] text-rose-500">
              删除后该账号的进度与书签一并清除
            </span>
            <div className="flex shrink-0 items-center gap-1">
              <button
                type="button"
                onClick={() => deleteMutation.mutate(user.id)}
                className="rounded-md bg-rose-500 px-2 py-1 text-[11px] font-medium text-white"
              >
                确认删除
              </button>
              <button
                type="button"
                onClick={() => setPendingDelete(null)}
                className="rounded-md px-2 py-1 text-[11px] text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
              >
                取消
              </button>
            </div>
          </div>
        )}
      </li>
    );
  }

  return (
    <section className="glass rounded-2xl p-5 shadow-lift sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">用户</h2>
          <p className="mt-1 text-xs text-zinc-500">
            创建账号并分配可见书库；未授权的书库对该用户不可见。
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreating((open) => !open)}
          className="flex shrink-0 items-center gap-1 whitespace-nowrap rounded-lg border border-zinc-200 px-2.5 py-1.5 text-xs font-medium transition hover:border-brand-500 hover:text-brand-500 dark:border-white/10"
        >
          <Icon name={creating ? "close" : "plus"} className="size-3.5" />
          {creating ? "取消" : "新建用户"}
        </button>
      </div>

      {creating && (
        <div className="mt-4 space-y-2 rounded-xl border border-zinc-200/80 p-3 dark:border-white/10">
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="用户名"
            className={fieldClass}
          />
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="初始密码，至少 8 位"
            className={fieldClass}
          />
          <div className="flex items-center gap-2">
            {(
              [
                { value: "listener", label: "听众" },
                { value: "editor", label: "上传者" },
              ] as const
            ).map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setRole(item.value)}
                className={[
                  "rounded-full border px-3 py-1 text-xs transition",
                  role === item.value
                    ? "border-brand-500 bg-brand-500/10 text-brand-500"
                    : "border-zinc-200 text-zinc-600 dark:border-white/10 dark:text-zinc-400",
                ].join(" ")}
              >
                {item.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] leading-relaxed text-zinc-500">
            听众只能收听、记录进度与书签；上传者可编辑书籍资料、上传封面，但只能删除自己上传的封面。管理员只有一个，只能在服务器上通过环境变量或 `echoshelf admin create` 创建，网页端不提供。
          </p>
          {createError && <p className="text-[11px] text-rose-500">{createError}</p>}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setCreating(false);
                setCreateError(null);
              }}
              className="rounded-lg px-3 py-1.5 text-xs text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
            >
              取消
            </button>
            <button
              type="button"
              onClick={() => createMutation.mutate()}
              disabled={
                username.trim().length < 2 ||
                password.length < 8 ||
                createMutation.isPending
              }
              className="rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-medium text-ink-950 disabled:opacity-40"
            >
              {createMutation.isPending ? "创建中…" : "创建"}
            </button>
          </div>
        </div>
      )}

      {actionError && (
        <p className="mt-3 rounded-lg bg-rose-500/10 px-2.5 py-1.5 text-[11px] text-rose-500">
          {actionError}
        </p>
      )}

      <ul className="mt-4 space-y-2">
        {usersQuery.isPending && (
          <li className="py-6 text-center text-xs text-zinc-500">加载中…</li>
        )}
        {users.map(renderUser)}
      </ul>
    </section>
  );
}
