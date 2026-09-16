
import type { Book } from "../types";

const SPINE_COLORS = [
  "#6b2b2b", // oxblood
  "#7a3b1f", // rust
  "#2f4f3e", // forest
  "#23395b", // navy
  "#4a3457", // plum
  "#5c4326", // leather
  "#1f4e4a", // teal
  "#6d2f4a", // berry
  "#3d4a2a", // olive
  "#43354d", // aubergine
  "#7a5230", // camel
  "#2c3e50", // slate
] as const;

function hashString(value: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return Math.abs(hash);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export interface SpineStyle {
  width: number;
  heightPct: number;
  color: string;
}

export const SPINE_GAP = 0;

const MIN_HEIGHT_PCT = 72;
const MAX_HEIGHT_PCT = 100;

export function spineStyle(book: Book): SpineStyle {
  const seed = hashString(`${book.title}|${book.author}`);
  const pages = book.number_of_pages ?? 0;

  const width = pages
    ? clamp(Math.round(pages / 11), 22, 54)
    : 24 + (seed % 10);

  const heightFromPages = pages ? pages / 22 : 0;
  const heightPct = clamp(
    MIN_HEIGHT_PCT + heightFromPages + (seed % 12),
    MIN_HEIGHT_PCT,
    MAX_HEIGHT_PCT,
  );

  return {
    width,
    heightPct,
    color: SPINE_COLORS[seed % SPINE_COLORS.length],
  };
}
