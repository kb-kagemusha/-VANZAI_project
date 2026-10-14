import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export const THEME_STORAGE_KEY = "vanzai.theme";
const PREVIEW_THEME_KEY = "vanzai.preview.theme";

export type ColorTheme = "light" | "dark";

export function readStoredTheme(): ColorTheme {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "dark" || stored === "light") return stored;
    if (window.localStorage.getItem(PREVIEW_THEME_KEY) === "dark") return "dark";
  } catch {
    return "light";
  }
  return "light";
}

export function applyTheme(theme: ColorTheme) {
  if (theme === "dark") {
    document.documentElement.dataset.theme = "dark";
    return;
  }
  delete document.documentElement.dataset.theme;
}

export function applyStoredTheme() {
  applyTheme(readStoredTheme());
}

type ThemeContextValue = {
  theme: ColorTheme;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ColorTheme>(() => readStoredTheme());

  useEffect(() => {
    applyTheme(theme);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // 保存できない環境でも、表示中の切り替えは維持する
    }
  }, [theme]);

  useEffect(() => {
    function onStorage(event: StorageEvent) {
      if (event.key !== THEME_STORAGE_KEY) return;
      setTheme(event.newValue === "dark" ? "dark" : "light");
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((current) => (current === "dark" ? "light" : "dark"));
  }, []);

  const value = useMemo(() => ({ theme, toggleTheme }), [theme, toggleTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useColorTheme() {
  const value = useContext(ThemeContext);
  if (!value) {
    throw new Error("ThemeProvider の内側で使ってください");
  }
  return value;
}
