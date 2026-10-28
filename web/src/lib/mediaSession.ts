import { useEffect } from "react";

import { chapterIndexAt, usePlayer } from "../store/player";

/** 锁屏 / 系统媒体面板的信息与按钮。 */
export function useMediaSession(): void {
  const book = usePlayer((state) => state.book);
  const trackId = usePlayer((state) => state.trackId);
  const isPlaying = usePlayer((state) => state.isPlaying);
  const positionSec = usePlayer((state) => state.positionSec);
  const durationSec = usePlayer((state) => state.durationSec);
  const rate = usePlayer((state) => state.rate);

  useEffect(() => {
    if (!("mediaSession" in navigator) || !book) return;

    const chapters = book.chapters ?? [];
    const track = book.tracks.find((item) => item.id === trackId);
    const title =
      chapters.length > 0
        ? chapters[chapterIndexAt(chapters, positionSec)].title
        : track?.title ?? book.title;

    navigator.mediaSession.metadata = new MediaMetadata({
      title,
      artist: book.author ?? "",
      album: book.title,
    });
    navigator.mediaSession.playbackState = isPlaying ? "playing" : "paused";

    try {
      const duration = Math.max(1, durationSec);
      navigator.mediaSession.setPositionState({
        duration,
        position: Math.min(Math.max(0, positionSec), duration),
        playbackRate: rate,
      });
    } catch {
      // 部分浏览器不支持 positionState，忽略
    }
  }, [book, trackId, isPlaying, positionSec, durationSec, rate]);

  useEffect(() => {
    if (!("mediaSession" in navigator)) return;

    navigator.mediaSession.setActionHandler("play", () => {
      const player = usePlayer.getState();
      if (player.book && !player.isPlaying) player.toggle();
    });
    navigator.mediaSession.setActionHandler("pause", () => {
      const player = usePlayer.getState();
      if (player.isPlaying) player.toggle();
    });
    navigator.mediaSession.setActionHandler("seekbackward", () =>
      usePlayer.getState().skip(-15),
    );
    navigator.mediaSession.setActionHandler("seekforward", () =>
      usePlayer.getState().skip(15),
    );
    navigator.mediaSession.setActionHandler("previoustrack", () =>
      usePlayer.getState().prevChapter(),
    );
    navigator.mediaSession.setActionHandler("nexttrack", () =>
      usePlayer.getState().nextChapter(),
    );

    return () => {
      navigator.mediaSession.setActionHandler("play", null);
      navigator.mediaSession.setActionHandler("pause", null);
      navigator.mediaSession.setActionHandler("seekbackward", null);
      navigator.mediaSession.setActionHandler("seekforward", null);
      navigator.mediaSession.setActionHandler("previoustrack", null);
      navigator.mediaSession.setActionHandler("nexttrack", null);
    };
  }, []);
}
