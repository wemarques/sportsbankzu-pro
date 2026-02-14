"use client";
import React from "react";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle({ className }: { className?: string }) {
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
      className={className ?? "p-2 rounded-lg hover:bg-secondary transition-colors"}
      onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
    >
      {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
    </button>
  );
}
