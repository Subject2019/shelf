import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError } from "../../api/client";
import { api, deviceId } from "../../api/endpoints";
import type { Device } from "../../api/types";
import { formFactorLabel } from "../../lib/device";
import { formatRelative } from "../../lib/format";
import { useAuth } from "../../store/auth";
import { Icon } from "../ui/Icon";

function onlineLabel(device: Device): string {
  if (device.revoked_at) return "已下线";
  if (device.online) return "在线";
  if (device.offline_at) return "离线";
  return device.last_seen_at ? `最近 ${formatRelative(device.last_seen_at)}` : "未活跃";
}

export default function DeviceSection() {
  const current = useAuth((state) => state.user);
  const logout = useAuth((state) => state.logout);
  const queryClient = useQueryClient();
  const [all, setAll] = useState(false);
  const [pendingKick, setPendingKick] = useState<string | null>(null);
  const [uaOpen, setUaOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const devicesQuery = useQuery({
    queryKey: ["devices", all],
    queryFn: () => api.devices(all),
  });

  const kickMutation = useMutation({
    mutationFn: (id: string) => api.kickDevice(id),
    onSuccess: (_data, id) => {
      setPendingKick(null);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["devices"] });
      // 踢的是当前设备：会话已失效，直接退出到登录页
      if (id === deviceId()) {
        void logout();
      }
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "操作失败");
    },
  });

  const devices = devicesQuery.data?.items ?? [];
  const isAdmin = current?.role === "admin";

  return (
    <section className="glass rounded-2xl p-5 shadow-lift sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">设备</h2>
          <p className="mt-1 text-xs text-zinc-500">
            「在线」= 页面可见或正在播放且有心跳；后台播放不会被判离线，暂停后仍隐藏
            20 秒才变「离线」。踢下线则立刻吊销登录状态。
          </p>
        </div>
        {isAdmin && (
          <button
            type="button"
            onClick={() => setAll((value) => !value)}
            className={[
              "shrink-0 rounded-lg border px-2.5 py-1.5 text-xs transition",
              all
                ? "border-brand-500 text-brand-500"
                : "border-zinc-200 text-zinc-500 dark:border-white/10",
            ].join(" ")}
          >
            {all ? "只看自己" : "全部用户"}
          </button>
        )}
      </div>

      {error && (
        <p className="mt-3 rounded-lg bg-rose-500/10 px-2.5 py-1.5 text-[11px] text-rose-500">
          {error}
        </p>
      )}

      <ul className="mt-4 space-y-2">
        {devicesQuery.isPending && (
          <li className="py-6 text-center text-xs text-zinc-500">加载中…</li>
        )}
        {devicesQuery.isSuccess && devices.length === 0 && (
          <li className="rounded-xl border border-dashed border-zinc-200 px-4 py-8 text-center text-xs text-zinc-500 dark:border-white/10">
            这个账号还没有登记设备
          </li>
        )}

        {devices.map((device) => {
          const isCurrent = device.id === deviceId();
          const revoked = Boolean(device.revoked_at);
          return (
            <li
              key={device.id}
              className="rounded-xl border border-zinc-200/80 p-3 dark:border-white/10"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate text-sm font-medium">
                      {device.name ?? device.id}
                    </span>
                    <span
                      className={[
                        "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px]",
                        revoked
                          ? "bg-zinc-200 text-zinc-500 dark:bg-white/10 dark:text-zinc-400"
                          : device.online
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                            : "bg-zinc-200 text-zinc-600 dark:bg-white/10 dark:text-zinc-300",
                      ].join(" ")}
                    >
                      {!revoked && device.online && (
                        <span className="size-1.5 rounded-full bg-emerald-500" />
                      )}
                      {onlineLabel(device)}
                    </span>
                    {formFactorLabel(device.form_factor) && (
                      <span className="rounded-full bg-zinc-200 px-1.5 py-0.5 text-[10px] text-zinc-600 dark:bg-white/10 dark:text-zinc-300">
                        {formFactorLabel(device.form_factor)}
                      </span>
                    )}
                    {isCurrent && (
                      <span className="rounded-full bg-brand-500/10 px-1.5 py-0.5 text-[10px] text-brand-500">
                        当前设备
                      </span>
                    )}
                  </div>

                  <p className="mt-1 text-[11px] text-zinc-500">
                    {[all ? device.username : null, device.os, device.screen]
                      .filter(Boolean)
                      .join(" · ") ||
                      (device.platform === "web"
                        ? "旧版网页端（重新登录后显示浏览器信息）"
                        : device.platform || "—")}
                  </p>
                  <p className="mt-0.5 text-[11px] text-zinc-500">
                    {[
                      device.created_at ? `首次 ${formatRelative(device.created_at)}` : null,
                      device.last_seen_at ? `最近活跃 ${formatRelative(device.last_seen_at)}` : null,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "—"}
                  </p>

                  {device.user_agent && (
                    <button
                      type="button"
                      onClick={() => setUaOpen(uaOpen === device.id ? null : device.id)}
                      className="mt-1 text-[10px] text-zinc-400 underline decoration-dotted underline-offset-2 hover:text-brand-500"
                    >
                      {uaOpen === device.id ? "收起 UA" : "查看 UA"}
                    </button>
                  )}
                  {uaOpen === device.id && device.user_agent && (
                    <p className="mt-1 break-all rounded-md bg-zinc-100 p-2 font-mono text-[10px] leading-relaxed text-zinc-500 dark:bg-white/[0.04]">
                      {device.user_agent}
                    </p>
                  )}
                </div>

                {!revoked && (
                  <button
                    type="button"
                    onClick={() =>
                      setPendingKick(pendingKick === device.id ? null : device.id)
                    }
                    aria-label="踢下线"
                    className="flex size-8 shrink-0 items-center justify-center rounded-full text-zinc-400 transition hover:bg-rose-500/10 hover:text-rose-500"
                  >
                    <Icon name="power" className="size-4" />
                  </button>
                )}
              </div>

              {pendingKick === device.id && (
                <div className="mt-2 flex items-center justify-between gap-2 rounded-lg bg-rose-500/10 px-2.5 py-1.5">
                  <span className="text-[11px] text-rose-500">
                    {isCurrent
                      ? "这是当前设备，确认后本页会退出登录"
                      : "确认后该设备需要重新登录"}
                  </span>
                  <div className="flex shrink-0 items-center gap-1">
                    <button
                      type="button"
                      onClick={() => kickMutation.mutate(device.id)}
                      className="rounded-md bg-rose-500 px-2 py-1 text-[11px] font-medium text-white"
                    >
                      确认
                    </button>
                    <button
                      type="button"
                      onClick={() => setPendingKick(null)}
                      className="rounded-md px-2 py-1 text-[11px] text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                    >
                      取消
                    </button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
