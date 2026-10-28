const PATHS = {
  home: ["M3 9.5 12 3l9 6.5V20a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"],
  library: [
    "M4 19.5V4.5A1.5 1.5 0 0 1 5.5 3H9v18H5.5A1.5 1.5 0 0 1 4 19.5z",
    "M14 3h4.5A1.5 1.5 0 0 1 20 4.5v15a1.5 1.5 0 0 1-1.5 1.5H14z",
  ],
  search: ["M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z", "m21 21-4.3-4.3"],
  collections: ["m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"],
  user: [
    "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
    "M4 21a8 8 0 0 1 16 0",
  ],
  settings: [
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "M4 12h2M18 12h2M12 4v2M12 18v2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M17.7 6.3l-1.4 1.4M7.7 16.3l-1.4 1.4",
  ],
  sun: [
    "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z",
    "M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
  ],
  moon: ["M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"],
  play: ["M8 5v14l11-7z"],
  pause: ["M9 5v14M15 5v14"],
  skipPrev: ["M19 20 9 12l10-8z", "M5 20V4"],
  skipNext: ["M5 4l10 8-10 8z", "M19 4v16"],
  volume: [
    "M11 5 6 9H3v6h3l5 5z",
    "M15.5 8.5a5 5 0 0 1 0 7",
  ],
  volumeMute: ["M11 5 6 9H3v6h3l5 5z", "m16 9 4 6M20 9l-4 6"],
  headphones: [
    "M4 14v-2a8 8 0 0 1 16 0v2",
    "M4 14h2a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a1 1 0 0 1-1-1z",
    "M20 14h-2a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h1a1 1 0 0 0 1-1z",
  ],
  arrowRight: ["M5 12h14", "m13 6 6 6-6 6"],
  spark: [
    "M12 3v4M12 17v4M3 12h4M17 12h4",
    "M12 8.5 13.4 11l2.6 1-2.6 1-1.4 2.5L10.6 13 8 12l2.6-1z",
  ],
  grid: ["M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z"],
  list: ["M8 6h13M8 12h13M8 18h13", "M3 6h.01M3 12h.01M3 18h.01"],
  chevronDown: ["m6 9 6 6 6-6"],
  chevronLeft: ["m15 6-6 6 6 6"],
  chevronRight: ["m9 6 6 6-6 6"],
  warning: ["M12 3 2.5 20h19z", "M12 9v5M12 17h.01"],
  image: [
    "M4 5h16v14H4z",
    "m4 15 4.5-4.5L13 15l2.5-2.5L20 17",
    "M15.5 9.5h.01",
  ],
  close: ["M6 6l12 12M18 6 6 18"],
  refresh: ["M21 12a9 9 0 1 1-3-6.7", "M21 3v6h-6"],
  bookmark: ["M6 3h12v18l-6-4.5L6 21z"],
  check: ["m4 12 5 5L20 6"],
  plus: ["M12 5v14M5 12h14"],
  power: ["M12 4v8", "M6.3 7.3a8 8 0 1 0 11.4 0"],
  edit: ["M4 20h4L20 8l-4-4L4 16z"],
  trash: ["M4 7h16", "M10 11v6M14 11v6", "M6 7l1 13h10l1-13", "M9 7V4h6v3"],
  eye: ["M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7", "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6"],
  eyeOff: ["M3 3l18 18", "M10.6 5.1A11 11 0 0 1 12 5c6.5 0 10 7 10 7a17.4 17.4 0 0 1-3.3 4.3", "M6.3 6.3A17.6 17.6 0 0 0 2 12s3.5 7 10 7a11 11 0 0 0 5.7-1.6"],
} as const;

export type IconName = keyof typeof PATHS;

interface IconProps {
  name: IconName;
  className?: string;
}

export function Icon({ name, className = "size-5" }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {PATHS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
