import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api } from "../../api/endpoints";
import { RATES } from "../../lib/playback";
import { chapterIndexAt, usePlayer } from "../../store/player";
import { Icon } from "../ui/Icon";
import SleepTimer from "./SleepTimer";

const toolClass =
  "flex w-full flex-col items-center gap-1 rounded-xl py-2 text-[10px] leading-none transition";

export default function PlayerTools() {
  const rate = usePlayer((state) => state.rate);
  const volume = usePlayer((state) => state.volume);
  const muted = usePlayer((state) => state.muted);
  const book = usePlayer((state) => state.book);
  const positionSec = usePlayer((state) => state.positionSec);
  const trackId = usePlayer((state) => state.trackId);

  const queryClient = useQueryClient();
  const [menu, setMenu] = useState<"rate" | "volume" | null>(null);
  const [justAdded, setJustAdded] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menu) return;
    const onPointerDown = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setMenu(null);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [menu]);

  const addBookmark = useMutation({
    mutationFn: () => {
      if (!book) throw new Error("没有正在播放的书");
      const chapters = book.chapters ?? [];
      const chapter =
        chapters.length > 0
          ? chapters[chapterIndexAt(chapters, positionSec)]
          : null;
      return api.createBookmark(book.id, {
        position_sec: Number(positionSec.toFixed(1)),
        track_id: trackId,
        note: chapter?.title ?? null,
      });
    },
    onSuccess: () => {
      setJustAdded(true);
      window.setTimeout(() => setJustAdded(false), 1500);
      if (book) {
        void queryClient.invalidateQueries({ queryKey: ["bookmarks", book.id] });
      }
    },
  });

  const effectiveVolume = muted ? 0 : volume;

  return (
    <div
      ref={rootRef}
      className="mt-5 flex w-full items-stretch gap-1 rounded-2xl bg-zinc-500/[0.08] p-1 dark:bg-white/[0.05]"
    >
      <SleepTimer variant="tool" />

      <div className="relative flex-1">
        <button
          type="button"
          onClick={() => setMenu(menu === "rate" ? null : "rate")}
          aria-label="播放倍速"
          className={[
            toolClass,
            menu === "rate" || rate !== 1
              ? "text-brand-500"
              : "text-zinc-500 hover:bg-zinc-100 hover:text-brand-500 dark:text-zinc-400 dark:hover:bg-white/[0.06]",
          ].join(" ")}
        >
          <span className="flex h-5 items-center text-[13px] font-medium tabular-nums">
            {rate}×
          </span>
          <span>倍速</span>
        </button>
        {menu === "rate" && (
          <div className="absolute bottom-full left-1/2 z-30 mb-2 grid w-36 -translate-x-1/2 grid-cols-2 gap-1 rounded-xl border border-zinc-200 bg-white p-1.5 shadow-xl dark:border-white/10 dark:bg-ink-800">
            {RATES.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => {
                  usePlayer.getState().setRate(item);
                  setMenu(null);
                }}
                className={[
                  "rounded-lg py-1 text-xs transition hover:bg-zinc-100 dark:hover:bg-white/10",
                  item === rate
                    ? "font-semibold text-brand-500"
                    : "text-zinc-600 dark:text-zinc-300",
                ].join(" ")}
              >
                {item}×
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="relative flex-1">
        <button
          type="button"
          onClick={() => setMenu(menu === "volume" ? null : "volume")}
          aria-label="音量"
          className={[
            toolClass,
            menu === "volume"
              ? "text-brand-500"
              : "text-zinc-500 hover:bg-zinc-100 hover:text-brand-500 dark:text-zinc-400 dark:hover:bg-white/[0.06]",
          ].join(" ")}
        >
          <Icon
            name={effectiveVolume === 0 ? "volumeMute" : "volume"}
            className="size-5"
          />
          <span>{Math.round(effectiveVolume * 100)}%</span>
        </button>
        {menu === "volume" && (
          <div className="absolute bottom-full left-1/2 z-30 mb-2 flex w-44 -translate-x-1/2 items-center gap-2 rounded-xl border border-zinc-200 bg-white px-3 py-2.5 shadow-xl dark:border-white/10 dark:bg-ink-800">
            <button
              type="button"
              onClick={() => usePlayer.getState().toggleMute()}
              aria-label={muted ? "取消静音" : "静音"}
              className="text-zinc-500 transition hover:text-brand-500 dark:text-zinc-400"
            >
              <Icon
                name={effectiveVolume === 0 ? "volumeMute" : "volume"}
                className="size-4"
              />
            </button>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={effectiveVolume}
              onChange={(event) =>
                usePlayer.getState().setVolume(Number(event.target.value))
              }
              aria-label="音量滑块"
              className="h-1 flex-1 cursor-pointer accent-brand-500"
            />
          </div>
        )}
      </div>

      <div className="relative flex-1">
        <button
          type="button"
          onClick={() => addBookmark.mutate()}
          disabled={!book || addBookmark.isPending}
          aria-label="添加书签"
          className={[
            toolClass,
            justAdded
              ? "text-emerald-500 dark:text-emerald-400"
              : "text-zinc-500 hover:bg-zinc-100 hover:text-brand-500 dark:text-zinc-400 dark:hover:bg-white/[0.06]",
          ].join(" ")}
        >
          <Icon name={justAdded ? "check" : "bookmark"} className="size-5" />
          <span>{justAdded ? "已添加" : "书签"}</span>
        </button>
      </div>
    </div>
  );
}
