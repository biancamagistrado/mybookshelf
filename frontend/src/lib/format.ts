
const SHELF_LABELS: Record<string, string> = {
  read: "Read",
  "currently-reading": "Currently reading",
  "to-read": "Want to read",
  "did-not-finish": "Did not finish",
  dnf: "Did not finish",
};

export function shelfLabel(shelf: string): string {
  return (
    SHELF_LABELS[shelf] ??
    shelf.replace(/-/g, " ").replace(/^\w/, (c) => c.toUpperCase())
  );
}

export function compactNumber(value: number): string {
  if (Math.abs(value) < 10_000) return value.toLocaleString();
  if (Math.abs(value) < 1_000_000)
    return `${(value / 1_000).toFixed(1).replace(/\.0$/, "")}K`;
  return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
}

export function formatDate(iso: string | null): string | null {
  if (!iso) return null;
  const date = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function pluralize(count: number, singular: string, plural?: string) {
  return count === 1 ? singular : (plural ?? `${singular}s`);
}
