/**
 * nav.js — keeps the nav in step with the section you are actually looking at.
 *
 * The active item used to be hardcoded in the HTML, so it stayed on the first
 * entry however far you scrolled. This moves it as you go.
 *
 * An IntersectionObserver does the work: each section is watched against a thin
 * band sitting just below the sticky nav, and whichever section occupies that
 * band owns the nav. A scroll listener backs it up for the top and bottom of the
 * page, where no section may be crossing the band at all.
 *
 * Pages whose nav only links elsewhere (verify, explorer) have no in-page
 * anchors, so this exits immediately and leaves their markup alone.
 */
(function () {
  const links = Array.from(document.querySelectorAll('.nav-links a[href^="#"]'));
  if (!links.length) return;

  const sections = links
    .map((link) => {
      const id = link.getAttribute("href").slice(1);
      const el = id ? document.getElementById(id) : null;
      return el ? { link, el } : null;
    })
    .filter(Boolean);

  if (!sections.length) return;

  const nav = document.querySelector(".nav");
  const subnav = document.querySelector(".subnav");
  // Both bars are sticky, so a section is only "reached" once it clears both.
  const navHeight = () =>
    (nav ? nav.offsetHeight : 66) + (subnav ? subnav.offsetHeight : 0);

  let activeLink = null;
  function setActive(link) {
    if (!link || link === activeLink) return;
    activeLink = link;
    links.forEach((l) => l.classList.toggle("is-active", l === link));
  }

  /* Geometry-based pick: the last section whose top has passed under the nav.
     Deliberately not wrapped in requestAnimationFrame — if a rAF callback is
     ever deferred, a "pending" flag would latch and swallow every later scroll. */
  function pick() {
    const line = window.scrollY + navHeight() + 32;

    let current = sections[0];
    for (const s of sections) {
      if (s.el.getBoundingClientRect().top + window.scrollY <= line) current = s;
    }

    // A short final section may never reach the line, so hand it the state once
    // the page bottoms out.
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) {
      current = sections[sections.length - 1];
    }

    setActive(current.link);
  }

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      () => pick(),
      {
        // A band just under the nav. Any section crossing it triggers a recheck,
        // and pick() decides which one actually owns the nav.
        rootMargin: "-" + (navHeight() + 32) + "px 0px -55% 0px",
        threshold: [0, 0.01]
      }
    );
    sections.forEach((s) => observer.observe(s.el));
  }

  let lastRun = 0;
  function onScroll() {
    const now = Date.now();
    if (now - lastRun < 80) return;
    lastRun = now;
    pick();
  }

  pick();
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", pick);
  window.addEventListener("hashchange", pick);
  window.addEventListener("load", pick);
})();
