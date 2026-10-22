/**
 * Small OKLCH toolkit. Naive UI needs hex strings for its theme overrides,
 * so accent presets are stored as a single hex and every derived shade
 * (hover, pressed, tints) is computed here in a perceptual space.
 */

export interface Oklch {
  /** Lightness 0..1 */
  l: number;
  /** Chroma 0..~0.4 */
  c: number;
  /** Hue in degrees */
  h: number;
}

function clamp01(v: number) {
  return Math.min(1, Math.max(0, v));
}

function srgbToLinear(c: number) {
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function linearToSrgb(c: number) {
  return c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055;
}

export function parseHex(hex: string): [number, number, number] {
  let h = hex.trim().replace(/^#/, "");
  if (h.length === 3) h = h.split("").map((ch) => ch + ch).join("");
  const n = Number.parseInt(h.slice(0, 6), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

export function toHex(r: number, g: number, b: number): string {
  const to = (v: number) =>
    Math.round(clamp01(v) * 255)
      .toString(16)
      .padStart(2, "0");
  return `#${to(r)}${to(g)}${to(b)}`;
}

export function hexToOklch(hex: string): Oklch {
  const [sr, sg, sb] = parseHex(hex);
  const r = srgbToLinear(sr);
  const g = srgbToLinear(sg);
  const b = srgbToLinear(sb);

  const l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b;
  const m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b;
  const s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b;

  const l_ = Math.cbrt(l);
  const m_ = Math.cbrt(m);
  const s_ = Math.cbrt(s);

  const L = 0.2104542553 * l_ + 0.793617785 * m_ - 0.0040720468 * s_;
  const A = 1.9779984951 * l_ - 2.428592205 * m_ + 0.4505937099 * s_;
  const B = 0.0259040371 * l_ + 0.782771766 * m_ - 0.808675766 * s_;

  const c = Math.hypot(A, B);
  let h = (Math.atan2(B, A) * 180) / Math.PI;
  if (h < 0) h += 360;
  return { l: L, c, h };
}

export function oklchToHex({ l, c, h }: Oklch): string {
  const rad = (h * Math.PI) / 180;
  const A = c * Math.cos(rad);
  const B = c * Math.sin(rad);

  const l_ = l + 0.3963377774 * A + 0.2158037573 * B;
  const m_ = l - 0.1055613458 * A - 0.0638541728 * B;
  const s_ = l - 0.0894841775 * A - 1.291485548 * B;

  const ll = l_ ** 3;
  const mm = m_ ** 3;
  const ss = s_ ** 3;

  const r = +4.0767416621 * ll - 3.3077115913 * mm + 0.2309699292 * ss;
  const g = -1.2684380046 * ll + 2.6097574011 * mm - 0.3413193965 * ss;
  const b = -0.0041960863 * ll - 0.7034186147 * mm + 1.707614701 * ss;

  return toHex(linearToSrgb(r), linearToSrgb(g), linearToSrgb(b));
}

/** Shift lightness (and optionally scale chroma) of a hex color in OKLCH. */
export function shade(hex: string, deltaL: number, chromaScale = 1): string {
  const { l, c, h } = hexToOklch(hex);
  return oklchToHex({ l: clamp01(l + deltaL), c: c * chromaScale, h });
}

/** `rgba()` string for a hex color at the given alpha. */
export function alpha(hex: string, a: number): string {
  const [r, g, b] = parseHex(hex);
  return `rgba(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)}, ${a})`;
}

/** Derived interaction states for an accent, tuned per theme. */
export function accentStates(hex: string, dark: boolean) {
  return {
    base: hex,
    hover: shade(hex, dark ? 0.07 : 0.05),
    pressed: shade(hex, dark ? -0.04 : -0.06),
    suppl: shade(hex, dark ? 0.1 : 0.08, 0.9),
  };
}
