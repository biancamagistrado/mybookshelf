import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "yellow" | "dark";

const STORAGE_KEY = "bookshelf-theme";
const THEMES: Theme[] = ["yellow", "light", "dark"];
const DEFAULT_THEME: Theme = "yellow";

function readStored(): Theme | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return THEMES.includes(stored as Theme) ? (stored as Theme) : null;
  } catch {
    return null;
  }
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme | null>(readStored);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === null) {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", theme);
    }
    try {
      if (theme === null) localStorage.removeItem(STORAGE_KEY);
      else localStorage.setItem(STORAGE_KEY, theme);
    } catch {
    }
  }, [theme]);

  const setTheme = useCallback((next: Theme) => setThemeState(next), []);

  const resolved: Theme = theme ?? DEFAULT_THEME;

  const cycle = useCallback(() => {
    const next = THEMES[(THEMES.indexOf(resolved) + 1) % THEMES.length];
    setThemeState(next);
  }, [resolved]);

  const nextTheme = THEMES[(THEMES.indexOf(resolved) + 1) % THEMES.length];

  return { theme, resolved, nextTheme, setTheme, cycle, themes: THEMES };
}
