/**
 * transition.js — fades between pages.
 *
 * Browsers with cross-document view transitions animate from the `@view-transition`
 * rule in the stylesheet and this file stays out of the way. Everywhere else it
 * runs the same fade by hand: paint the outgoing page faded, then navigate.
 *
 * The navigation itself is never conditional on the animation. If anything here
 * throws, or the browser is mid-repaint, the timer still fires and the link is
 * followed — a broken transition must not become a broken link.
 */
(function () {
  const reduced = window.matchMedia
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Cross-document view transitions handle this natively.
  const nativeCrossDoc = typeof document.startViewTransition === "function"
    && CSS.supports("view-transition-name", "none")
    && matchMedia("(prefers-reduced-motion: no-preference)").matches
    && "onpagereveal" in window;

  /* Entering: fade the new page in. Skipped when the browser did it natively. */
  if (!reduced && !nativeCrossDoc) {
    document.addEventListener("DOMContentLoaded", () => {
      document.body.classList.add("is-entering");
      setTimeout(() => document.body.classList.remove("is-entering"), 400);
    });
  }

  // Coming back via the back button restores a faded-out page from the cache.
  window.addEventListener("pageshow", (e) => {
    document.body.classList.remove("is-leaving");
    if (e.persisted && !reduced && !nativeCrossDoc) {
      document.body.classList.add("is-entering");
      setTimeout(() => document.body.classList.remove("is-entering"), 400);
    }
  });

  if (reduced || nativeCrossDoc) return;

  /* Leaving: fade out, then follow the link. */
  document.addEventListener("click", (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

    const link = e.target.closest("a");
    if (!link) return;

    const href = link.getAttribute("href");
    if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) return;
    if (link.target === "_blank" || link.hasAttribute("download")) return;

    let url;
    try {
      url = new URL(link.href, window.location.href);
    } catch (err) {
      return;
    }
    if (url.origin !== window.location.origin) return;
    // Same page, different hash: that is in-page navigation, not a page change.
    if (url.pathname === window.location.pathname && url.hash) return;

    e.preventDefault();
    document.body.classList.add("is-leaving");
    setTimeout(() => { window.location.href = link.href; }, 170);
  });
})();
