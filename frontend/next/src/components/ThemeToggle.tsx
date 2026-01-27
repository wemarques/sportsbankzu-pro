import React from "react";

export function ThemeToggle() {
  const [theme, setTheme] = React.useState<string>(() => {
    if (typeof window === "undefined") return "dark";
    return localStorage.getItem("sb_theme") || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  });
  React.useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    localStorage.setItem("sb_theme", theme);
  }, [theme]);
  return (
    <button
      aria-label="Alternar tema"
      className="fixed top-3 right-3 px-3 py-2 rounded-md border border-[var(--border)] bg-[var(--card)] text-[var(--text)]"
      onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
    >
      {theme === "light" ? "🌙" : "☀️"}
    </button>
  );
}
