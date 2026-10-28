import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // 由 CSS 变量驱动，运行时切换主题色（src/styles/accent.ts）
        brand: {
          50: "rgb(var(--brand-50) / <alpha-value>)",
          100: "rgb(var(--brand-100) / <alpha-value>)",
          200: "rgb(var(--brand-200) / <alpha-value>)",
          300: "rgb(var(--brand-300) / <alpha-value>)",
          400: "rgb(var(--brand-400) / <alpha-value>)",
          500: "rgb(var(--brand-500) / <alpha-value>)",
          600: "rgb(var(--brand-600) / <alpha-value>)",
          700: "rgb(var(--brand-700) / <alpha-value>)",
          800: "rgb(var(--brand-800) / <alpha-value>)",
          900: "rgb(var(--brand-900) / <alpha-value>)",
        },
        ink: {
          950: "#0b0d10",
          900: "#111418",
          850: "#161a20",
          800: "#1c2129",
          700: "#2a313b",
          600: "#3b4552",
        },
      },
      borderRadius: {
        card: "12px",
      },
      fontFamily: {
        sans: [
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "PingFang SC",
          "Hiragino Sans GB",
          "Microsoft YaHei",
          "sans-serif",
        ],
      },
      boxShadow: {
        // 全部用品牌色变量，换主题色时阴影跟着变
        glow: "0 0 0 1px rgb(var(--brand-500) / 0.35), 0 14px 44px -14px rgb(var(--brand-500) / 0.45)",
        "glow-sm": "0 10px 28px -12px rgb(var(--brand-500) / 0.55)",
        "glow-lg": "0 28px 80px -24px rgb(var(--brand-500) / 0.6)",
        lift: "0 20px 46px -26px rgba(8, 10, 14, 0.5)",
      },
      backgroundImage: {
        "brand-fade":
          "radial-gradient(1200px 420px at 8% -12%, rgb(var(--brand-500) / 0.22), transparent 62%)",
        "brand-gradient":
          "linear-gradient(135deg, rgb(var(--brand-400)) 0%, rgb(var(--brand-500)) 48%, rgb(var(--brand-600)) 100%)",
        "brand-sheen":
          "linear-gradient(140deg, rgba(255,255,255,0.26), rgba(255,255,255,0) 46%)",
        "card-fade":
          "linear-gradient(to top, rgba(11,13,16,0.78) 0%, rgba(11,13,16,0) 58%)",
      },
    },
  },
  plugins: [],
} satisfies Config;
