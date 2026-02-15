"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "./theme-provider";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      aria-label="Alternar tema"
      className="fixed top-3 right-3 z-10 px-3 py-2 rounded-md border border-border bg-card text-card-foreground hover:bg-accent transition-colors"
      onClick={toggleTheme}
    >
      {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
    </button>
  );
}
