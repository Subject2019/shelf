import { RATES } from "../../lib/playback";
import { usePlayer } from "../../store/player";

const TOGGLES = [
  {
    key: "skipIntro" as const,
    label: "自动跳过片头",
    hint: "每集（每个音频文件）开头跳过设定的秒数",
  },
  {
    key: "skipOutro" as const,
    label: "自动跳过片尾",
    hint: "每集（每个音频文件）结尾前按设定的秒数切到下一集（需要开启自动连播）",
  },
  {
    key: "autoNext" as const,
    label: "自动连播下一集",
    hint: "关闭后一集播完会停在结尾，不再自动继续",
  },
];

/** 播放偏好：保存在本设备浏览器，不写服务端账号。 */
export default function PlaybackSection() {
  const rate = usePlayer((state) => state.rate);
  const setRate = usePlayer((state) => state.setRate);
  const skipIntro = usePlayer((state) => state.skipIntro);
  const skipOutro = usePlayer((state) => state.skipOutro);
  const autoNext = usePlayer((state) => state.autoNext);
  const setSkipIntro = usePlayer((state) => state.setSkipIntro);
  const setSkipOutro = usePlayer((state) => state.setSkipOutro);
  const setAutoNext = usePlayer((state) => state.setAutoNext);
  const introSec = usePlayer((state) => state.introSec);
  const outroSec = usePlayer((state) => state.outroSec);
  const setIntroSec = usePlayer((state) => state.setIntroSec);
  const setOutroSec = usePlayer((state) => state.setOutroSec);
  const values = { skipIntro, skipOutro, autoNext };
  const setters = {
    skipIntro: setSkipIntro,
    skipOutro: setSkipOutro,
    autoNext: setAutoNext,
  };

  return (
    <section className="glass rounded-2xl p-5 shadow-lift sm:p-6">
      <h2 className="text-sm font-semibold">播放偏好</h2>

      <div className="mt-4">
        <p className="text-xs text-zinc-500">默认倍速（播放器里也能随时改）</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {RATES.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setRate(item)}
              className={[
                "rounded-lg border px-3 py-1 text-xs tabular-nums transition",
                item === rate
                  ? "border-brand-500 bg-brand-500/10 font-semibold text-brand-500"
                  : "border-zinc-200 text-zinc-600 hover:border-brand-500/40 dark:border-white/10 dark:text-zinc-300",
              ].join(" ")}
            >
              {item}×
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 space-y-3">
        {TOGGLES.map((item) => {
          const checked = values[item.key];
          return (
            <div key={item.key} className="space-y-2">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm">{item.label}</p>
                  <p className="mt-0.5 text-xs text-zinc-500">{item.hint}</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={checked}
                  aria-label={item.label}
                  onClick={() => setters[item.key](!checked)}
                  className={[
                    "mt-0.5 h-5 w-9 shrink-0 rounded-full p-0.5 transition",
                    checked ? "bg-brand-500" : "bg-zinc-300 dark:bg-white/15",
                  ].join(" ")}
                >
                  <span
                    className={[
                      "block size-4 rounded-full bg-white shadow transition",
                      checked ? "translate-x-4" : "translate-x-0",
                    ].join(" ")}
                  />
                </button>
              </div>
              {item.key === "skipIntro" && checked && (
                <label className="flex items-center gap-2 text-xs text-zinc-500">
                  片头跳过
                  <input
                    type="number"
                    min={0}
                    step={1}
                    inputMode="numeric"
                    value={introSec || ""}
                    placeholder="0"
                    onChange={(event) => setIntroSec(Number(event.target.value))}
                    className="h-8 w-16 rounded-lg border border-zinc-200 bg-white px-2 text-center text-sm tabular-nums outline-none focus:border-brand-500 dark:border-white/10 dark:bg-white/[0.06]"
                  />
                  秒
                </label>
              )}
              {item.key === "skipOutro" && checked && (
                <label className="flex items-center gap-2 text-xs text-zinc-500">
                  片尾跳过
                  <input
                    type="number"
                    min={0}
                    step={1}
                    inputMode="numeric"
                    value={outroSec || ""}
                    placeholder="0"
                    onChange={(event) => setOutroSec(Number(event.target.value))}
                    className="h-8 w-16 rounded-lg border border-zinc-200 bg-white px-2 text-center text-sm tabular-nums outline-none focus:border-brand-500 dark:border-white/10 dark:bg-white/[0.06]"
                  />
                  秒
                </label>
              )}
            </div>
          );
        })}
      </div>

      <p className="mt-4 text-[11px] text-zinc-400 dark:text-zinc-500">
        秒数按「每个音频文件（每一集）」生效，对多音频文件的书逐集跳过；单个大文件（内含章节）只在整本开头/结尾生效。填 0 表示沿用书籍自身设置；以上偏好只保存在这台设备的浏览器中。
      </p>
    </section>
  );
}
