/**
 * 全局播放器：单例 <audio> 由 PlayerBar 注册，路由切换不断音。
 * 进度上报遵循 ADR-0002：15s 定时 + 暂停/切轨/卸载上报，UI 跳转带 explicit_seek。
 */

import { create } from "zustand";

import { getAccessToken } from "../api/client";
import { api, deviceId } from "../api/endpoints";
import type { BookDetail, Chapter, Track } from "../api/types";
import {
  getNativePlayer,
  type NativePlayPayload,
  type NativeState,
} from "../lib/nativePlayer";

/** ArrayBuffer → base64，用于把封面内嵌进原生 MediaMetadata。 */
function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

const RATE_KEY = "echoshelf.playback_rate";
const SKIP_INTRO_KEY = "echoshelf.skip_intro";
const SKIP_OUTRO_KEY = "echoshelf.skip_outro";
const AUTO_NEXT_KEY = "echoshelf.auto_next";
const SKIP_INTRO_SEC_KEY = "echoshelf.skip_intro_sec";
const SKIP_OUTRO_SEC_KEY = "echoshelf.skip_outro_sec";

function readFlag(key: string, fallback: boolean): boolean {
  const raw = localStorage.getItem(key);
  return raw === null ? fallback : raw === "1";
}

function readNum(key: string, fallback: number): number {
  const raw = localStorage.getItem(key);
  if (raw === null) return fallback;
  const value = Number(raw);
  return Number.isFinite(value) && value >= 0 ? value : fallback;
}
const REPORT_INTERVAL_MS = 15_000;
const SEEK_REPORT_DELAY_MS = 500;

export interface TrackWithOffset extends Track {
  offsetSec: number;
}

let audioEl: HTMLAudioElement | null = null;
let reportTimer: number | null = null;
let seekReportTimer: number | null = null;
/** Android 壳注入的原生播放桥；普通浏览器为 null。 */
const nativePlayer = getNativePlayer();

function withOffsets(tracks: Track[]): TrackWithOffset[] {
  let offset = 0;
  return tracks.map((track) => {
    const item = { ...track, offsetSec: offset };
    offset += track.duration_sec;
    return item;
  });
}

// 浏览器普遍支持这些容器/编码；wma、ape 等一律让服务端转码成 opus
const BROWSER_PLAYABLE = new Set([
  "mp3",
  "m4a",
  "m4b",
  "aac",
  "flac",
  "ogg",
  "oga",
  "opus",
  "wav",
  "webm",
]);

function urlFor(track: Track, token: string | null): string {
  const params = new URLSearchParams();
  if (token) params.set("token", token);

  const format = (track.format ?? "").toLowerCase();
  if (format && !BROWSER_PLAYABLE.has(format)) {
    params.set("transcode", "opus");
    params.set("bitrate", "64");
  }

  const query = params.toString();
  return query ? `${track.stream_url}?${query}` : track.stream_url;
}

function findTrackById(tracks: TrackWithOffset[], id: number | null) {
  return tracks.find((track) => track.id === id) ?? null;
}

const LAST_BOOK_KEY = "echoshelf.last_book";

export interface LastBook {
  id: number;
  title: string;
  position_sec: number;
}

/** 记下「上次在听的书」，供刷新后 /player 页提供继续收听的入口。 */
function rememberLastBook(book: BookDetail, positionSec: number): void {
  try {
    const payload: LastBook = {
      id: book.id,
      title: book.title,
      position_sec: Math.round(positionSec),
    };
    localStorage.setItem(LAST_BOOK_KEY, JSON.stringify(payload));
  } catch {
    // 隐私模式写不进去就算了
  }
}

export function readLastBook(): LastBook | null {
  try {
    const raw = localStorage.getItem(LAST_BOOK_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as LastBook;
    return typeof parsed?.id === "number" ? parsed : null;
  } catch {
    return null;
  }
}

function trackAt(tracks: TrackWithOffset[], positionSec: number) {
  return (
    tracks.find((track) => positionSec < track.offsetSec + track.duration_sec) ??
    tracks[tracks.length - 1] ??
    null
  );
}

/** 当前位置落在第几章（章节按 start_sec 升序）。 */
export function chapterIndexAt(chapters: Chapter[], positionSec: number): number {
  let index = 0;
  for (let i = 0; i < chapters.length; i += 1) {
    if (chapters[i].start_sec <= positionSec + 0.01) index = i;
    else break;
  }
  return index;
}

function startReporting() {
  if (reportTimer) return;
  reportTimer = window.setInterval(() => {
    usePlayer.getState().reportProgress(false);
  }, REPORT_INTERVAL_MS);
}

function stopReporting() {
  if (!reportTimer) return;
  window.clearInterval(reportTimer);
  reportTimer = null;
}

let sleepTicker: number | null = null;

function startSleepTicker() {
  if (sleepTicker !== null) return;
  sleepTicker = window.setInterval(() => {
    const state = usePlayer.getState();
    if (state.sleepMode !== "duration") return;
    // 暂停时不计时；已经在等本集结束时也不再倒计时
    if (!state.isPlaying || state.sleepWaitingChapterEnd) return;

    const left = state.sleepRemainingSec - 1;
    if (left > 0) {
      usePlayer.setState({ sleepRemainingSec: left });
      // 最后 30 秒音量线性降到 0，避免突然静音
      if (left <= SLEEP_FADE_SEC && audioEl) {
        audioEl.volume = Math.max(0, state.volume * (left / SLEEP_FADE_SEC));
      }
      return;
    }

    const chapters = state.book?.chapters ?? [];
    usePlayer.setState({ sleepRemainingSec: 0 });
    if (state.sleepFinishChapter && chapters.length > 0) {
      usePlayer.setState({ sleepWaitingChapterEnd: true });
      return;
    }
    state.pauseForSleep();
  }, 1000);
}

function stopSleepTicker() {
  if (sleepTicker === null) return;
  window.clearInterval(sleepTicker);
  sleepTicker = null;
}

/** 其他设备最近写入的进度。 */
export interface RemoteProgress {
  bookId: number;
  title: string;
  positionSec: number;
  deviceId: string | null;
  updatedAt: number;
}

// 防止 visibilitychange / focus / pageshow 同时触发时刷接口
let lastSyncAt = 0;
let noticeTimer: number | null = null;
// 用户点了「留在这台」的那条进度，不要反复弹
let dismissedRemoteKey: string | null = null;
// 「误拖进度条」撤销提示的自动消失定时器
let jumpUndoTimer: number | null = null;
// 睡眠定时到点前的淡出时长（秒）
const SLEEP_FADE_SEC = 30;

function flashNotice(message: string) {
  usePlayer.setState({ syncNotice: message });
  if (noticeTimer !== null) window.clearTimeout(noticeTimer);
  noticeTimer = window.setTimeout(() => {
    usePlayer.setState({ syncNotice: null });
    noticeTimer = null;
  }, 5000);
}

interface PlayerState {
  book: BookDetail | null;
  tracks: TrackWithOffset[];
  trackId: number | null;
  token: string | null;
  isPlaying: boolean;
  isLoading: boolean;
  positionSec: number;
  durationSec: number;
  rate: number;
  /** 播放偏好（保存在本设备浏览器） */
  skipIntro: boolean;
  skipOutro: boolean;
  autoNext: boolean;
  /** 片头/片尾跳过秒数（本设备；0 表示沿用书籍自身的 intro_sec/outro_sec） */
  introSec: number;
  outroSec: number;
  volume: number;
  muted: boolean;
  error: string | null;

  // 睡眠定时
  sleepMode: "off" | "duration" | "chapters";
  sleepRemainingSec: number;
  sleepChaptersLeft: number;
  // 时长到点后是否等本集播完
  sleepFinishChapter: boolean;
  // 已到点、正在等本集结束
  sleepWaitingChapterEnd: boolean;
  // 上一次统计到的章节/轨序号，用来发现「跨集」
  sleepChapterMark: number;

  // 其他设备最近一次写入的进度（账号级唯一，用来提示/接续）
  remoteProgress: RemoteProgress | null;
  // 短暂的同步提示，如「已同步其他设备的进度」
  syncNotice: string | null;

  // 拖动进度条造成的大跳转，用于「撤销」
  jumpUndo: { from: number; to: number } | null;

  open: (
    bookId: number,
    options?: { trackId?: number; positionSec?: number },
  ) => Promise<void>;
  toggle: () => void;
  seekTo: (absoluteSec: number) => void;
  /** 拖动进度条用：大跳转时记下原点，可一键撤销 */
  seekWithUndo: (absoluteSec: number) => void;
  undoJump: () => void;
  skip: (deltaSec: number) => void;
  nextTrack: () => void;
  prevTrack: () => void;
  nextChapter: () => void;
  prevChapter: () => void;
  setRate: (rate: number) => void;
  setSkipIntro: (value: boolean) => void;
  setSkipOutro: (value: boolean) => void;
  setAutoNext: (value: boolean) => void;
  setIntroSec: (value: number) => void;
  setOutroSec: (value: number) => void;
  setVolume: (volume: number) => void;
  toggleMute: () => void;
  close: () => void;
  reportProgress: (explicitSeek?: boolean, keepalive?: boolean) => void;

  setSleepDuration: (minutes: number, finishChapter: boolean) => void;
  setSleepChapters: (count: number) => void;
  setSleepFinishChapter: (value: boolean) => void;
  clearSleep: () => void;
  pauseForSleep: () => void;
  handleSleepTick: (positionSec: number) => void;

  /** 拉取服务端最近进度：同书且暂停时直接跳到最新位置，异书时提示接续 */
  syncFromServer: () => Promise<void>;
  dismissRemote: () => void;
}

export const usePlayer = create<PlayerState>((set, get) => {
  function switchTo(track: TrackWithOffset, positionInTrack = 0) {
    if (nativePlayer) {
      const index = get().tracks.findIndex((item) => item.id === track.id);
      if (index >= 0) nativePlayer.seekToTrack(index, positionInTrack);
      set({ trackId: track.id, positionSec: track.offsetSec + positionInTrack });
      return;
    }
    if (!audioEl) return;
    const token = get().token;
    audioEl.src = urlFor(track, token);
    audioEl.addEventListener(
      "loadedmetadata",
      () => {
        if (!audioEl) return;
        audioEl.currentTime = Math.max(
          0,
          Math.min(track.duration_sec, positionInTrack),
        );
        void audioEl.play().catch(() => undefined);
      },
      { once: true },
    );
    set({ trackId: track.id, positionSec: track.offsetSec + positionInTrack });
  }

  function scheduleSeekReport() {
    if (seekReportTimer) window.clearTimeout(seekReportTimer);
    seekReportTimer = window.setTimeout(() => {
      seekReportTimer = null;
      get().reportProgress(true);
    }, SEEK_REPORT_DELAY_MS);
  }

  return {
    book: null,
    tracks: [],
    trackId: null,
    token: null,
    isPlaying: false,
    isLoading: false,
    positionSec: 0,
    durationSec: 0,
    rate: Number(localStorage.getItem(RATE_KEY) ?? "1") || 1,
    skipIntro: readFlag(SKIP_INTRO_KEY, true),
    skipOutro: readFlag(SKIP_OUTRO_KEY, true),
    autoNext: readFlag(AUTO_NEXT_KEY, true),
    introSec: readNum(SKIP_INTRO_SEC_KEY, 0),
    outroSec: readNum(SKIP_OUTRO_SEC_KEY, 0),
    volume: 1,
    muted: false,
    error: null,
    sleepMode: "off",
    sleepRemainingSec: 0,
    sleepChaptersLeft: 0,
    sleepFinishChapter: false,
    sleepWaitingChapterEnd: false,
    sleepChapterMark: 0,
    remoteProgress: null,
    syncNotice: null,
    jumpUndo: null,

    async open(bookId, options) {
      const current = get();
      if (current.book?.id === bookId && (audioEl || nativePlayer)) {
        if (!current.isPlaying) {
          // 先对齐账号的最新进度再播放：另一台设备可能已经听远了
          await get().syncFromServer();
          if (nativePlayer) {
            const token = getAccessToken();
            if (token) nativePlayer.setAuth?.(token);
            nativePlayer.resume();
          } else void audioEl?.play().catch(() => undefined);
        } else if (nativePlayer) {
          nativePlayer.pause();
        } else {
          audioEl?.pause();
        }
        return;
      }

      // 换书时旧的定时状态（章节序号、剩余集数）没有意义
      if (current.book?.id !== bookId) get().clearSleep();

      set({ isLoading: true, error: null });
      try {
        const [detail, playToken] = await Promise.all([
          api.bookDetail(bookId),
          api.playToken(bookId),
        ]);
        const tracks = withOffsets(detail.tracks);
        if (tracks.length === 0) {
          throw new Error("这本书没有可播放的音轨");
        }

        // 章节超过 500 条时详情会省略，兜底再拉一次
        let chapters = detail.chapters;
        if (chapters === null) {
          chapters = await api
            .chapters(bookId, 1, 500)
            .then((list) => list.items)
            .catch(() => []);
        }
        const bookDetail = { ...detail, chapters };

        const savedProgress = detail.progress?.position_sec ?? 0;
        const saved = Math.max(0, options?.positionSec ?? savedProgress);
        // 跳过片头：只在「从书本进度接着听」时生效；
        // 书签/检查点这类显式位置不干预（它们指向用户自己选的地方）。
        const intro =
          get().introSec > 0 ? get().introSec : (detail.intro_sec ?? 0);
        const isRestore =
          options?.positionSec === undefined ||
          Math.abs(options.positionSec - savedProgress) < 0.5;
        const start =
          isRestore && get().skipIntro && intro > 0 && saved < intro ? intro : saved;
        const target =
          (options?.trackId ? findTrackById(tracks, options.trackId) : null) ??
          trackAt(tracks, start) ??
          tracks[0];

        set({
          book: bookDetail,
          tracks,
          trackId: target.id,
          token: playToken.token,
          durationSec: detail.total_duration_sec,
          positionSec: start,
          isLoading: false,
          error: null,
        });

        rememberLastBook(bookDetail, start);

        if (nativePlayer) {
          audioEl?.pause();
          const intro =
            get().introSec > 0 ? get().introSec : (detail.intro_sec ?? 0);
          const outro =
            get().outroSec > 0 ? get().outroSec : (detail.outro_sec ?? 0);
          const nativeTracks = tracks.map((track) => {
            const clipStartSec =
              get().skipIntro && intro > 0 && intro < track.duration_sec
                ? intro
                : 0;
            const clipEndSec =
              get().skipOutro && outro > 0 && track.duration_sec > outro + 1
                ? track.duration_sec - outro
                : track.duration_sec;
            return {
              id: track.id,
              url: new URL(
                urlFor(track, playToken.token),
                window.location.origin,
              ).toString(),
              title: track.title || bookDetail.title,
              artist: detail.author ?? "",
              durationSec: track.duration_sec,
              offsetSec: track.offsetSec,
              clipStartSec,
              clipEndSec,
            };
          });
          const coverUrl = detail.cover_url
            ? new URL(detail.cover_url, window.location.origin).toString()
            : null;
          // 系统媒体通知对 http/带鉴权封面的加载并不可靠，直接把封面字节内嵌给原生。
          let coverData: string | null = null;
          if (coverUrl) {
            const coverController = new AbortController();
            const coverTimer = window.setTimeout(() => coverController.abort(), 3000);
            try {
              const response = await fetch(coverUrl, {
                signal: coverController.signal,
              });
              if (response.ok) {
                coverData = arrayBufferToBase64(await response.arrayBuffer());
              }
            } catch {
              // 拿不到封面就退回 coverUrl，不影响播放
            } finally {
              window.clearTimeout(coverTimer);
            }
          }
          const payload: NativePlayPayload = {
            tracks: nativeTracks,
            startIndex: Math.max(
              0,
              tracks.findIndex((track) => track.id === target.id),
            ),
            startPositionSec: start,
            rate: get().rate,
            coverUrl,
            coverData,
            bookId,
            baseUrl: window.location.origin,
            token: getAccessToken() ?? "",
            deviceId: deviceId(),
            resume: isRestore,
          };
          nativePlayer.play(JSON.stringify(payload));
          set({ isPlaying: true });
          startReporting();
          return;
        }

        if (!audioEl) return;
        audioEl.playbackRate = get().rate;
        audioEl.src = urlFor(target, playToken.token);
        audioEl.volume = get().volume;
        const offset = Math.max(
          0,
          Math.min(target.duration_sec, start - target.offsetSec),
        );
        audioEl.addEventListener(
          "loadedmetadata",
          () => {
            if (!audioEl) return;
            audioEl.currentTime = offset;
            void audioEl.play().catch(() => {
              set({ error: "浏览器拦截了自动播放，点一下播放键开始" });
            });
          },
          { once: true },
        );
      } catch (error) {
        set({
          isLoading: false,
          error: error instanceof Error ? error.message : "无法打开这本书",
        });
      }
    },

    toggle() {
      if (nativePlayer) {
        if (!get().book) return;
        const token = getAccessToken();
        if (token) nativePlayer.setAuth?.(token);
        if (get().isPlaying) nativePlayer.pause();
        else nativePlayer.resume();
        return;
      }
      if (!audioEl || !get().book) return;
      if (audioEl.paused) void audioEl.play().catch(() => undefined);
      else audioEl.pause();
    },

    seekTo(absoluteSec) {
      const state = get();
      const target = trackAt(state.tracks, absoluteSec);
      if (!target) return;

      if (nativePlayer) {
        const index = state.tracks.findIndex((track) => track.id === target.id);
        if (index >= 0) {
          nativePlayer.seekToTrack(index, absoluteSec - target.offsetSec);
        }
        set({ trackId: target.id, positionSec: absoluteSec });
        scheduleSeekReport();
        return;
      }

      if (!audioEl) return;
      if (target.id !== state.trackId) {
        switchTo(target, absoluteSec - target.offsetSec);
      } else {
        audioEl.currentTime = Math.max(
          0,
          Math.min(target.duration_sec, absoluteSec - target.offsetSec),
        );
        set({ positionSec: absoluteSec });
      }
      scheduleSeekReport();
    },

    seekWithUndo(absoluteSec) {
      const from = get().positionSec;
      get().seekTo(absoluteSec);

      // 小幅度拖动不上报撤销，避免正常微调也弹提示
      if (Math.abs(absoluteSec - from) < 300) return;

      set({ jumpUndo: { from, to: absoluteSec } });
      if (jumpUndoTimer !== null) window.clearTimeout(jumpUndoTimer);
      jumpUndoTimer = window.setTimeout(() => {
        usePlayer.setState({ jumpUndo: null });
        jumpUndoTimer = null;
      }, 10_000);
    },

    undoJump() {
      const jump = get().jumpUndo;
      if (!jump) return;
      if (jumpUndoTimer !== null) {
        window.clearTimeout(jumpUndoTimer);
        jumpUndoTimer = null;
      }
      set({ jumpUndo: null });
      get().seekTo(jump.from);
    },

    skip(deltaSec) {
      const state = get();
      if (!state.book) return;
      const target = Math.max(
        0,
        Math.min(state.durationSec - 0.5, state.positionSec + deltaSec),
      );
      state.seekTo(target);
    },

    nextTrack() {
      const state = get();
      const index = state.tracks.findIndex((track) => track.id === state.trackId);
      const next = state.tracks[index + 1];
      if (!next) return;
      // 逐集跳过片头：进入下一集（音频文件）时，从该集开头跳过 intro 秒
      const intro =
        state.introSec > 0 ? state.introSec : (state.book?.intro_sec ?? 0);
      const startInTrack =
        state.skipIntro && intro > 0 && intro < next.duration_sec ? intro : 0;
      switchTo(next, startInTrack);
    },

    prevTrack() {
      const state = get();
      if (nativePlayer) {
        const track = findTrackById(state.tracks, state.trackId);
        const inTrack = track ? state.positionSec - track.offsetSec : 0;
        if (track && inTrack > 5) {
          const index = state.tracks.findIndex((item) => item.id === track.id);
          if (index >= 0) nativePlayer.seekToTrack(index, 0);
        } else {
          nativePlayer.previous();
        }
        return;
      }
      // 播过 5 秒先回本轨开头，再往上一轨
      if (audioEl && audioEl.currentTime > 5) {
        audioEl.currentTime = 0;
        return;
      }
      const index = state.tracks.findIndex((track) => track.id === state.trackId);
      const prev = state.tracks[index - 1];
      if (prev) switchTo(prev, 0);
    },

    nextChapter() {
      const state = get();
      const chapters = state.book?.chapters;
      if (!chapters || chapters.length === 0) {
        state.nextTrack();
        return;
      }
      const index = chapterIndexAt(chapters, state.positionSec);
      const next = chapters[index + 1];
      if (next) state.seekTo(next.start_sec);
    },

    prevChapter() {
      const state = get();
      const chapters = state.book?.chapters;
      if (!chapters || chapters.length === 0) {
        state.prevTrack();
        return;
      }
      const index = chapterIndexAt(chapters, state.positionSec);
      const current = chapters[index];
      // 本章已播 5 秒以上先回章首，否则退到上一章
      if (current && state.positionSec - current.start_sec > 5) {
        state.seekTo(current.start_sec);
        return;
      }
      const prev = chapters[index - 1];
      if (prev) state.seekTo(prev.start_sec);
    },

    setRate(rate) {
      localStorage.setItem(RATE_KEY, String(rate));
      if (nativePlayer) nativePlayer.setRate(rate);
      if (audioEl) audioEl.playbackRate = rate;
      set({ rate });
      get().reportProgress(false);
    },

    setSkipIntro(value) {
      localStorage.setItem(SKIP_INTRO_KEY, value ? "1" : "0");
      set({ skipIntro: value });
    },

    setSkipOutro(value) {
      localStorage.setItem(SKIP_OUTRO_KEY, value ? "1" : "0");
      set({ skipOutro: value });
    },

    setAutoNext(value) {
      localStorage.setItem(AUTO_NEXT_KEY, value ? "1" : "0");
      set({ autoNext: value });
    },

    setIntroSec(value) {
      const v = Math.max(0, Math.round(value));
      localStorage.setItem(SKIP_INTRO_SEC_KEY, String(v));
      set({ introSec: v });
    },

    setOutroSec(value) {
      const v = Math.max(0, Math.round(value));
      localStorage.setItem(SKIP_OUTRO_SEC_KEY, String(v));
      set({ outroSec: v });
    },

    setVolume(volume) {
      const clamped = Math.max(0, Math.min(1, volume));
      if (nativePlayer) nativePlayer.setVolume(clamped);
      if (audioEl) {
        audioEl.volume = clamped;
        audioEl.muted = clamped === 0;
      }
      set({ volume: clamped, muted: clamped === 0 });
    },

    toggleMute() {
      if (nativePlayer) {
        const next = !get().muted;
        nativePlayer.setVolume(next ? 0 : get().volume);
        set({ muted: next });
        return;
      }
      if (!audioEl) return;
      audioEl.muted = !audioEl.muted;
      set({ muted: audioEl.muted });
    },

    close() {
      get().reportProgress(false);
      get().clearSleep();
      stopReporting();
      if (nativePlayer) nativePlayer.stop();
      if (audioEl) {
        audioEl.pause();
        audioEl.removeAttribute("src");
        audioEl.load();
      }
      set({
        book: null,
        tracks: [],
        trackId: null,
        token: null,
        isPlaying: false,
        positionSec: 0,
        durationSec: 0,
        error: null,
      });
    },

    setSleepDuration(minutes, finishChapter) {
      const state = get();
      if (audioEl) audioEl.volume = state.volume;
      const chapters = state.book?.chapters ?? [];
      set({
        sleepMode: "duration",
        sleepRemainingSec: Math.max(60, Math.round(minutes * 60)),
        sleepChaptersLeft: 0,
        sleepFinishChapter: finishChapter,
        sleepWaitingChapterEnd: false,
        sleepChapterMark: chapterIndexAt(chapters, state.positionSec),
      });
      startSleepTicker();
    },

    setSleepChapters(count) {
      const state = get();
      if (audioEl) audioEl.volume = state.volume;
      const chapters = state.book?.chapters ?? [];
      set({
        sleepMode: "chapters",
        sleepChaptersLeft: Math.max(1, Math.round(count)),
        sleepRemainingSec: 0,
        sleepFinishChapter: false,
        sleepWaitingChapterEnd: false,
        sleepChapterMark: chapterIndexAt(chapters, state.positionSec),
      });
      stopSleepTicker();
    },

    setSleepFinishChapter(value) {
      const state = get();
      if (!value && state.sleepWaitingChapterEnd) {
        // 已经到点且在等本集结束：取消「播完本集」就直接停
        state.pauseForSleep();
        return;
      }
      set({ sleepFinishChapter: value });
    },

    clearSleep() {
      stopSleepTicker();
      // 淡出可能把音量压低了，恢复用户设置的值
      if (audioEl) audioEl.volume = get().volume;
      set({
        sleepMode: "off",
        sleepRemainingSec: 0,
        sleepChaptersLeft: 0,
        sleepFinishChapter: false,
        sleepWaitingChapterEnd: false,
      });
    },

    pauseForSleep() {
      if (nativePlayer) nativePlayer.pause();
      else audioEl?.pause();
      get().clearSleep();
    },

    async syncFromServer() {
      const state = get();
      if (!state.book) return;

      const nowMs = Date.now();
      if (nowMs - lastSyncAt < 8000) return;
      lastSyncAt = nowMs;

      try {
        const { items } = await api.recentProgress(10);
        const mine = deviceId();
        const nowSec = Math.floor(Date.now() / 1000);

        // 找「最近 2 分钟内、另一台设备」写的最新一条：
        // 只取 items[0] 会被本机自己的写入盖住，看不到别人。
        const latest = items.find(
          (item) =>
            item.device_id !== mine && nowSec - item.updated_at <= 120,
        );
        if (!latest) return;

        if (latest.book_id !== state.book.id) {
          const key = `${latest.book_id}:${latest.updated_at}`;
          if (dismissedRemoteKey === key) return;
          set({
            remoteProgress: {
              bookId: latest.book_id,
              title: latest.title,
              positionSec: latest.position_sec,
              deviceId: latest.device_id,
              updatedAt: latest.updated_at,
            },
          });
          return;
        }

        set({ remoteProgress: null });
        // 同一本书：播放中不打断，暂停时才跟随过去
        if (state.isPlaying) return;
        if (Math.abs(latest.position_sec - state.positionSec) < 15) return;
        state.seekTo(latest.position_sec);
        flashNotice("已同步其他设备的进度");
      } catch {
        // 网络抖动时静默失败，下一次回到前台会重试
      }
    },

    dismissRemote() {
      const remote = get().remoteProgress;
      if (remote) dismissedRemoteKey = `${remote.bookId}:${remote.updatedAt}`;
      set({ remoteProgress: null });
    },

    handleSleepTick(positionSec) {
      const state = get();
      if (state.sleepMode === "off") return;

      const chapters = state.book?.chapters ?? [];
      const unitIndex =
        chapters.length > 0
          ? chapterIndexAt(chapters, positionSec)
          : state.tracks.findIndex((track) => track.id === state.trackId);

      if (state.sleepMode === "chapters") {
        if (unitIndex > state.sleepChapterMark) {
          const left =
            state.sleepChaptersLeft - (unitIndex - state.sleepChapterMark);
          if (left <= 0) {
            state.pauseForSleep();
            return;
          }
          set({ sleepChaptersLeft: left, sleepChapterMark: unitIndex });
        } else if (unitIndex < state.sleepChapterMark) {
          // 用户手动回退，不算「又听完一集」
          set({ sleepChapterMark: unitIndex });
        }
        return;
      }

      if (!state.sleepWaitingChapterEnd) return;
      const boundary =
        chapters.length > 0
          ? (chapters[unitIndex]?.end_sec ?? Number.POSITIVE_INFINITY)
          : state.durationSec;
      if (positionSec >= boundary - 0.15) {
        state.pauseForSleep();
      }
    },

    reportProgress(explicitSeek = false, keepalive = false) {
      const state = get();
      const book = state.book;
      if (!book) return;

      const token = getAccessToken();
      // 网页平时每 15 秒会调到这里，顺手把刷新后的 token 推给原生服务。
      if (nativePlayer && token) nativePlayer.setAuth?.(token);

      const payload = {
        track_id: state.trackId,
        position_sec: Number(state.positionSec.toFixed(3)),
        playback_rate: state.rate,
        device_id: deviceId(),
        client_updated_at: Math.floor(Date.now() / 1000),
        explicit_seek: explicitSeek,
      };

      if (keepalive) {
        // 页面卸载时用 keepalive 请求，sendBeacon 无法携带 Authorization
        fetch(`/api/v1/progress/${book.id}`, {
          method: "PUT",
          keepalive: true,
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token ?? ""}`,
          },
          body: JSON.stringify(payload),
        }).catch(() => undefined);
        return;
      }

      api.putProgress(book.id, payload).catch(() => undefined);
    },
  };
});

/** PlayerBar 挂载时调用，把原生 audio 事件接到 store 上。 */
export function bindAudioElement(element: HTMLAudioElement | null): void {
  audioEl = element;
  if (!element || element.dataset.bound === "1") return;
  element.dataset.bound = "1";
  element.volume = usePlayer.getState().volume;

  element.addEventListener("play", () => {
    usePlayer.setState({ isPlaying: true, error: null });
    // 一开播就抢占进度：切设备时以「最后按下播放的那台」为准
    usePlayer.getState().reportProgress(false);
    startReporting();
  });

  element.addEventListener("pause", () => {
    usePlayer.setState({ isPlaying: false });
    stopReporting();
    usePlayer.getState().reportProgress(false);
  });

  element.addEventListener("timeupdate", () => {
    const state = usePlayer.getState();
    const track = findTrackById(state.tracks, state.trackId);
    if (!track) return;
    const positionSec = track.offsetSec + element.currentTime;
    usePlayer.setState({ positionSec });

    // 跳过片尾：按「当前这一集（音频文件）」的结尾计算，到点切下一集；最后一集则停住
    const outro =
      state.outroSec > 0 ? state.outroSec : (state.book?.outro_sec ?? 0);
    const trackEnd = track.offsetSec + track.duration_sec;
    if (
      state.skipOutro &&
      state.autoNext &&
      outro > 0 &&
      track.duration_sec > outro + 1 &&
      positionSec >= trackEnd - outro
    ) {
      const trackIndex = state.tracks.findIndex((item) => item.id === state.trackId);
      if (trackIndex >= 0 && trackIndex < state.tracks.length - 1) {
        state.nextTrack();
        return;
      }
      element.pause();
      return;
    }

    state.handleSleepTick(positionSec);
  });

  element.addEventListener("ended", () => {
    const state = usePlayer.getState();
    const chapters = state.book?.chapters ?? [];

    // 整轨没有章节信息时，「一集」等于一轨
    if (chapters.length === 0) {
      if (state.sleepWaitingChapterEnd) {
        state.pauseForSleep();
        return;
      }
      if (state.sleepMode === "chapters") {
        const left = state.sleepChaptersLeft - 1;
        if (left <= 0) {
          state.pauseForSleep();
          return;
        }
        usePlayer.setState({ sleepChaptersLeft: left });
      }
    }

    // 关闭自动连播时，一集播完就停在结尾
    if (!state.autoNext) {
      usePlayer.setState({ isPlaying: false, positionSec: state.durationSec });
      state.reportProgress(true);
      return;
    }

    const index = state.tracks.findIndex((track) => track.id === state.trackId);
    if (index >= 0 && index < state.tracks.length - 1) {
      state.nextTrack();
      return;
    }
    usePlayer.setState({ isPlaying: false, positionSec: state.durationSec });
    usePlayer.getState().reportProgress(true);
  });

  element.addEventListener("error", () => {
    usePlayer.setState({ isPlaying: false, error: "音频加载失败，请重试" });
  });
}

/**
 * 原生播放状态回调：Android 壳每 500ms 推一次，更新网页 UI。
 * 普通浏览器不会走到这里。
 */
function setupNativePlayerState(): void {
  if (!nativePlayer) return;
  window.__shelfPlayer = window.__shelfPlayer ?? {};
  // 网页暂停/后台时也定期把可能已刷新的 token 推给原生服务；真正播放时
  // reportProgress 还会每 15 秒推一次。
  window.setInterval(() => {
    const token = getAccessToken();
    if (token) nativePlayer.setAuth?.(token);
  }, 60_000);

  window.__shelfPlayer.onState = (json: string) => {
    try {
      const state = JSON.parse(json) as NativeState;
      const current = usePlayer.getState();
      if (!current.book) return;
      const hasError = Boolean(state.error);
      const track = hasError ? null : current.tracks[state.trackIndex];
      const wasPlaying = current.isPlaying;
      const nativeVolume =
        !hasError && typeof state.volume === "number"
          ? state.volume
          : current.volume;
      usePlayer.setState({
        isPlaying: hasError ? false : Boolean(state.playing),
        isLoading: hasError ? false : Boolean(state.buffering),
        positionSec: hasError
          ? current.positionSec
          : Number(state.positionSec) || 0,
        trackId: track?.id ?? current.trackId,
        rate: Number(state.rate) || current.rate,
        volume: nativeVolume,
        muted: nativeVolume === 0,
        error: state.error ?? null,
      });
      current.handleSleepTick(Number(state.positionSec) || 0);
      if (wasPlaying && !state.playing && !state.buffering) {
        stopReporting();
        usePlayer.getState().reportProgress(false);
      }
      if (!wasPlaying && state.playing) {
        startReporting();
      }
    } catch {
      // 原生状态格式异常时忽略，不影响网页播放
    }
  };
}

setupNativePlayerState();
