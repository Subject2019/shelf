/** 界面偏好：深浅主题 + 主题色，均保存在本机。 */

import { create } from "zustand";

import { ACCENTS, applyAccent, isValidHex, presetOf, type AccentId } from "../styles/accent";

export type Theme = "dark" | "light";

const THEME_KEY = "echoshelf.theme";
const ACCENT_KEY = "echoshelf.accent";
const DEFAULT_ACCENT = ACCENTS[0].hex;

/** 手机浏览器的地址栏/状态栏跟着变，否则切浅色后顶部仍是黑的 */
const THEME_COLORS: Record<Theme, string> = {
  dark: "#0b0d10",
  light: "#fafafa",
};

function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.style.colorScheme = theme;

  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", THEME_COLORS[theme]);
}

function initialTheme(): Theme {
  return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
}

function initialAccent(): string {
  const saved = localStorage.getItem(ACCENT_KEY);
  return saved && isValidHex(saved) ? saved : DEFAULT_ACCENT;
}

const initialThemeValue = initialTheme();
const initialAccentHex = initialAccent();
applyTheme(initialThemeValue);
applyAccent(initialAccentHex);

interface UiState {
  theme: Theme;
  accent: AccentId;
  accentHex: string;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  setAccent: (accent: AccentId, hex?: string) => void;
}

export const useUi = create<UiState>((set, get) => ({
  theme: initialThemeValue,
  accent: presetOf(initialAccentHex),
  accentHex: initialAccentHex,

  setTheme(theme: Theme) {
    localStorage.setItem(THEME_KEY, theme);
    applyTheme(theme);
    set({ theme });
  },

  toggleTheme() {
    get().setTheme(get().theme === "dark" ? "light" : "dark");
  },

  setAccent(accent: AccentId, hex?: string) {
    const value = hex ?? ACCENTS.find((item) => item.id === accent)?.hex;
    if (!value || !isValidHex(value) || !applyAccent(value)) return;
    localStorage.setItem(ACCENT_KEY, value);
    set({ accent, accentHex: value });
  },
}));
