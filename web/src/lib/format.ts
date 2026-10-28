/** 时长、数字与相对时间格式化。 */

export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "—";
  const total = Math.round(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.round((total % 3600) / 60);
  if (hours > 0) return `${hours} 小时 ${minutes} 分`;
  return `${minutes} 分`;
}

export function formatRelative(epochSeconds: number): string {
  if (!epochSeconds) return "—";
  const diff = Date.now() / 1000 - epochSeconds;
  if (diff < 60) return "刚刚";
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前`;
  return new Date(epochSeconds * 1000).toLocaleDateString("zh-CN");
}

export function formatCount(value: number): string {
  return value.toLocaleString("zh-CN");
}

/** 播放器用的时钟格式：m:ss 或 h:mm:ss。 */
export function formatClock(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const total = Math.floor(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const pad = (value: number) => String(value).padStart(2, "0");
  if (hours > 0) return `${hours}:${pad(minutes)}:${pad(secs)}`;
  return `${minutes}:${pad(secs)}`;
}

export function initialOf(text: string): string {
  return Array.from(text.trim())[0] ?? "书";
}

/** 由书名派生稳定色相（0–359），用于生成无封面时的渐变占位。 */
export function hueOf(text: string): number {
  let hash = 0;
  for (const char of text) {
    hash = (hash * 31 + char.codePointAt(0)!) % 360;
  }
  return hash;
}

/** 无封面时的渐变背景，同一本书始终一致。 */
export function coverGradient(text: string): string {
  const hue = hueOf(text);
  return `linear-gradient(150deg, hsl(${hue} 46% 42%), hsl(${(hue + 40) % 360} 50% 20%))`;
}
