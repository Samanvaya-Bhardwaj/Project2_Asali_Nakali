/**
 * theme.js — light and dark, defaulting to whatever the system asks for.
 *
 * Three states rather than two: "system", "light" and "dark". System is the
 * default and is handled by CSS alone (`prefers-color-scheme`), so the page is
 * already correct before this file runs. This script only writes `data-theme`
 * when someone has made an explicit choice, and removes it again when they go
 * back to following the system.
 *
 * A small inline snippet in each page's <head> applies a stored choice before
 * first paint; without it, choosing light on a dark-set machine would flash
 * dark on every navigation.
 */
window.Theme = (function () {
  const KEY = "asali_theme";
  const ORDER = ["system", "light", "dark"];

  const media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function stored() {
    try {
      const v = localStorage.getItem(KEY);
      return ORDER.indexOf(v) >= 0 ? v : "system";
    } catch (e) {
      return "system";
    }
  }

  /** What is actually on screen, once "system" is resolved. */
  function effective(pref) {
    const p = pref || stored();
    if (p === "system") return media && media.matches ? "dark" : "light";
    return p;
  }

  function apply(pref) {
    const root = document.documentElement;
    if (pref === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", pref);

    // Let the browser paint form controls and scrollbars to match.
    root.style.colorScheme = effective(pref);
    render();
    window.dispatchEvent(new CustomEvent("theme:changed", {
      detail: { preference: pref, effective: effective(pref) }
    }));
  }

  function set(pref) {
    const next = ORDER.indexOf(pref) >= 0 ? pref : "system";
    try {
      if (next === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, next);
    } catch (e) {
      /* private mode; the choice lasts for this page only */
    }
    apply(next);
  }

  /** Cycles system → light → dark → system. */
  function toggle() {
    set(ORDER[(ORDER.indexOf(stored()) + 1) % ORDER.length]);
  }

  const ICONS = {
    system: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>',
    light:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    dark:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>'
  };

  const LABEL = {
    system: "Following your system",
    light: "Light",
    dark: "Dark"
  };

  function render() {
    const btn = document.getElementById("themeToggle");
    if (!btn) return;
    const pref = stored();
    btn.innerHTML = ICONS[pref];
    btn.setAttribute("title", LABEL[pref] + " — click to change");
    btn.setAttribute("aria-label", "Colour theme: " + LABEL[pref]);
  }

  // Following the system means following it as it changes, not just at load.
  if (media) {
    const onSystemChange = () => {
      if (stored() === "system") apply("system");
    };
    if (media.addEventListener) media.addEventListener("change", onSystemChange);
    else if (media.addListener) media.addListener(onSystemChange);
  }

  document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("themeToggle");
    if (btn) btn.addEventListener("click", toggle);
    apply(stored());
  });

  return { set, toggle, get: stored, effective };
})();
