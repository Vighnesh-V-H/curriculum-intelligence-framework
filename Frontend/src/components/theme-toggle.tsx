"use client";

import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  return (
    <Button
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      className="theme-toggle"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      size="icon"
      variant="ghost"
    >
      {isDark ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
      <span className="sr-only">{isDark ? "Light theme" : "Dark theme"}</span>
    </Button>
  );
}
