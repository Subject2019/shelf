/**
 * 主题色系统：只维护一个主色 hex，自动推导 Tailwind 的 brand 50–900 色阶，
 * 写入 CSS 变量供 `bg-brand-500/10` 这类带透明度的类使用。
 */

export interface AccentPreset {
  id: string;
  label: string;
  hex: string;
}

export const ACCENTS: AccentPreset[] = [
  { id: "amber", label: "暖橙", hex: "#E8843C" },
  { id: "ocean", label: "海蓝", hex: "#3B82F6" },
  { id: "violet", label: "紫罗兰", hex: "#8B5CF6" },
  { id: "emerald", label: "松绿", hex: "#10B981" },
  { id: "rose", label: "玫红", hex: "#F43F5E" },
  { id: "slate", label: "石墨", hex: "#64748B" },
];

export type AccentId = string;

interface Rgb {
  r: number;
  g: number;
  b: number;
}

const WHITE: Rgb = { r: 255, g: 255, b: 255 };
const BLACK: Rgb = { r: 0, g: 0, b: 0 };

const SCALE: { step: number; mixWith: "white" | "black" | null; weight: number }[] = [
  { step: 50, mixWith: "white", weight: 0.92 },
  { step: 100, mixWith: "white", weight: 0.84 },
  { step: 200, mixWith: "white", weight: 0.68 },
  { step: 300, mixWith: "white", weight: 0.46 },
  { step: 400, mixWith: "white", weight: 0.22 },
  { step: 500, mixWith: null, weight: 0 },
  { step: 600, mixWith: "black", weight: 0.12 },
  { step: 700, mixWith: "black", weight: 0.26 },
  { step: 800, mixWith: "black", weight: 0.42 },
  { step: 900, mixWith: "black", weight: 0.56 },
];

export function isValidHex(value: string): boolean {
  return /^#[0-9a-fA-F]{6}$/.test(value.trim());
}

function hexToRgb(hex: string): Rgb | null {
  if (!isValidHex(hex)) return null;
  const value = hex.trim().slice(1);
  return {
    r: Number.parseInt(value.slice(0, 2), 16),
    g: Number.parseInt(value.slice(2, 4), 16),
    b: Number.parseInt(value.slice(4, 6), 16),
  };
}

function mix(from: Rgb, to: Rgb, weight: number): Rgb {
  return {
    r: Math.round(from.r + (to.r - from.r) * weight),
    g: Math.round(from.g + (to.g - from.g) * weight),
    b: Math.round(from.b + (to.b - from.b) * weight),
  };
}

/** 把主色写入 --brand-* 变量；返回是否成功。 */
export function applyAccent(hex: string): boolean {
  const base = hexToRgb(hex);
  if (!base) return false;

  const root = document.documentElement;
  for (const { step, mixWith, weight } of SCALE) {
    const color = mixWith ? mix(base, mixWith === "white" ? WHITE : BLACK, weight) : base;
    root.style.setProperty(`--brand-${step}`, `${color.r} ${color.g} ${color.b}`);
  }
  root.dataset.accent = presetOf(hex);
  return true;
}

export function presetOf(hex: string): AccentId {
  const normalized = hex.trim().toLowerCase();
  return ACCENTS.find((item) => item.hex.toLowerCase() === normalized)?.id ?? "custom";
}
