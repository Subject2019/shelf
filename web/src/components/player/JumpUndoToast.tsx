import { formatClock } from "../../lib/format";
import { usePlayer } from "../../store/player";
import { Icon } from "../ui/Icon";

/**
 * 拖动进度条造成大幅度跳转时的「撤销」提示。
 *
 * 误触进度条后可以直接回到原来的位置，不用去翻章节或进度回溯点。
 * 注意：透明度别用刻度外的裸值（如 92），Tailwind 不会生成对应类，
 * 结果是透明背景 + 同色文字，日间/深色都会看不清；精确值请写成 [0.92]。
 */
export default function JumpUndoToast() {
  const jump = usePlayer((state) => state.jumpUndo);
  if (!jump) return null;

  return (
    <div className="fixed bottom-32 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-[11px] text-ink-900 shadow-lift dark:border-white/10 dark:bg-ink-800 dark:text-zinc-100">
      <span className="flex items-center gap-1.5 whitespace-nowrap">
        <Icon name="refresh" className="size-3.5 text-brand-500" />
        已跳到 {formatClock(jump.to)}
      </span>
      <button
        type="button"
        onClick={() => usePlayer.getState().undoJump()}
        className="whitespace-nowrap rounded-full bg-brand-500 px-2.5 py-1 text-[11px] font-medium text-white transition hover:brightness-110"
      >
        回到 {formatClock(jump.from)}
      </button>
    </div>
  );
}
