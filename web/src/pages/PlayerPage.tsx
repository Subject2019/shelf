import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";

import { api } from "../api/endpoints";
import PlayerLibraryPanel from "../components/player/PlayerLibraryPanel";
import PlayerStage from "../components/player/PlayerStage";
import { Icon } from "../components/ui/Icon";
import {
  chapterIndexAt,
  readLastBook,
  usePlayer,
  type LastBook,
} from "../store/player";

export default function PlayerPage() {
  const book = usePlayer((state) => state.book);
  const [lastBook, setLastBook] = useState<LastBook | null>(null);

  useEffect(() => {
    if (!book) setLastBook(readLastBook());
  }, [book]);
  const positionSec = usePlayer((state) => state.positionSec);
  const trackId = usePlayer((state) => state.trackId);
  const isPlaying = usePlayer((state) => state.isPlaying);
  const rate = usePlayer((state) => state.rate);
  const queryClient = useQueryClient();

  const addBookmark = useMutation({
    mutationFn: (note: string | null) => {
      if (!book) throw new Error("没有正在播放的书");
      const chapters = book.chapters ?? [];
      const chapter = chapters.length
        ? chapters[chapterIndexAt(chapters, positionSec)]
        : null;
      return api.createBookmark(book.id, {
        position_sec: Number(positionSec.toFixed(1)),
        track_id: trackId,
        note: note ?? chapter?.title ?? null,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["bookmarks", book?.id] });
    },
  });

  if (!book) {
    return (
      <div className="mx-auto max-w-md py-16 text-center">
        <div className="mx-auto flex size-16 items-center justify-center rounded-2xl bg-brand-500/10 text-brand-500">
          <Icon name="headphones" className="size-7" />
        </div>
        <h1 className="mt-5 text-lg font-semibold">
          {lastBook ? "接着上次的继续听" : "还没有正在播放的书"}
        </h1>
        <p className="mt-2 text-sm text-zinc-500">
          {lastBook
            ? "页面刷新后播放状态不会自动恢复，点一下就能回到原来的位置。"
            : "到书库挑一本，点封面就能开始；进度会自动保存。"}
        </p>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          {lastBook && (
            <button
              type="button"
              onClick={() => void usePlayer.getState().open(lastBook.id)}
              className="btn-gradient inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium"
            >
              <Icon name="play" className="size-4" />
              继续收听《{lastBook.title}》
            </button>
          )}
          <Link
            to="/library"
            className={[
              "inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition",
              lastBook
                ? "border border-zinc-300 text-zinc-700 hover:border-brand-500/40 hover:text-brand-500 dark:border-white/10 dark:text-zinc-300"
                : "btn-gradient",
            ].join(" ")}
          >
            去书库
            <Icon name="arrowRight" className="size-4" />
          </Link>
        </div>
      </div>
    );
  }

  const chapters = book.chapters ?? [];
  const chapterIndex =
    chapters.length > 0 ? chapterIndexAt(chapters, positionSec) : 0;
  const currentChapter = chapters[chapterIndex] ?? null;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">播放</h1>
          <p className="mt-1 text-sm text-zinc-500">
            {isPlaying ? "正在播放" : "已暂停"}
            {currentChapter ? ` · ${currentChapter.title}` : ""}
            {rate !== 1 ? ` · ${rate}×` : ""}
          </p>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_21rem]">
        <section className="glass rounded-3xl p-6 shadow-lift sm:p-8">
          <PlayerStage />
        </section>

        <aside className="glass flex h-[24rem] flex-col overflow-hidden rounded-2xl shadow-lift lg:sticky lg:top-20 lg:h-[calc(100dvh-8rem)]">
          <PlayerLibraryPanel
            bookId={book.id}
            chapters={chapters}
            currentIndex={chapterIndex}
            positionSec={positionSec}
            onSeek={(value) => usePlayer.getState().seekTo(value)}
            onAddBookmark={(note) => addBookmark.mutate(note)}
          />
        </aside>
      </div>
    </div>
  );
}
