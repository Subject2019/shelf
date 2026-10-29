/**
 * 从浏览器里采集设备指纹，登录时上报给服务端。
 *
 * 目标：设备列表能显示「Chrome 141 · Android 14 · 390×844」，而不是只有一个「网页版」。
 * 全部基于 navigator，不引第三方 UA 解析库（省 100KB+，规则够用）。
 */

export type FormFactor = "phone" | "tablet" | "desktop";

export interface DeviceProfile {
  name: string;
  platform: "web";
  app_version: string;
  os: string;
  form_factor: FormFactor;
  screen: string;
  user_agent: string;
}

/** 顺序很重要：微信/QQ/UC 的 UA 里也带 Chrome/Safari。 */
const BROWSERS: [RegExp, string][] = [
  [/MicroMessenger\/([\d.]+)/, "微信"],
  [/MQQBrowser\/([\d.]+)/, "QQ 浏览器"],
  [/UCBrowser\/([\d.]+)/, "UC 浏览器"],
  [/HuaweiBrowser\/([\d.]+)/, "华为浏览器"],
  [/MiuiBrowser\/([\d.]+)/, "小米浏览器"],
  [/SamsungBrowser\/([\d.]+)/, "三星浏览器"],
  [/Edg(?:A|iOS)?\/([\d.]+)/, "Edge"],
  [/OPR\/([\d.]+)/, "Opera"],
  [/Firefox\/([\d.]+)/, "Firefox"],
  [/Chrome\/([\d.]+)/, "Chrome"],
  [/Version\/([\d.]+).*Safari/, "Safari"],
];

function browserOf(userAgent: string): { name: string; version: string } {
  for (const [pattern, name] of BROWSERS) {
    const match = userAgent.match(pattern);
    if (match) {
      return { name, version: match[1].split(".")[0] ?? "" };
    }
  }
  return { name: "浏览器", version: "" };
}

function osOf(userAgent: string): string {
  const android = userAgent.match(/Android\s([\d.]+)/);
  if (android) return `Android ${android[1]}`;

  const ios = userAgent.match(/(?:iPhone )?OS (\d+)[._](\d+)/);
  if (ios) return `iOS ${ios[1]}.${ios[2]}`;

  if (/HarmonyOS|OpenHarmony/.test(userAgent)) return "HarmonyOS";
  if (/Windows NT 10/.test(userAgent)) return "Windows 10/11";
  if (/Windows NT 6\.3/.test(userAgent)) return "Windows 8.1";
  if (/Windows NT 6\.1/.test(userAgent)) return "Windows 7";
  if (/Mac OS X/.test(userAgent)) return "macOS";
  if (/CrOS/.test(userAgent)) return "ChromeOS";
  if (/Linux/.test(userAgent)) return "Linux";
  return "未知系统";
}

function formFactorOf(userAgent: string): FormFactor {
  // iPadOS 13+ 的 UA 伪装成 macOS，只能靠触点数区分
  if (
    /iPad|Tablet/i.test(userAgent) ||
    (navigator.maxTouchPoints > 1 && /Macintosh/.test(userAgent))
  ) {
    return "tablet";
  }
  if (/Mobi|Android|iPhone/i.test(userAgent)) return "phone";
  return "desktop";
}

export function describeDevice(): DeviceProfile {
  const userAgent = navigator.userAgent;
  const browser = browserOf(userAgent);
  const dpr = Math.round(window.devicePixelRatio * 10) / 10;

  return {
    name: browser.version ? `${browser.name} ${browser.version}` : browser.name,
    platform: "web",
    app_version: "0.2.7",
    os: osOf(userAgent),
    form_factor: formFactorOf(userAgent),
    screen: `${window.screen.width}×${window.screen.height}${dpr > 1 ? ` · ${dpr}x` : ""}`,
    user_agent: userAgent,
  };
}

/** 设备列表里的形态标签 */
export function formFactorLabel(value: string | null | undefined): string {
  return { phone: "手机", tablet: "平板", desktop: "桌面" }[value ?? ""] ?? "";
}
