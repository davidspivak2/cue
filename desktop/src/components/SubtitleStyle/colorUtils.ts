const HEX_RE = /^#[0-9A-Fa-f]{6}$/;

export function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  if (!HEX_RE.test(hex)) return null;
  return {
    r: Number.parseInt(hex.slice(1, 3), 16),
    g: Number.parseInt(hex.slice(3, 5), 16),
    b: Number.parseInt(hex.slice(5, 7), 16)
  };
}

export function rgbToHex(r: number, g: number, b: number): string {
  const clamp = (n: number) => Math.round(Math.max(0, Math.min(255, n)));
  return `#${[r, g, b].map((c) => clamp(c).toString(16).padStart(2, "0")).join("")}`;
}

export function hexToHsv(hex: string): { h: number; s: number; v: number } | null {
  const rgb = hexToRgb(hex);
  if (!rgb) return null;
  const r = rgb.r / 255;
  const g = rgb.g / 255;
  const b = rgb.b / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const d = max - min;
  let h = 0;
  const s = max === 0 ? 0 : d / max;
  const v = max;
  if (d !== 0) {
    switch (max) {
      case r:
        h = (g - b) / d + (g < b ? 6 : 0);
        break;
      case g:
        h = (b - r) / d + 2;
        break;
      default:
        h = (r - g) / d + 4;
    }
    h /= 6;
  }
  return { h: h * 360, s, v };
}

export function hsvToHex(h: number, s: number, v: number): string {
  const hi = Math.floor(((h % 360) + 360) % 360 / 60) % 6;
  const f = ((h % 360) + 360) % 360 / 60 - Math.floor(((h % 360) + 360) % 360 / 60);
  const p = v * (1 - s);
  const q = v * (1 - f * s);
  const t = v * (1 - (1 - f) * s);
  let r = 0;
  let g = 0;
  let b = 0;
  switch (hi) {
    case 0:
      r = v; g = t; b = p;
      break;
    case 1:
      r = q; g = v; b = p;
      break;
    case 2:
      r = p; g = v; b = t;
      break;
    case 3:
      r = p; g = q; b = v;
      break;
    case 4:
      r = t; g = p; b = v;
      break;
    default:
      r = v; g = p; b = q;
  }
  return rgbToHex(r * 255, g * 255, b * 255);
}

export function hexToHsl(hex: string): { h: number; s: number; l: number } | null {
  const rgb = hexToRgb(hex);
  if (!rgb) return null;
  const r = rgb.r / 255;
  const g = rgb.g / 255;
  const b = rgb.b / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r:
        h = (g - b) / d + (g < b ? 6 : 0);
        break;
      case g:
        h = (b - r) / d + 2;
        break;
      default:
        h = (r - g) / d + 4;
    }
    h /= 6;
  }
  return { h: h * 360, s: s * 100, l: l * 100 };
}

export function hslToHex(h: number, s: number, l: number): string {
  s /= 100;
  l /= 100;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    return l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
  };
  return rgbToHex(f(0) * 255, f(8) * 255, f(4) * 255);
}

export const SWATCH_SETS = {
  text: {
    full: [
      "#FFFFFF", "#F2F2F2", "#FFF1CC", "#FFD400", "#00E5FF",
      "#7CFF00", "#FFB000", "#FF4DFF", "#4D9CFF", "#FF3B30"
    ],
    paneCount: 5
  },
  outline: {
    full: ["#000000", "#111827", "#1F2937", "#0B1220", "#2B2B2B", "#FFFFFF", "#F2F2F2"],
    paneCount: 5,
    hasAuto: true
  },
  shadow: {
    full: ["#000000", "#111827", "#0B1220", "#1F2937", "#2B2B2B", "#3B1A5A"],
    paneCount: 5
  },
  highlight: {
    full: [
      "#FFD400", "#00E5FF", "#7CFF00", "#00E676", "#FFB000",
      "#FF4DFF", "#A855F7", "#FFFFFF", "#F2F2F2", "#FF3B30"
    ],
    paneCount: 5
  },
  background: {
    full: ["#000000", "#111827", "#1F2937", "#0B1220", "#052E16", "#3F0A0A", "#2B2B2B", "#FFFFFF"],
    paneCount: 5
  }
} as const;

export type ColorKind = keyof typeof SWATCH_SETS;
