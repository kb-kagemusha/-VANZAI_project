import { useColorTheme } from "../lib/theme";

type ThemeToggleProps = {
  placement?: "inline" | "fixed";
};

function MoonIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="m4.93 4.93 1.41 1.41" />
      <path d="m17.66 17.66 1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="m6.34 17.66-1.41 1.41" />
      <path d="m19.07 4.93-1.41 1.41" />
    </svg>
  );
}

export function ThemeToggle({ placement = "inline" }: ThemeToggleProps) {
  const { theme, toggleTheme } = useColorTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      className={placement === "fixed" ? "theme-toggle theme-toggle--fixed" : "theme-toggle"}
      onClick={toggleTheme}
      aria-pressed={isDark}
      aria-label={isDark ? "ライトモードに切り替え" : "ダークモードに切り替え"}
    >
      {isDark ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}
