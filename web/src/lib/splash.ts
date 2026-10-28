/** 启动屏（<shelf-launch-splash>）就绪信号的 TS 封装。 */

interface ShelfSplashApi {
  /** 应用首屏已就绪，启动屏可以退场；可重复调用，组件内部会去重。 */
  ready?: () => void;
  /** 立即跳过启动屏。 */
  skip?: () => void;
  /** 当前是否有启动屏在显示。 */
  active?: boolean;
}

function splash(): ShelfSplashApi | undefined {
  return (window as unknown as { ShelfSplash?: ShelfSplashApi }).ShelfSplash;
}

/** 首屏渲染完成、用户可以开始交互时调用一次。 */
export function splashReady(): void {
  splash()?.ready?.();
}

/** 立即隐藏启动屏（如初始化异常兜底）。 */
export function splashSkip(): void {
  splash()?.skip?.();
}

/** 启动屏是否还在显示。 */
export function splashActive(): boolean {
  return Boolean(splash()?.active);
}
