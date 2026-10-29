/**
 * Android WebView 壳注入的原生播放桥（window.ShelfPlayer）。
 * 网页端检测到它时，把音频交给原生 Media3 播放，以支持状态栏/锁屏控制与后台播放；
 * 普通浏览器没有这个对象，继续走 <audio>。
 */

export interface NativeTrackPayload {
  id: number;
  url: string;
  title: string;
  artist?: string;
  durationSec: number;
  offsetSec: number;
  clipStartSec: number;
  clipEndSec: number;
}

export interface NativePlayPayload {
  tracks: NativeTrackPayload[];
  startIndex: number;
  startPositionSec: number;
  rate: number;
  coverUrl?: string | null;
  /** 封面图的 base64（不带 data: 前缀）；有它时原生优先用内嵌 artwork，避免 HTTP 加载失败 */
  coverData?: string | null;
  /** 当前书籍 ID，原生服务据此直接上报进度 */
  bookId: number;
  /** 服务器根地址，例如 http://192.168.1.10:8080 */
  baseUrl: string;
  /** 当前 access token；原生服务不落盘，只在内存中使用 */
  token: string;
  deviceId: string;
  /** 是否从服务器进度恢复；只有恢复时才允许被原生本地较新进度覆盖 */
  resume: boolean;
}

export interface NativeState {
  playing: boolean;
  buffering: boolean;
  trackIndex: number;
  trackId: number;
  positionSec: number;
  rate: number;
  /** 原生播放器音量（0~1）；通知栏/锁屏调整音量时回传 */
  volume?: number;
  error: string | null;
}

export interface ShelfPlayerBridge {
  play(payload: string): void;
  setAuth(token: string): void;
  pause(): void;
  resume(): void;
  seekTo(absoluteSec: number): void;
  seekToTrack(index: number, positionInTrackSec: number): void;
  setRate(rate: number): void;
  setVolume(volume: number): void;
  next(): void;
  previous(): void;
  stop(): void;
}

declare global {
  interface Window {
    ShelfPlayer?: ShelfPlayerBridge;
    __shelfPlayer?: {
      onState?: (json: string) => void;
    };
  }
}

export function getNativePlayer(): ShelfPlayerBridge | null {
  if (typeof window === "undefined") return null;
  return window.ShelfPlayer ?? null;
}
