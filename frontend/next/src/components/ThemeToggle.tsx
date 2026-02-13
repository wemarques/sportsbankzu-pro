"use client";

import { useState, useEffect } from "react";

export function ThemeToggle() {
  const [theme, setTheme] = useState<string>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    const stored = localStorage.getItem("sb_theme");
    const prefers = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    setTheme(stored || prefers);
  }, [mounted]);

  useEffect(() => {
    if (!mounted) return;
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    localStorage.setItem("sb_theme", theme);
  }, [theme, mounted]);

  if (!mounted) {
    return null;
  }

  return (
    <button
      aria-label="Alternar tema"
      className="fixed top-3 right-3 z-10 px-3 py-2 rounded-md border border-[var(--border)] bg-[var(--card)] text-[var(--text)]"
      onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
    >
      {theme === "light" ? "🌙" : "☀️"}
    </button>
  );
}
