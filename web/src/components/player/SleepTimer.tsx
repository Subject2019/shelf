import { useRef, useState } from "react";
import { createPortal } from "react-dom";

import { usePlayer } from "../../store/player";
import { Icon } from "../ui/Icon";

const DURATIONS = [15, 30, 45, 60, 90];
const CHAPTERS = [1, 2, 3, 5];

function clock(total: number): string {
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

const chip =
  "rounded-full px-2 py-1 text-[11px] text-zinc-600 transition hover:bg-brand-500/10 hover:text-brand-500 dark:text-zinc-300";

interface SleepTimerProps {
  /**
   * 触发按钮样式：
   * - `icon` 播放条上的纯图标
   * - `pill` 带文字的胶囊
   * - `tool` 播放页工具条里的一格（图标在上、文字在下）
   */
  variant?: "icon" | "pill" | "tool";
}

export default function SleepTimer({ variant = "icon" }: SleepTimerProps) {
  const [open, setOpen] = useState(false);
  const [customMinutes, setCustomMinutes] = useState("20");
  const [customCount, setCustomCount] = useState("4");
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [coords, setCoords] = useState<{ left: number; bottom: number } | null>(
    null,
  );

  const mode = usePlayer((state) => state.sleepMode);
  const remaining = usePlayer((state) => state.sleepRemainingSec);
  const chaptersLeft = usePlayer((state) => state.sleepChaptersLeft);
  const finishChapter = usePlayer((state) => state.sleepFinishChapter);
  const waiting = usePlayer((state) => state.sleepWaitingChapterEnd);

  const active = mode !== "off";
  const status =
    mode === "duration"
      ? waiting
        ? "本集后停"
        : clock(remaining)
      : mode === "chapters"
        ? `${chaptersLeft} 集`
        : "";

  const triggerClass =
    variant === "tool"
      ? [
          "flex w-full flex-col items-center gap-1 rounded-xl py-2 text-[10px] transition",
          active
            ? "bg-brand-500/10 text-brand-500"
            : "text-zinc-500 hover:bg-zinc-100 hover:text-brand-500 dark:text-zinc-400 dark:hover:bg-white/[0.06]",
        ].join(" ")
      : variant === "pill"
        ? [
            "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs transition",
            active
              ? "border-brand-500/40 bg-brand-500/10 text-brand-500"
              : "border-zinc-200 text-zinc-600 hover:border-brand-400/50 hover:text-brand-500 dark:border-white/10 dark:text-zinc-300",
          ].join(" ")
        : [
            "relative flex size-8 items-center justify-center rounded-full transition hover:bg-zinc-100 dark:hover:bg-white/10",
            active ? "text-brand-500" : "text-zinc-600 dark:text-zinc-300",
          ].join(" ");

  // 弹框用 fixed + 视口内夹紧，避免按钮贴边时弹框超出屏幕（竖屏播放页工具格靠左时尤其明显）
  function toggle() {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (rect) {
      const width = 256; // w-64
      const margin = 8;
      const left = Math.min(
        Math.max(rect.left + rect.width / 2 - width / 2, margin),
        Math.max(margin, window.innerWidth - width - margin),
      );
      setCoords({ left, bottom: window.innerHeight - rect.top + 8 });
    }
    setOpen((value) => !value);
  }

  return (
    <div className={variant === "tool" ? "relative flex-1" : "relative"}>
      <button
        ref={triggerRef}
        type="button"
        onClick={toggle}
        aria-label="睡眠定时"
        className={triggerClass}
      >
        <Icon name="moon" className={variant === "tool" ? "size-5" : "size-4"} />
        {variant === "icon" ? (
          active && (
            <span className="absolute right-1 top-1 size-1.5 rounded-full bg-brand-500" />
          )
        ) : (
          <span className={variant === "tool" ? "leading-none" : ""}>
            {active && status
              ? status
              : variant === "pill"
                ? "睡眠定时"
                : "定时"}
          </span>
        )}
      </button>

      {open && coords && createPortal(
        <div
          style={{ left: coords.left, bottom: coords.bottom }}
          className="fixed z-50 w-64 max-h-[70vh] overflow-y-auto rounded-2xl border border-zinc-200 bg-white p-3 shadow-xl dark:border-white/10 dark:bg-ink-800"
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium">睡眠定时</p>
            {active && (
              <button
                type="button"
                onClick={() => {
                  usePlayer.getState().clearSleep();
                  setOpen(false);
                }}
                className="text-[11px] text-zinc-400 hover:text-rose-500"
              >
                关闭定时
              </button>
            )}
          </div>

          <p className="mt-1 text-[11px] text-brand-500">
            {mode === "duration"
              ? waiting
                ? "时间到，本集播完就停"
                : `剩余 ${clock(remaining)}`
              : mode === "chapters"
                ? `还剩 ${chaptersLeft} 集`
                : "未启用"}
          </p>

          <p className="mt-3 text-[11px] text-zinc-500">按时长</p>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            {DURATIONS.map((minutes) => (
              <button
                key={minutes}
                type="button"
                onClick={() =>
                  usePlayer.getState().setSleepDuration(minutes, finishChapter)
                }
                className={chip}
              >
                {minutes} 分
              </button>
            ))}
          </div>
          <div className="mt-1.5 flex items-center gap-1">
            <input
              type="number"
              min={1}
              max={600}
              value={customMinutes}
              onChange={(event) => setCustomMinutes(event.target.value)}
              aria-label="自定义分钟数"
              className="h-7 w-14 rounded-lg border border-zinc-200 bg-transparent px-2 text-[11px] outline-none focus:border-brand-400 dark:border-white/10"
            />
            <span className="text-[11px] text-zinc-500">分钟</span>
            <button
              type="button"
              onClick={() =>
                usePlayer
                  .getState()
                  .setSleepDuration(Number(customMinutes) || 20, finishChapter)
              }
              className="ml-auto rounded-full bg-brand-500 px-2.5 py-1 text-[11px] font-medium text-white"
            >
              开始
            </button>
          </div>

          <label className="mt-2 flex items-center gap-1.5 text-[11px] text-zinc-600 dark:text-zinc-300">
            <input
              type="checkbox"
              checked={finishChapter}
              onChange={(event) =>
                usePlayer.getState().setSleepFinishChapter(event.target.checked)
              }
              className="size-3 accent-brand-500"
            />
            到点后播完本集再停
          </label>

          <p className="mt-3 text-[11px] text-zinc-500">按集数</p>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            {CHAPTERS.map((count) => (
              <button
                key={count}
                type="button"
                onClick={() => usePlayer.getState().setSleepChapters(count)}
                className={chip}
              >
                {count} 集
              </button>
            ))}
          </div>
          <div className="mt-1.5 flex items-center gap-1">
            <input
              type="number"
              min={1}
              max={99}
              value={customCount}
              onChange={(event) => setCustomCount(event.target.value)}
              aria-label="自定义集数"
              className="h-7 w-14 rounded-lg border border-zinc-200 bg-transparent px-2 text-[11px] outline-none focus:border-brand-400 dark:border-white/10"
            />
            <span className="text-[11px] text-zinc-500">集后停</span>
            <button
              type="button"
              onClick={() =>
                usePlayer.getState().setSleepChapters(Number(customCount) || 1)
              }
              className="ml-auto rounded-full bg-brand-500 px-2.5 py-1 text-[11px] font-medium text-white"
            >
              开始
            </button>
          </div>

          <p className="mt-3 text-[10px] leading-relaxed text-zinc-400">
            暂停播放时定时也会暂停；「按集数」在跨到下一集时计数，无章节信息的书按音轨计。
          </p>
        </div>,
        document.body,
      )}
    </div>
  );
}
