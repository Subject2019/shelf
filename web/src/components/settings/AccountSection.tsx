import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { api } from "../../api/endpoints";
import { useAuth } from "../../store/auth";

const inputClass =
  "mt-1 w-full rounded-xl border border-zinc-200 bg-white/70 px-3 py-2 text-sm outline-none transition focus:border-brand-500/60 focus:ring-2 focus:ring-brand-500/20 dark:border-white/10 dark:bg-white/[0.04]";

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "修改失败，请稍后再试";
}

/** 账号安全：修改自己的密码（管理员重置他人在「用户」区）。 */
export default function AccountSection() {
  const logout = useAuth((state) => state.logout);
  const navigate = useNavigate();

  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api.changePassword({ old_password: oldPassword, new_password: newPassword }),
    onSuccess: async () => {
      // 后端会把所有 refresh token 标记失效，这里直接回登录页，避免下次刷新时突然掉线
      await logout();
      navigate("/login", { replace: true });
    },
  });

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);
    if (newPassword.length < 8) {
      setFormError("新密码至少 8 位");
      return;
    }
    if (newPassword === oldPassword) {
      setFormError("新密码不能和原密码相同");
      return;
    }
    if (newPassword !== confirm) {
      setFormError("两次输入的新密码不一致");
      return;
    }
    mutation.mutate();
  }

  return (
    <section className="glass rounded-2xl p-5 shadow-lift sm:p-6">
      <h2 className="text-sm font-semibold">账号安全</h2>
      <p className="mt-1 text-xs text-zinc-500">
        修改后其他设备会退出登录，当前页面也会回到登录页。
      </p>

      <form className="mt-4 grid gap-4 sm:grid-cols-3" onSubmit={submit}>
        <label className="text-xs text-zinc-500">
          原密码
          <input
            className={inputClass}
            type="password"
            autoComplete="current-password"
            value={oldPassword}
            onChange={(event) => setOldPassword(event.target.value)}
            required
          />
        </label>
        <label className="text-xs text-zinc-500">
          新密码
          <input
            className={inputClass}
            type="password"
            autoComplete="new-password"
            minLength={8}
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            required
          />
        </label>
        <label className="text-xs text-zinc-500">
          确认新密码
          <input
            className={inputClass}
            type="password"
            autoComplete="new-password"
            minLength={8}
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            required
          />
        </label>

        {formError && (
          <p className="text-xs text-rose-500 sm:col-span-3">{formError}</p>
        )}
        {mutation.isError && (
          <p className="text-xs text-rose-500 sm:col-span-3">
            {errorText(mutation.error)}
          </p>
        )}

        <div className="sm:col-span-3">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded-xl bg-brand-500 px-4 py-2 text-xs font-medium text-ink-950 transition hover:opacity-90 disabled:opacity-50"
          >
            {mutation.isPending ? "修改中…" : "修改密码"}
          </button>
        </div>
      </form>
    </section>
  );
}
