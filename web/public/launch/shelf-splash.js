/*
 * SHELF launch splash
 * A self-contained PWA splash overlay. Integrate once, then call
 * window.ShelfSplash.ready() when the app's initial screen is ready.
 *
 * v1.0.0 — no external dependencies.
 */
(() => {
  "use strict";

  const TAG = "shelf-launch-splash";
  if (customElements.get(TAG)) return;

  const EASE = "cubic-bezier(.16, 1, .3, 1)";
  const EASE_SOFT = "cubic-bezier(.33, 1, .68, 1)";
  const REDUCED_QUERY = "(prefers-reduced-motion: reduce)";
  const CURRENT_VERSION = "1.0.0";

  const CSS = `
    :host {
      --splash-paper: #f1ede4;
      --splash-ink: #111110;
      --splash-accent: #f05a32;
      --splash-muted: rgba(17, 17, 16, .52);
      --splash-quiet: rgba(17, 17, 16, .34);
      --splash-line: rgba(17, 17, 16, .13);
      --splash-hairline: rgba(17, 17, 16, .075);
      --splash-sans: "Helvetica Neue", Helvetica, "Segoe UI", Arial, sans-serif;
      --splash-mono: "SFMono-Regular", "Cascadia Mono", "Roboto Mono", Menlo, Consolas, monospace;
      --splash-logo-width: min(60vw, 37vh, 380px);
      --splash-edge-x: clamp(24px, 4vw, 58px);
      --splash-edge-y: clamp(22px, 4.2vh, 42px);

      position: fixed;
      inset: 0;
      z-index: 999999;
      display: block;
      overflow: hidden;
      background: var(--splash-paper);
      color: var(--splash-ink);
      font-family: var(--splash-sans);
      opacity: 1;
      margin: 0;
      border: 0;
      transition: opacity 420ms cubic-bezier(.22, 1, .36, 1);
      overscroll-behavior: contain;
      touch-action: none;
      user-select: none;
      -webkit-user-select: none;
      -webkit-tap-highlight-color: transparent;
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
      color-scheme: light;
    }

    :host([hidden]),
    :host(.is-leaving) {
      pointer-events: none;
    }

    :host([hidden]) {
      display: none !important;
    }

    :host(.is-leaving) {
      opacity: 0;
    }

    *, *::before, *::after {
      box-sizing: border-box;
    }

    button {
      font: inherit;
    }

    .stage {
      position: absolute;
      inset: 0;
      isolation: isolate;
      overflow: hidden;
      background:
        radial-gradient(120% 90% at 50% -8%, rgba(255, 255, 255, .85) 0%, rgba(255, 255, 255, 0) 58%),
        linear-gradient(180deg, #f6f2ea 0%, var(--splash-paper) 46%, #eae4d8 100%);
    }

    /* ---------- atmosphere ---------- */

    .atmosphere {
      position: absolute;
      inset: 0;
      z-index: 0;
      pointer-events: none;
      overflow: hidden;
    }

    .grid {
      position: absolute;
      inset: 0;
      opacity: 0;
      background-image: linear-gradient(to right, var(--splash-hairline) 1px, transparent 1px);
      background-size: 12.5% 100%;
      -webkit-mask-image: linear-gradient(to bottom, transparent 0%, #000 18%, #000 82%, transparent 100%);
      mask-image: linear-gradient(to bottom, transparent 0%, #000 18%, #000 82%, transparent 100%);
    }

    .aura {
      position: absolute;
      left: 50%;
      top: 43%;
      width: min(88vmin, 1040px);
      aspect-ratio: 1;
      transform: translate(-50%, -50%);
      border-radius: 50%;
      background: radial-gradient(circle, rgba(255, 255, 255, .92) 0%, rgba(255, 255, 255, .32) 42%, rgba(255, 255, 255, 0) 70%);
      filter: blur(6px);
      opacity: 0;
    }

    .ring {
      position: absolute;
      left: 50%;
      top: 43%;
      border: 1px solid rgba(17, 17, 16, .075);
      border-radius: 50%;
      transform: translate(-50%, -50%);
      opacity: 0;
      will-change: transform, opacity;
    }

    .ring--outer {
      width: min(93vmin, 1120px);
      aspect-ratio: 1;
    }

    .ring--inner {
      width: min(65vmin, 760px);
      aspect-ratio: 1;
      border-color: rgba(17, 17, 16, .06);
    }

    .ring--inner::after {
      content: "";
      position: absolute;
      inset: 9%;
      border: 1px dashed rgba(17, 17, 16, .045);
      border-radius: 50%;
    }

    .grain {
      position: absolute;
      inset: -60px;
      z-index: 5;
      pointer-events: none;
      opacity: .055;
      mix-blend-mode: multiply;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.84' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.62'/%3E%3C/svg%3E");
      background-size: 180px 180px;
      animation: grain-shift 1.1s steps(3) infinite;
    }

    @keyframes grain-shift {
      0% { transform: translate3d(0, 0, 0); }
      33% { transform: translate3d(-2%, 1%, 0); }
      66% { transform: translate3d(1%, -2%, 0); }
      100% { transform: translate3d(0, 0, 0); }
    }

    .vignette {
      position: absolute;
      inset: 0;
      z-index: 4;
      pointer-events: none;
      background: radial-gradient(ellipse 90% 80% at 50% 46%, transparent 52%, rgba(35, 28, 20, .06) 100%);
    }

    /* ---------- frame + microcopy ---------- */

    .frame {
      position: absolute;
      inset: clamp(13px, 1.6vw, 24px);
      z-index: 1;
      border: 1px solid var(--splash-hairline);
      opacity: 0;
      pointer-events: none;
    }

    .frame::before {
      content: "";
      position: absolute;
      top: -1px;
      left: -1px;
      width: clamp(22px, 4vw, 54px);
      height: 1px;
      background: var(--splash-accent);
    }

    .frame::after {
      content: "";
      position: absolute;
      top: -1px;
      left: -1px;
      width: 1px;
      height: clamp(22px, 4vw, 54px);
      background: var(--splash-accent);
    }

    .masthead {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      z-index: 3;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      padding:
        calc(var(--splash-edge-y) + env(safe-area-inset-top, 0px))
        calc(var(--splash-edge-x) + env(safe-area-inset-right, 0px))
        var(--splash-edge-y)
        calc(var(--splash-edge-x) + env(safe-area-inset-left, 0px));
      color: var(--splash-quiet);
      font-family: var(--splash-mono);
      font-size: 9px;
      font-weight: 500;
      line-height: 1;
      letter-spacing: .24em;
      text-transform: uppercase;
      opacity: 0;
      pointer-events: none;
    }

    .masthead__brand {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      color: var(--splash-ink);
    }

    .masthead__brand::before {
      content: "";
      width: 5px;
      height: 5px;
      background: var(--splash-accent);
    }

    .masthead sup {
      position: relative;
      top: -.08em;
      margin-left: 2px;
      font-size: .67em;
      letter-spacing: 0;
    }

    .masthead__meta {
      white-space: nowrap;
    }

    .masthead__slash {
      display: inline-block;
      margin: 0 .55em;
      color: var(--splash-accent);
    }

    /* ---------- logo lockup ---------- */

    .splash-main {
      position: absolute;
      inset: 0;
      z-index: 2;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: clamp(84px, 13vh, 128px) 24px clamp(148px, 21vh, 198px);
      pointer-events: none;
    }

    .lockup {
      display: flex;
      flex-direction: column;
      align-items: center;
    }

    .brand {
      position: relative;
      width: var(--splash-logo-width);
      aspect-ratio: 914 / 1060;
      will-change: transform;
    }

    .mark {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 86.1321%;
      overflow: hidden;
    }

    .mark__half {
      position: absolute;
      top: 0;
      width: 50%;
      height: 100%;
      opacity: 0;
      will-change: transform, opacity, filter;
    }

    .mark__half--left {
      left: 0;
      transform-origin: 100% 50%;
    }

    .mark__half--right {
      left: 50%;
      transform-origin: 0 50%;
    }

    .mark__half img,
    .mark__full img,
    .wordmark__letter img {
      display: block;
      width: 100%;
      height: 100%;
      user-select: none;
      -webkit-user-drag: none;
    }

    /* Protects against a hairline at the seam once the halves land. */
    .mark__full {
      position: absolute;
      inset: 0;
      z-index: 2;
      opacity: 0;
      pointer-events: none;
      will-change: opacity;
    }

    .mark__seam {
      position: absolute;
      top: -10%;
      bottom: -10%;
      left: 50%;
      z-index: 3;
      width: 1px;
      background: linear-gradient(to bottom,
        rgba(240, 90, 50, 0) 0%,
        rgba(240, 90, 50, .9) 18%,
        var(--splash-accent) 50%,
        rgba(240, 90, 50, .9) 82%,
        rgba(240, 90, 50, 0) 100%);
      transform: translateX(-50%) scaleY(0);
      transform-origin: 50% 50%;
      opacity: 0;
    }

    .wordmark {
      position: absolute;
      left: 10.5033%;
      top: 91.3208%;
      width: 76.3676%;
      height: 8.6792%;
    }

    .wordmark__letter {
      position: absolute;
      display: block;
      opacity: 0;
      transform-origin: 50% 100%;
      will-change: transform, opacity, filter;
    }

    .wordmark__letter--s { left: .1433%; top: 1.0870%; width: 9.1691%; height: 98.9130%; }
    .wordmark__letter--h { left: 23.0659%; top: 3.2609%; width: 11.1748%; height: 93.4783%; }
    .wordmark__letter--e { left: 47.9943%; top: 4.3478%; width: 9.0258%; height: 92.3913%; }
    .wordmark__letter--l { left: 70.2006%; top: 4.3478%; width: 6.5903%; height: 92.3913%; }
    .wordmark__letter--f { left: 91.2607%; top: 4.3478%; width: 8.7393%; height: 92.3913%; }

    .tagline {
      display: flex;
      align-items: center;
      gap: clamp(10px, 1.8vw, 18px);
      margin-top: clamp(24px, 4.2vh, 38px);
      opacity: 0;
      transform: translateY(7px);
    }

    .tagline__rule {
      width: clamp(18px, 4.5vw, 54px);
      height: 1px;
      background: linear-gradient(90deg, rgba(17,17,16,0), var(--splash-line));
      transform: scaleX(0);
    }

    .tagline__rule--end {
      background: linear-gradient(90deg, var(--splash-line), rgba(17,17,16,0));
    }

    .tagline__text {
      color: var(--splash-muted);
      font-family: var(--splash-mono);
      font-size: clamp(8.5px, 1.1vw, 10px);
      font-weight: 500;
      line-height: 1;
      letter-spacing: .3em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .tagline__text::after {
      content: "";
      display: inline-block;
      width: 4px;
      height: 4px;
      margin-left: .9em;
      border-radius: 50%;
      background: var(--splash-accent);
      vertical-align: 1px;
    }

    /* ---------- loading ---------- */

    .footer {
      position: absolute;
      left: 50%;
      bottom: calc(clamp(24px, 4.8vh, 48px) + env(safe-area-inset-bottom, 0px));
      z-index: 3;
      width: min(620px, calc(100vw - (var(--splash-edge-x) * 2)));
      transform: translate(-50%, 10px);
      opacity: 0;
    }

    .footer__meta {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 13px;
      color: var(--splash-muted);
      font-family: var(--splash-mono);
      font-size: 9px;
      font-weight: 500;
      line-height: 1;
      letter-spacing: .2em;
      text-transform: uppercase;
    }

    .status {
      display: inline-flex;
      align-items: center;
      gap: 9px;
      min-height: 10px;
    }

    .status::before {
      content: "";
      width: 5px;
      height: 5px;
      flex: 0 0 auto;
      border: 1px solid var(--splash-accent);
      border-radius: 50%;
      background: transparent;
      transition: background-color .35s ease, transform .35s ease;
    }

    :host(.is-ready) .status::before {
      background: var(--splash-accent);
      transform: scale(1.08);
    }

    .pct {
      flex: 0 0 auto;
      color: var(--splash-ink);
      font-family: var(--splash-mono);
      font-size: 10px;
      letter-spacing: .08em;
      font-variant-numeric: tabular-nums;
    }

    .pct-value {
      display: inline-block;
      min-width: 2.1ch;
      text-align: right;
    }

    .pct__sign {
      margin-left: 3px;
      color: var(--splash-quiet);
      font-size: 8px;
    }

    .progress {
      position: relative;
      height: 2px;
      overflow: hidden;
      background: rgba(17, 17, 16, .12);
    }

    .progress__fill {
      position: absolute;
      inset: 0;
      background: var(--splash-accent);
      transform: scaleX(0);
      transform-origin: 0 50%;
      will-change: transform;
    }

    .progress__fill.is-completing {
      transition: transform .26s cubic-bezier(.22, 1, .36, 1);
    }

    .progress__fill::after {
      content: "";
      position: absolute;
      top: 50%;
      right: 0;
      width: 4px;
      height: 4px;
      border-radius: 50%;
      background: var(--splash-accent);
      transform: translate(50%, -50%);
      box-shadow: 0 0 0 3px rgba(240, 90, 50, .12);
    }

    .progress__ticks {
      position: absolute;
      inset: 0;
      opacity: .52;
      background-image: repeating-linear-gradient(90deg,
        transparent 0 calc(5% - 1px),
        rgba(241, 237, 228, .85) calc(5% - 1px) 5%);
      pointer-events: none;
      mix-blend-mode: soft-light;
    }

    .footer__row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      margin-top: 13px;
      color: var(--splash-quiet);
      font-family: var(--splash-mono);
      font-size: 8px;
      line-height: 1;
      letter-spacing: .18em;
      text-transform: uppercase;
    }

    .skip {
      position: relative;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 56px;
      min-height: 44px;
      margin: -15px -8px -15px 0;
      padding: 12px 8px;
      border: 0;
      border-radius: 4px;
      background: transparent;
      color: var(--splash-ink);
      font-family: var(--splash-mono);
      font-size: 9px;
      font-weight: 500;
      line-height: 1;
      letter-spacing: .18em;
      text-transform: uppercase;
      cursor: pointer;
      opacity: 0;
      pointer-events: none;
      transition: color .2s ease, opacity .25s ease;
    }

    .skip[hidden] {
      display: none;
    }

    .skip:not([hidden]) {
      opacity: 1;
      pointer-events: auto;
    }

    .skip::after {
      content: "";
      position: absolute;
      left: 8px;
      right: 8px;
      bottom: 9px;
      height: 1px;
      background: currentColor;
      opacity: .24;
    }

    .skip:hover {
      color: var(--splash-accent);
    }

    .skip:focus-visible {
      outline: 1px solid var(--splash-accent);
      outline-offset: 2px;
    }

    /* ---------- responsive ---------- */

    @media (max-width: 640px) {
      :host {
        --splash-logo-width: min(66vw, 34vh, 340px);
        --splash-edge-x: 22px;
        --splash-edge-y: 22px;
      }

      .masthead {
        font-size: 8px;
        letter-spacing: .18em;
      }

      .masthead__meta {
        max-width: 46%;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .splash-main {
        padding: 86px 18px 152px;
      }

      .tagline {
        margin-top: 24px;
      }

      .tagline__text {
        font-size: 8px;
        letter-spacing: .24em;
      }

      .footer {
        bottom: calc(25px + env(safe-area-inset-bottom, 0px));
        width: calc(100vw - 44px);
      }

      .footer__meta {
        font-size: 8px;
        letter-spacing: .16em;
      }

      .footer__row {
        font-size: 7px;
        letter-spacing: .14em;
      }

      .skip {
        font-size: 8px;
      }
    }

    @media (max-height: 640px) and (orientation: landscape) {
      :host {
        --splash-logo-width: min(46vw, 44vh, 300px);
      }

      .splash-main {
        padding-top: 64px;
        padding-bottom: 118px;
      }

      .tagline { margin-top: 18px; }
      .footer { bottom: calc(16px + env(safe-area-inset-bottom, 0px)); }
    }

    @media (prefers-reduced-motion: reduce) {
      :host { transition: none; }
      .grain { animation: none; }
      .progress,
      .pct { visibility: hidden; }
      .status::before,
      .skip,
      .progress__fill { transition: none; }
    }
  `;

  const MARKUP = `
    <div class="stage" part="stage">
      <div class="atmosphere" aria-hidden="true">
        <div class="grid"></div>
        <div class="aura"></div>
        <div class="ring ring--outer"></div>
        <div class="ring ring--inner"></div>
        <div class="grain"></div>
      </div>

      <div class="frame" aria-hidden="true"></div>

      <header class="masthead" aria-hidden="true">
        <span class="masthead__brand">SHELF<sup>®</sup></span>
        <span class="masthead__meta">Private library<span class="masthead__slash">/</span>001</span>
      </header>

      <div class="splash-main">
        <div class="lockup" part="lockup">
          <div class="brand" part="logo">
            <div class="mark">
              <div class="mark__half mark__half--left">
                <img src="data:image/png;base64,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" alt="" draggable="false">
              </div>
              <div class="mark__half mark__half--right">
                <img src="data:image/png;base64,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IzmbMvXqQAEARDKP3w4yU0Pp8wKAGPRGkjP11b2SAIhkbyQ5FRt3ABDJPUMpkACIJACIJACIJACIJACIJACIJACIJACIJACIJACIJACIJAAgkgAgkgAgkgAgkgAgkgAgkgAgkgAgkgAgkgAgkgAgkgAgkgCASAKASAKASAKASAKASAKASAKASAKASAKASAKASAKASAIAIgkAIgkAIgkAIgkAIgkAIgkAIgkAIgkAIgkAIgkAIgkAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQAIJIAIJIAIJIAIJIAIJIAIJIAIJIAIJIAIJIAIJIAIJIAIJIAgEgCgEgCgEgCgEgCgEgCgEgCgEgCgEgCgEgCgEgCgEgCACIJACIJACIJACIJACIJACIJACIJACIJACIJACIJACIJAIgkAIgkAIgkAIgkAIgkAIgkAIgkAIgkAIgkAIgkAIgkACCSACCSACCSACCSACCSACCSACCSACCSACCSACCSACCSAIBIAoBIAoBIAoBIAoBIAoBIAoBIAoBIAoBIAoBIAoBIAoBIAgAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQCIJACIJACIJACIJACIJACIJACIJACIJACIJACIJACIJAAgkgAgkgAgkgAgkgAgkgAgkgAgkgAgkgAgkgAgkgAgkgCASAKASAKASAKASAKASAKASAKASAKASAKASAKASAKASAKASPoUAIBIAoBIAoBIAoBIAoBIAoBIAoBIAoBIAoBIAoBIAoBIAgAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQCIJACIJACIJACIJACIJACIJACIJACIJACIJACIJACIJAAgkgAgkgAgkgAgkgAgkgAgkgAgkgAgkgAgkgAgkgAgkgCASAKASAKASAKASAKASAKASAKASAKASAKASAKASAKASAKASAIAIgkAIgkAIgkAIgkAIgkAIgkAIgkAIgkAIgkAIgkAIgkAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQAiCQAIJIAIJIAIJIAIJIAIJIAIJIAIJIAIJIAIJIAIJIAIJIAgEgCgEgCgEgCgEgCgEgCgEgCgEgCgEgCgEgCgEgCgEgCACIJACIJACIJACIJACIJACIJACIJACIJACIJACIJACIJACIJAIgk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" alt="" draggable="false">
              </div>
              <div class="mark__full">
                <img src="data:image/png;base64,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" alt="" draggable="false">
              </div>
              <span class="mark__seam" aria-hidden="true"></span>
            </div>

            <div class="wordmark" role="img" aria-label="SHELF">
              <span class="wordmark__letter wordmark__letter--s"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABbCAYAAADDeIOGAAALkklEQVR42s1c+XcT1xX+RjNabVnesB2DMTWmKYSQtKFJ2tMl/aH/dJs2zelJk5YucYEkQMAYjB0beZW1SzP9Yb57uNWRZc2bp0XnzJGE0Zu537v78hyM78tRFwAEAPxB3GRUrwQAF0ASgMfPLv89of6eUMS3+S6fW7yafA+iPoQ3QgAyAAoAlgHMA5jl9wkAWQWMbFIbQANADcAZgFMABwD2APwAoEggxpIDHO5khgTmASyQ+GsALgNYJBA5AGm1+1Ai0CaRZwAOAewCeAHgOYAtAnICoEKO8McBAIfE5EjkFQArAK4CWOX3twBcIhekOgjv9qqR0D0A2wBeAngKYJPXNjmkdpFYDAMAF8AkgOsAPuD1DokukGCtBxJ9rKl1QANAlYA8BvBvAF8C+A7AK/6/YBQ6wCWrXwVwA8C7JPzH3PVJEm+qQBMELsv7zFC8CgCmASwBuE/xOCNQQwHA4YNNUL4/BvALEr/Mh0v1udNRAEkrrpqjjpnh318AOCLnBJ27NAh5XyTBvwXwCYCPKPd5gpPA4EyrRxAKAKYoAjXqhOYgAXC4s8sAfgrg1yT+FgHJ8n7OEPwLjxwhJlUrzv/zF2wCkCLL3VHE/4za3RuB0yViOE06G7QaNe0vuBYV3hIV3e8B/Iafs2PgbWaVpanSRzgVfeBaIn5K7fyvAKyTG0ZJvNZJYi0S5IBjgtH2LCCcofa9Q+JvUQGN0ytPp6tNPbArStG14M8vALgL4HfU9oUhKTuTzZqkT1CkPqjG5YAZOjYfA/gJFU4chRd0mCnHoscq4pBR1sHzYiI6D+AmOWDVwLMLVJRXBVDn93aH/GZo1kwdqBbXPwDwmlzQjuMJCpKLANZIvInc+5TFp/TjX1FB1RTLzjGOWGPUmDOwXicAngH4grHCA+qBihfD1V0i4StkqagPVQKwD+AJffYHdFlPyQkJEjvHWOIdctsqo8bcBaLhE8jXAB4B+A+AvxKIPQBlAC0vhtOzAuBHtADJiGzv8yG+BvA3AA/JBXtinvh/0+SCbQA7THzcBfA2uSHVBQRZv0KANwDc43WfHNaIEwyJ6VvltRgRAGH7bwH8CcCnfNB6F1+9oRIc+9y9IkFK8t6pLuufMQr8L9f/mnkCDa4xAOLzL3H3ZyOsIzvznPH6I+56qQe3tNQlopFSscUcOQVcu8h1NwD8i8TvnHePOADM8ZqMoJnb3J1nZPndCHm8JrnhGxI/ScXr8TnqXO87yvo9itZhr3t4MWLvgoFG9snWh5TFSidL9vH7KsFL0w/JkI4tavh73PmXvE/LdlbYVSyYNHRGsiTAM7DrPgn7ngRnad83+P0+OaHUD3d5MeLtlIHpE+65RLadMHRsqrQIG+Sgx5R18SX8fmsEXsyqjWme8Dojxm/IulWDtRrkgj1uxmk3LT8IAALlrgaGCnSRMcR7NG+b1AlRRaFCZ8cxfB4jAHQ6um0oQnm6tndVRafSLWfXR+AUq17oGfrvdbqS9Rj3XgTwPtm2QaW1e176GgPM3ZvI/yT98itUZibxv1iTDEGVklfTpMY3TA4IuPP7ZN8S1/EMAJhgPFGjOFW4fsO02jsMDpBgaJ7m7JLyyEz0gc7e+iqHXx1EP4AtEZCQeIYxwZLyx03D6wwvhyJQVpwwdhwgbFpgQHQtZgpcApwCgUyQCyrkhGAcAairjM06P3sWKks5hGl2h/c4oVj44wSAmMM02VaiwnwML9HpqPhOKHGoDMo6uBYyrW3u3LRKjiRiPlOmI84vqapOME4ANFStbZbKcMpC2V0CrhwVbYLicGpbHOICoNPaWdWgkDYIlc9TjFlyREKJgzXrYKM26Hfsyix1Qd5CQcNV3WSZQVgHW9Vhn3b7iFwwQwfJtdAMIdYhTz0Dm9bBZn+AjhA9su7MOanrONYh1+EsNeOIg00AJIN7QiASdJIkdWZDHNK0Diner0RxMLYOtnuEAmUZykqTT1vqEtHWoaCSIkcUi2DUAIg+kGJkjQ+cp6OUtARCUiVWJYqUUNofNQBQ5uoIb/oIZlSVF5asQ56fWwzNK1GTNIMCQMRBROGE95pG2FABS/X+DDlrggAc8wrGAQBdCClzlyQtnrMgDo5yllKK606iZIcHDYAWh5LK981x92zoBOkJzKomiGK/ucVhAKBT2GfkBgl785acJRGvOsKq0Yt+uWBYAEDFDGK3HRX72xAH6QMskwvKvMYGAKjMb5E6Ic3YIWvBY4QqjpTUNEkwTgDobFKFGtunFl+gKDgx22NTXH8bYcWpZ51wFABA1QGkuCLeXdawYqydJIfm9znCMnq9l3M0yqGpsvLcXFU6v6pygohRfZZ5gbNedUMXo31Jw0OJl3R9zMQQB3HAtngd9ao5jhoAdDRK6mmTfMzapQxTFfm9NW4igI6Gh10AX1GJSVLFi9HFImtke220i/F5takXHMrxIkUiE1EUJCTfoUO0TfGqjzMHaNndRdhDeJ27OEFAooDgkLbkRbokETMxIYGIZ3EQ6pjma0O5tL7hROyFRRpT+UrSVKXVFEbZpEfnHPP4A8Jmxztce9KgHc9X47NWBiclE7OghiFzlK1NhM2PO1E6tC4wjfsMbZsxwvDqRVkiL0LMnWHEdRPhNNiH3JljhKOq8tBNS8UWzVGBwe+rdILqvbjS62PXdQl8jQDc4nsWYaGiQZv7raWqjaPOD3AMs9MyYV7u9TzeOc0Pui53DWGv/m2EZfAlvJn3Fzt9g+As0QdvxYztsxS1gkGoLGbwlADUonCAq1h9GWE7/LsIu7lu89/SXSKwywRhXfXnmoKQ5v3X6AtENYG+miY/jBoMTSHs/HpfEX2ZwcXUOTNBCf7tFt3OM4rCniEAUyT+A76bNGTL7p9eZEI95Xq+RefjJsIOzrcRToVMqhMdelVxV/Cm8bGtev9aEXJ7omQ/5AYsR0yUNKiUd5gQqfULwDzCgeefk/g1dZxFv3I7TzCOlV/wnO/tLubRUcrOI9A3COIvuQGzEU11mZy3iXBW6MLOU3EXCx3KLm9Q35ex9fd40wyAf9AXPyIoohvcjmzuLDnoI27CbSrgpOF02EM6U+1+ABCbqcfVTFxbKWMvEIQpitUTxuV7qvVN1/eWCP46wuHLFeockxzhEQF4RA7w+9m1Bn+4qWZrJg0jxQT1ySqJuIqwpf0xQZCafpJcNo+wU/QG303L6ZID2GMcsdVvhcjjD4/VD48slK8EiBVywqrq72mpUndWnfmRN6wgSxT5FOH8wVOld/qSW3EcXqszeRZVM3OcgYqMSk40lTJ01MlR+hQZGDZqFRGOy2xwE+tRm6Xb3KEthFNXV/jwKcDKSQ5JYGBJlBNumgxG7kSJR9wu3wOy5CxldFxfEjB9D+DvAP5MPVaKkj9wz5kGmaIeWBzR+R/9yH2VFuYLAJ9R/o+juuCdANSpUDKqHT43ZiBIoXUX4dzxZwzHjQ5Tc3uUrgLK7vJFmdUR1BEeAfgcwB+p+HZNM1Fuj3BS2s+mCUB2xEdjVGipnnDnP0c4HC1H48AmAE2VUUmpfpyMhQKmaSeqZIu/Qjgb/E9q/BoG1CjZUmPrDYrDtCpgDlPeNxlXfArgD1R4Bzb6hd0+cmsynCgt69KjmxqQcvTVaOwTdTzelwhPgdikzzKUZulAxfX7lMGyivb02X7tLqfA4JwTHoKOMwGbqsHylHL9kET/he8PmHesWEi9R06Ly46UmGnZoc99lb6CnNw2QbOp3VutM3yVLGnQ2khbS4l2vMj1n1Hmn6n225bt0RnHIFNboI8wz1B2mUHPkqrJ5zvO8EqobG1DES2pqyIBfqXmEY9U719zUINTceV3ihywzohP8oczKpUmusJXbF5RxO+T8JeU7wP+HeM6OdopGq+pS85oqqbVSU2pjrOB22R76REqc4cPuc5BzHnkoQMgvT6yq3LSkxx4kuwCQEOJgYBQUU0M/jAB+B/zTbe5iff4gAAAAABJRU5ErkJggg==" alt="" draggable="false"></span>
              <span class="wordmark__letter wordmark__letter--h"><img src="data:image/png;base64,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" alt="" draggable="false"></span>
              <span class="wordmark__letter wordmark__letter--e"><img src="data:image/png;base64,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" alt="" draggable="false"></span>
              <span class="wordmark__letter wordmark__letter--l"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAC4AAABVCAYAAAA2XNY1AAAFP0lEQVR42tWbT3PiRhDFn/4gMAYkvLtJVXJJKsllK8d8gHztfIjktHvMIYds/m1sgQFjQFIO+8bplcFmWlLDThWFdynB4/Gbnp6eVoBmIwbQBzAGcAlgACDka9UT1wV8lABWAG4AzPjvoz+4yegDeAHgawBfAngFIOFrxQHBUvgWwDsAbwDcWgofAfgKwI8AfgDwHYALvlY+43hIsT8D2AD4ldeUFsIHdPwbAN/S+d4TwoPa3zmAlL9S4Mtok5EAmAD4DEAmMAGA6JlrCzq95PNz8+KjETYU3gMwpPi+57ULAH8B+APA/MCc6FT4iD/3wPPaNaPJv4wslaXwhMLHNUyOGfcMgTenEn7J58jz2g0RkcKrridnSKZHfESK95CO31k5HlLwhI5r3me9x/HOhUcUnTUQLlFZa5zzHQERSym8CSoLxvGthXDneMrHSPE+JV1e8AvsrBzvCcd9UXGiV3S70E4ya1QKJldzTTRpC5VMgcqOYXBG4eUpHQ893N4wksyJi6nwnpiYfY/3qYTw3BqVkEv8mJsGH773CTdz3OUnI0UqW1J4LlAxiSoBXc6Yh/vmOhUXm1xMzspK+BDAlF8gVji+tUbFZYQp95kXiqW+5Ep5I+J458IDMSmn3PH4Ci8ovJHoUwjfckLe8gvAQngbqGwoWpURandA0vErz8lZEZMlo8l9E0w0UaVXEx55Ljxu47CxFC5R8RVecjLOAVzT8cJKeCAqsxndDzwcXxOTnI5XlsIHFD5Sbh7crt6U8Yir5pCY+ApfCeEbK1Qiuu3KEZFndbXa47gJKj0KTul2AN3meGYdVfp0e9pAuEPlmouPifABI4lWuEPlliWJRnxrhGeKcrJLrlYUfdfUbStUXA6+bCMMNkVFk1jNm2aEWsdTJSprrpa5prjZFipXno5X4gB2Lg6pzIWPFEcma3FybIpKKHKUvmLzcCeEm6HiRF8yR4mUC4+54xGdnlC49sgktxQui5sTOu+bWDlUTKOK2/FcUfxQefKwYn5iFscjITyr9aLAoxZ+xwVo09aqeQwqCVfLVIGKq1ot8f+RSWXtuAaVUpzzrNt024fxzHO75qqyM1G1qqyEu129BhWHybVY6s2ER2TcoeJzZLKrRZONJSoR8UgVu/qCXF+LiAIr4a77Z6w4MnFh8CSoJKKfsKfcqnWGSvzEUj9iNOkrC/gSla2F44HobvOtEZ4UFVdqSxkKE8VSX4g8fMkvYuL4UJQjEqXjq6ZHghrhF2JzrEHFNUK2mhH6otJXoOJO1tZtVK2OjSqhOD2eKgv4cz62bYfBY1HxFV6wzOZ2PNsu+D4WldgzuVqIzfGuK+GHUBmKVTNS5OALPkf8xQplp5ykoBLHjlV8oCF9SNF9ZZNBScEvaM5OGZ2kmTvR8reNn2g9TaDr1RoC+ALA98TNtS9FDdxOKPhPfLgtIY/3lNrGyn5wh95LAK8BfM4Pc5wHStHuff8G8BbA7wAW8YFy8lgpPOKEnuLD7QdNh7wZ5Df+/ROAIN6z1F+J+xaaflibw7VF3QMo4gPdP1pUuhgVcbuVh7vhnoXnHIW7TPN9XXhQQ2XSAJW2h2wXeVjUwgOopGfkeEnhuRCOTwGVspb/PHI8rE3Oc0NFJm4fMR6L8/qkhTtW2pycy5rjD+LcUn+p7MC3YvwRKiHxmCjr4F2j4vavD7eWhcLtTCRXwZk5vkCtDyCm8JhOV6Lhq3cmwt8D+Kd+wBuLn2PO7Ctghhdq7hZpObECEfmF2eGjjYPrJ3wpujjR1Ub3SOGy1PGOzs/cf/4HitjNc3uyyZ4AAAAASUVORK5CYII=" alt="" draggable="false"></span>
              <span class="wordmark__letter wordmark__letter--f"><img src="data:image/png;base64,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" alt="" draggable="false"></span>
            </div>
          </div>

          <p class="tagline">
            <span class="tagline__rule"></span>
            <span class="tagline__text">Every idea, in its place.</span>
            <span class="tagline__rule tagline__rule--end"></span>
          </p>
        </div>
      </div>

      <footer class="footer" part="footer">
        <div class="footer__meta">
          <span class="status" role="status" aria-live="polite">Preparing your shelf</span>
          <span class="pct" aria-hidden="true"><span class="pct-value">00</span><span class="pct__sign">%</span></span>
        </div>

        <div class="progress" role="progressbar" aria-label="SHELF launch progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
          <span class="progress__fill"></span>
          <span class="progress__ticks" aria-hidden="true"></span>
        </div>

        <div class="footer__row">
          <span>Collect — Curate — Keep</span>
          <button class="skip" part="skip" type="button" hidden>SKIP</button>
        </div>
      </footer>

      <div class="vignette" aria-hidden="true"></div>
    </div>
  `;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const pad = value => String(value).padStart(2, "0");

  class ShelfLaunchSplash extends HTMLElement {
    constructor() {
      super();

      const root = this.attachShadow({ mode: "open" });
      root.innerHTML = `<style>${CSS}</style>${MARKUP}`;

      this._refs = {
        grid: root.querySelector(".grid"),
        aura: root.querySelector(".aura"),
        ringOuter: root.querySelector(".ring--outer"),
        ringInner: root.querySelector(".ring--inner"),
        frame: root.querySelector(".frame"),
        masthead: root.querySelector(".masthead"),
        brand: root.querySelector(".brand"),
        markLeft: root.querySelector(".mark__half--left"),
        markRight: root.querySelector(".mark__half--right"),
        markFull: root.querySelector(".mark__full"),
        seam: root.querySelector(".mark__seam"),
        letters: Array.from(root.querySelectorAll(".wordmark__letter")),
        tagline: root.querySelector(".tagline"),
        ruleStart: root.querySelector(".tagline__rule"),
        ruleEnd: root.querySelector(".tagline__rule--end"),
        footer: root.querySelector(".footer"),
        status: root.querySelector(".status"),
        pctValue: root.querySelector(".pct-value"),
        progress: root.querySelector(".progress"),
        bar: root.querySelector(".progress__fill"),
        skip: root.querySelector(".skip")
      };

      this._onSkipClick = () => this.skip();
      this._onKeyDown = event => {
        if (event.key === "Escape" && !this._refs.skip.hidden) {
          event.preventDefault();
          this.skip();
        }
      };

      this._tick = this._tick.bind(this);
      this._tickRaf = 0;
      this._timers = new Set();
      this._animations = [];
      this._inerted = [];
      this._initialized = false;
      this._active = false;
      this._finishing = false;
      this._removed = false;
      this._cleanupDone = false;
      this._appReady = false;
      this._minElapsed = false;
      this._reduced = false;
      this._startedAt = 0;
      this._finishReason = "";
      this._previousFocus = null;
      this._previousHtmlOverflow = "";
      this._previousBodyOverflow = "";
    }

    connectedCallback() {
      if (this._initialized) return;
      this._initialized = true;

      const config = this._readConfig();
      this._config = config;
      this._reduced = window.matchMedia(REDUCED_QUERY).matches;

      const force = new URLSearchParams(window.location.search).has("splash");
      let seen = false;
      try {
        seen = sessionStorage.getItem(config.storageKey) === "1";
      } catch (error) {
        /* Private mode / disabled storage: show the splash rather than fail. */
      }

      if (!config.alwaysShow && seen && !force) {
        this._removed = true;
        this.remove();
        return;
      }

      try {
        sessionStorage.setItem(config.storageKey, "1");
      } catch (error) {
        /* Non-fatal. */
      }

      this._setSkipLabel(config.skipLabel);
      this._refs.skip.addEventListener("click", this._onSkipClick);
      document.addEventListener("keydown", this._onKeyDown, true);
      this._lockPage();
      this._lockBackground();

      this._active = true;
      this._startedAt = performance.now();

      if (this._reduced) {
        this.classList.add("is-reduced");
        this._setStaticState();
      } else {
        this._playIntro();
        this._tickRaf = requestAnimationFrame(this._tick);
      }

      const minDuration = this._reduced
        ? Math.min(600, config.minDuration)
        : config.minDuration;

      this._later(() => {
        this._minElapsed = true;
        this._maybeFinish();
      }, minDuration);

      this._later(() => this._finish("timeout"), config.maxDuration);

      this._later(() => {
        if (!this._finishing && !this._removed) {
          this._refs.skip.hidden = false;
        }
      }, this._reduced ? Math.min(config.skipAfter, 500) : config.skipAfter);

      this.dispatchEvent(new CustomEvent("shelf-splash-show", {
        bubbles: true,
        composed: true,
        detail: { force }
      }));
    }

    disconnectedCallback() {
      if (this._removed) return;
      this._removed = true;
      this._clearTimers();
      cancelAnimationFrame(this._tickRaf);
      this._cleanup();
    }

    /* Public API ------------------------------------------------------- */

    /** Call when the initial app screen/data is ready. */
    ready() {
      if (this._removed) return;
      this._appReady = true;
      this._maybeFinish();
    }

    /** Remove the splash immediately. */
    skip() {
      if (!this._active || this._finishing || this._removed) return;
      this._finish("skip");
    }

    /* Configuration ---------------------------------------------------- */

    _readConfig() {
      const number = (name, fallback) => {
        const raw = this.getAttribute(name);
        if (raw === null || raw.trim() === "") return fallback;
        const value = Number(raw);
        return Number.isFinite(value) ? value : fallback;
      };

      const minDuration = clamp(number("min-duration", 2000), 500, 8000);
      const maxDuration = clamp(number("max-duration", 5000), minDuration, 15000);
      const skipAfter = clamp(number("skip-after", 900), 0, 5000);
      const skipLabel = (this.getAttribute("skip-label") ?? "SKIP").trim() || "SKIP";

      return {
        minDuration,
        maxDuration,
        skipAfter,
        skipLabel,
        storageKey: this.getAttribute("storage-key") || "shelf.splash.seen",
        alwaysShow: this.hasAttribute("always-show")
      };
    }

    _setSkipLabel(label) {
      this._refs.skip.textContent = label;
    }

    /* Lifecycle helpers ------------------------------------------------ */

    _later(callback, delay) {
      const timer = window.setTimeout(() => {
        this._timers.delete(timer);
        callback();
      }, Math.max(0, delay));
      this._timers.add(timer);
      return timer;
    }

    _clearTimers() {
      for (const timer of this._timers) window.clearTimeout(timer);
      this._timers.clear();
    }

    _lockPage() {
      this._previousHtmlOverflow = document.documentElement.style.overflow;
      this._previousBodyOverflow = document.body ? document.body.style.overflow : "";
      document.documentElement.style.overflow = "hidden";
      if (document.body) document.body.style.overflow = "hidden";
    }

    _lockBackground() {
      this._previousFocus = document.activeElement;

      if (!this.parentElement) return;
      for (const sibling of Array.from(this.parentElement.children)) {
        if (sibling === this) continue;
        if (["SCRIPT", "STYLE", "LINK", "META", "TEMPLATE", "NOSCRIPT"].includes(sibling.tagName)) continue;
        if (!sibling.hasAttribute("inert")) {
          sibling.setAttribute("inert", "");
          this._inerted.push(sibling);
        }
      }
    }

    _cleanup() {
      if (this._cleanupDone) return;
      this._cleanupDone = true;

      this._clearTimers();
      cancelAnimationFrame(this._tickRaf);
      this._animations.forEach(animation => animation.cancel());
      this._animations = [];

      document.removeEventListener("keydown", this._onKeyDown, true);

      for (const sibling of this._inerted) {
        sibling.removeAttribute("inert");
      }
      this._inerted = [];

      document.documentElement.style.overflow = this._previousHtmlOverflow;
      if (document.body) document.body.style.overflow = this._previousBodyOverflow;

      const previous = this._previousFocus;
      if (previous && previous.isConnected && typeof previous.focus === "function") {
        try {
          previous.focus({ preventScroll: true });
        } catch (error) {
          /* Focus restoration is best-effort. */
        }
      }
    }

    _setStatus(label) {
      if (this._refs.status.textContent !== label) {
        this._refs.status.textContent = label;
      }
    }

    _setProgress(scale, percent) {
      this._refs.bar.style.transform = `scaleX(${clamp(scale, 0, 1).toFixed(4)})`;
      this._refs.pctValue.textContent = pad(clamp(percent, 0, 100));
      this._refs.progress.setAttribute("aria-valuenow", String(clamp(percent, 0, 100)));
    }

    _maybeFinish() {
      if (this._finishing || this._removed) return;
      if (this._appReady && this._minElapsed) {
        this._finish("ready");
      }
    }

    _finish(reason) {
      if (this._finishing || this._removed) return;
      this._finishing = true;
      this._finishReason = reason;
      this._clearTimers();
      cancelAnimationFrame(this._tickRaf);
      this._refs.skip.hidden = true;

      if (reason === "skip") {
        this.style.transitionDuration = this._reduced ? "0ms" : "160ms";
        this.classList.add("is-leaving");
        this._later(() => this._finalize(), this._reduced ? 0 : 170);
        return;
      }

      this.classList.add("is-ready");
      this._setStatus("Shelf ready");
      this._refs.pctValue.textContent = "100";
      this._refs.progress.setAttribute("aria-valuenow", "100");
      this._refs.bar.classList.add("is-completing");
      requestAnimationFrame(() => {
        this._refs.bar.style.transform = "scaleX(1)";
      });

      const wait = reason === "ready" ? 280 : 220;
      this._later(() => {
        this.classList.add("is-leaving");
        if (this._reduced) this.style.transitionDuration = "0ms";
        this._later(() => this._finalize(), this._reduced ? 0 : 430);
      }, this._reduced ? 0 : wait);
    }

    _finalize() {
      if (this._removed) return;
      this._removed = true;
      const duration = Math.max(0, Math.round(performance.now() - this._startedAt));
      const detail = { reason: this._finishReason, duration };
      this._cleanup();
      this.style.display = "none";
      this.remove();
      document.dispatchEvent(new CustomEvent("shelf-splash-finished", { detail }));
    }

    /* Intro ------------------------------------------------------------ */

    _animate(element, keyframes, options) {
      const animation = element.animate(keyframes, {
        fill: "both",
        easing: EASE,
        ...options
      });
      this._animations.push(animation);
      return animation;
    }

    _playIntro() {
      const r = this._refs;

      this._animate(r.grid, [
        { opacity: 0 },
        { opacity: 1 }
      ], { duration: 800, delay: 0, easing: EASE_SOFT });

      this._animate(r.aura, [
        { opacity: 0, transform: "translate(-50%, -50%) scale(.84)" },
        { opacity: 1, transform: "translate(-50%, -50%) scale(1)" }
      ], { duration: 900, delay: 0, easing: EASE });

      this._animate(r.ringOuter, [
        { opacity: 0, transform: "translate(-50%, -50%) scale(.9)" },
        { opacity: 1, transform: "translate(-50%, -50%) scale(1)" }
      ], { duration: 950, delay: 50, easing: EASE });

      this._animate(r.ringInner, [
        { opacity: 0, transform: "translate(-50%, -50%) scale(.92)" },
        { opacity: 1, transform: "translate(-50%, -50%) scale(1)" }
      ], { duration: 950, delay: 100, easing: EASE });

      this._animate(r.frame, [
        { opacity: 0 },
        { opacity: 1 }
      ], { duration: 650, delay: 90, easing: EASE_SOFT });

      this._animate(r.masthead, [
        { opacity: 0, transform: "translateY(-6px)" },
        { opacity: 1, transform: "translateY(0)" }
      ], { duration: 600, delay: 120, easing: EASE });

      this._animate(r.seam, [
        { opacity: 0, transform: "translateX(-50%) scaleY(0)" },
        { opacity: 1, offset: .22, transform: "translateX(-50%) scaleY(.35)" },
        { opacity: 1, offset: .68, transform: "translateX(-50%) scaleY(1)" },
        { opacity: 0, offset: 1, transform: "translateX(-50%) scaleY(1)" }
      ], {
        duration: 900,
        delay: 30,
        easing: "cubic-bezier(.65, 0, .35, 1)"
      });

      this._animate(r.markLeft, [
        {
          opacity: 0,
          filter: "blur(9px)",
          transform: "translate3d(-118%, 0, 0) rotate(-4deg)"
        },
        {
          opacity: 1,
          offset: .18,
          filter: "blur(4px)",
          transform: "translate3d(-62%, 0, 0) rotate(-2deg)"
        },
        {
          opacity: 1,
          offset: .84,
          filter: "blur(0)",
          transform: "translate3d(1%, 0, 0) rotate(.1deg)"
        },
        {
          opacity: 1,
          filter: "blur(0)",
          transform: "translate3d(0, 0, 0) rotate(0deg)"
        }
      ], { duration: 760, delay: 80, easing: EASE });

      this._animate(r.markRight, [
        {
          opacity: 0,
          filter: "blur(9px)",
          transform: "translate3d(118%, 0, 0) rotate(4deg)"
        },
        {
          opacity: 1,
          offset: .18,
          filter: "blur(4px)",
          transform: "translate3d(62%, 0, 0) rotate(2deg)"
        },
        {
          opacity: 1,
          offset: .84,
          filter: "blur(0)",
          transform: "translate3d(-1%, 0, 0) rotate(-.1deg)"
        },
        {
          opacity: 1,
          filter: "blur(0)",
          transform: "translate3d(0, 0, 0) rotate(0deg)"
        }
      ], { duration: 760, delay: 80, easing: EASE });

      this._animate(r.brand, [
        { transform: "scale(1)" },
        { transform: "scale(1.012)", offset: .4 },
        { transform: "scale(.998)", offset: .72 },
        { transform: "scale(1)" }
      ], { duration: 280, delay: 780, easing: "cubic-bezier(.3, 0, .2, 1)" });

      this._animate(r.markFull, [
        { opacity: 0 },
        { opacity: 1 }
      ], { duration: 180, delay: 720, easing: "linear" });

      r.letters.forEach((letter, index) => {
        this._animate(letter, [
          {
            opacity: 0,
            filter: "blur(6px)",
            transform: "translateY(62%) rotate(1.6deg)"
          },
          {
            opacity: 1,
            filter: "blur(0)",
            transform: "translateY(0) rotate(0deg)"
          }
        ], {
          duration: 500,
          delay: 740 + index * 48,
          easing: EASE
        });
      });

      this._animate(r.tagline, [
        { opacity: 0, transform: "translateY(7px)" },
        { opacity: 1, transform: "translateY(0)" }
      ], { duration: 520, delay: 860, easing: EASE });

      this._animate(r.ruleStart, [
        { transform: "scaleX(0)" },
        { transform: "scaleX(1)" }
      ], { duration: 520, delay: 900, easing: EASE });

      this._animate(r.ruleEnd, [
        { transform: "scaleX(0)" },
        { transform: "scaleX(1)" }
      ], { duration: 520, delay: 940, easing: EASE });

      this._animate(r.footer, [
        { opacity: 0, transform: "translate(-50%, 9px)" },
        { opacity: 1, transform: "translate(-50%, 0)" }
      ], { duration: 460, delay: 560, easing: EASE });
    }

    _setStaticState() {
      const r = this._refs;
      const set = (element, styles) => Object.assign(element.style, styles);

      set(r.grid, { opacity: "1" });
      set(r.aura, { opacity: "1", transform: "translate(-50%, -50%) scale(1)" });
      set(r.ringOuter, { opacity: "1", transform: "translate(-50%, -50%) scale(1)" });
      set(r.ringInner, { opacity: "1", transform: "translate(-50%, -50%) scale(1)" });
      set(r.frame, { opacity: "1" });
      set(r.masthead, { opacity: "1", transform: "translateY(0)" });
      set(r.markLeft, { opacity: "0" });
      set(r.markRight, { opacity: "0" });
      set(r.markFull, { opacity: "1" });
      set(r.seam, { opacity: "0" });
      set(r.tagline, { opacity: "1", transform: "translateY(0)" });
      set(r.ruleStart, { transform: "scaleX(1)" });
      set(r.ruleEnd, { transform: "scaleX(1)" });
      set(r.footer, { opacity: "1", transform: "translate(-50%, 0)" });

      r.letters.forEach(letter => {
        set(letter, { opacity: "1", transform: "translateY(0)", filter: "blur(0)" });
      });

      this._setStatus("Preparing your shelf");
    }

    _tick(now) {
      if (!this._active || this._finishing || this._removed || this._reduced) return;

      const elapsed = now - this._startedAt;
      const progress = clamp((elapsed - 820) / 1000, 0, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const target = this._appReady ? 1 : 0.82;
      const shown = eased * target;

      this._setProgress(shown, Math.round(shown * 100));

      if (shown >= 0.995) {
        this._setStatus("Shelf ready");
      } else if (shown >= 0.62) {
        this._setStatus("Almost there");
      } else {
        this._setStatus("Preparing your shelf");
      }

      this._tickRaf = requestAnimationFrame(this._tick);
    }
  }

  if (!customElements.get(TAG)) {
    customElements.define(TAG, ShelfLaunchSplash);
  }

  const api = {
    version: CURRENT_VERSION,
    ready() {
      document.querySelector(TAG)?.ready();
    },
    skip() {
      document.querySelector(TAG)?.skip();
    },
    get active() {
      return Boolean(document.querySelector(TAG));
    }
  };

  if (!window.ShelfSplash) {
    window.ShelfSplash = api;
  }
})();
