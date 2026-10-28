import { useEffect } from "react";

import { usePlayer } from "../store/player";

/** 全局播放快捷键；输入框内不拦截。 */
export function usePlayerHotkeys(): void {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName;
        if (
          tag === "INPUT" ||
          tag === "TEXTAREA" ||
          tag === "SELECT" ||
          target.isContentEditable
        ) {
          return;
        }
      }

      const player = usePlayer.getState();
      if (!player.book) return;

      switch (event.key) {
        case " ":
          event.preventDefault();
          player.toggle();
          break;
        case "ArrowLeft":
          event.preventDefault();
          player.skip(-15);
          break;
        case "ArrowRight":
          event.preventDefault();
          player.skip(15);
          break;
        case "ArrowUp":
          event.preventDefault();
          player.setVolume(player.volume + 0.05);
          break;
        case "ArrowDown":
          event.preventDefault();
          player.setVolume(player.volume - 0.05);
          break;
        case "j":
        case "J":
          player.skip(-30);
          break;
        case "l":
        case "L":
          player.skip(30);
          break;
        case "[":
          player.prevChapter();
          break;
        case "]":
          player.nextChapter();
          break;
        case "m":
        case "M":
          player.toggleMute();
          break;
        default:
          break;
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
}
