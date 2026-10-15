"use client";

import { useEffect, useState } from "react";

/** Light/dark switch. The theme is applied before first paint by the script in app/layout.tsx. */
export function ThemeToggle() {
  const [dark, setDark] = useState<boolean | null>(null);

  useEffect(() => {
    setDark(document.documentElement.dataset.theme === "dark");
  }, []);

  function toggle() {
    const next = !dark;
    document.documentElement.dataset.theme = next ? "dark" : "light";
    localStorage.setItem("theme", next ? "dark" : "light");
    setDark(next);
  }

  return (
    <button
      type="button" role="switch" aria-checked={dark ?? false} aria-label="Dark mode"
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      className="theme-switch" onClick={toggle}
    >
      <span aria-hidden className="icon">☀</span>
      <span aria-hidden className="track"><span className="thumb" /></span>
      <span aria-hidden className="icon">☾</span>
    </button>
  );
}
