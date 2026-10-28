import { formatClock } from "../../lib/format";
import { usePlayer } from "../../store/player";
import { Icon } from "../ui/Icon";

/**
 * 另一台设备听的是别的书时，提示是否切过去。
 *
 * 同一本书的情况由 `syncFromServer()` 直接 seek，不会出现这个提示。
 */
export default function ProgressSyncToast() {
  const remote = usePlayer((state) => state.remoteProgress);
  const notice = usePlayer((state) => state.syncNotice);
  const currentBookId = usePlayer((state) => state.book?.id ?? null);

  if (notice) {
    return (
      <div className="pointer-events-none fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-full bg-ink-900/90 px-3 py-1.5 text-[11px] text-white shadow-lg dark:bg-white/90 dark:text-ink-900">
        {notice}
      </div>
    );
  }

  if (!remote || remote.bookId === currentBookId) return null;

  return (
    <div className="fixed bottom-28 right-4 z-50 w-64 rounded-2xl border border-zinc-200 bg-white p-3 shadow-xl dark:border-white/10 dark:bg-ink-800 sm:right-6">
      <div className="flex items-start gap-2">
        <span className="mt-0.5 text-brand-500">
          <Icon name="headphones" className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] text-zinc-500">另一台设备正在听</p>
          <p className="truncate text-xs font-medium">{remote.title}</p>
          <p className="mt-0.5 text-[11px] tabular-nums text-zinc-500">
            {formatClock(remote.positionSec)}
          </p>
        </div>
      </div>

      <div className="mt-2.5 flex gap-2">
        <button
          type="button"
          onClick={() => {
            usePlayer.setState({ remoteProgress: null });
            void usePlayer
              .getState()
              .open(remote.bookId, { positionSec: remote.positionSec });
          }}
          className="flex-1 rounded-full bg-brand-500 py-1.5 text-[11px] font-medium text-white transition hover:brightness-110"
        >
          接续这台
        </button>
        <button
          type="button"
          onClick={() => usePlayer.getState().dismissRemote()}
          className="rounded-full px-2.5 py-1.5 text-[11px] text-zinc-500 transition hover:bg-zinc-100 dark:hover:bg-white/10"
        >
          留在这台
        </button>
      </div>
    </div>
  );
}
