/**
 * 在线状态上报。
 *
 * 只靠「最近一次请求时间」判断在线会有明显延迟：用户关掉页面后，服务端要等窗口过期
 * 才知道。所以这里补三件事：
 *
 * 1. 页面可见时每 45 秒心跳（服务端窗口 2 分钟，容纳后台节流）
 * 2. 页面隐藏超过 20 秒、或 `pagehide` 时主动上报离线
 * 3. **正在播放时不降级**：听书本来就是后台行为，音频在放就不该显示离线；
 *    此时继续心跳，暂停后若仍隐藏，再走 20 秒倒计时
 *
 * 另外播放器每 15 秒上报一次进度，本身也会刷新服务端的 `last_seen_at`，
 * 两道信号互为兜底。
 */

import { api, deviceId } from "../api/endpoints";
import { usePlayer } from "../store/player";

const HEARTBEAT_MS = 45_000;
const HIDDEN_GRACE_MS = 20_000;

export function startPresence(): () => void {
  let hiddenTimer: number | undefined;
  let stopped = false;

  const isPlaying = () => usePlayer.getState().isPlaying;

  const report = (online: boolean) => {
    if (stopped) return;
    void api.setPresence(deviceId(), online).catch(() => {
      // 页面正在关闭 / 网络断开时失败是正常的
    });
  };

  const clearHiddenTimer = () => {
    window.clearTimeout(hiddenTimer);
    hiddenTimer = undefined;
  };

  const scheduleOffline = () => {
    clearHiddenTimer();
    if (!document.hidden || isPlaying()) return;
    // 切标签页通常只是短暂离开，20 秒内回来就不算离线
    hiddenTimer = window.setTimeout(() => {
      if (!isPlaying() && document.hidden) report(false);
    }, HIDDEN_GRACE_MS);
  };

  const onVisibilityChange = () => {
    clearHiddenTimer();
    if (document.visibilityState === "visible") {
      report(true);
      return;
    }
    // 后台播放：保持在线，不再排离线倒计时
    if (isPlaying()) {
      report(true);
      return;
    }
    scheduleOffline();
  };

  const onPageHide = () => {
    clearHiddenTimer();
    // 移动端切后台进入 bfcache 也会触发 pagehide，此时音频可能还在放
    if (isPlaying()) {
      report(true);
      return;
    }
    report(false);
  };

  const onPageShow = () => report(true);

  // 播放状态变化：开始播放 → 立刻刷新在线；暂停且页面隐藏 → 20 秒后离线
  const unsubscribe = usePlayer.subscribe((state, previous) => {
    if (state.isPlaying === previous.isPlaying) return;
    if (state.isPlaying) {
      clearHiddenTimer();
      report(true);
    } else {
      scheduleOffline();
    }
  });

  const heartbeat = window.setInterval(() => {
    if (!document.hidden || isPlaying()) report(true);
  }, HEARTBEAT_MS);

  document.addEventListener("visibilitychange", onVisibilityChange);
  window.addEventListener("pagehide", onPageHide);
  window.addEventListener("pageshow", onPageShow);

  return () => {
    stopped = true;
    window.clearInterval(heartbeat);
    clearHiddenTimer();
    unsubscribe();
    document.removeEventListener("visibilitychange", onVisibilityChange);
    window.removeEventListener("pagehide", onPageHide);
    window.removeEventListener("pageshow", onPageShow);
  };
}
