/**
 * cluster.js — one shared connection setting for the whole site.
 *
 * Both node addresses live here, in localStorage, so whatever you point the
 * explorer at is what the verification page talks to as well. Every page gets
 * the same connection panel, opened from the status chip in the nav.
 *
 * Caveat worth knowing: localStorage is per origin. Pages served from
 * http://127.0.0.1:8011 share this setting; if you open the site from a second
 * machine's address instead, that browser keeps its own copy.
 */
window.Cluster = (function () {
  const KEY_1 = "asali_pc1_endpoint";
  const KEY_2 = "asali_pc2_endpoint";
  const DEFAULT_1 = "http://192.168.52.152:8011";
  const DEFAULT_2 = "http://192.168.52.111:8012";


  function read(key, fallback) {
    try {
      return (localStorage.getItem(key) || fallback).replace(/\/+$/, "");
    } catch (e) {
      return fallback;
    }
  }

  const state = {
    pc1: read(KEY_1, DEFAULT_1),
    pc2: read(KEY_2, DEFAULT_2),
    pc1Online: null,
    pc2Online: null,
    pc1Ms: null,
    pc2Ms: null,
    partitioned: false
  };

  function get() {
    return { pc1: state.pc1, pc2: state.pc2 };
  }

  function status() {
    return {
      pc1Online: state.pc1Online,
      pc2Online: state.pc2Online,
      pc1Ms: state.pc1Ms,
      pc2Ms: state.pc2Ms,
      partitioned: state.partitioned,
      anyOnline: state.pc1Online === true || state.pc2Online === true,
      allOnline: state.pc1Online === true && state.pc2Online === true
    };
  }

  function set(pc1, pc2) {
    state.pc1 = (pc1 || DEFAULT_1).trim().replace(/\/+$/, "");
    state.pc2 = (pc2 || DEFAULT_2).trim().replace(/\/+$/, "");
    try {
      localStorage.setItem(KEY_1, state.pc1);
      localStorage.setItem(KEY_2, state.pc2);
    } catch (e) {
      /* private mode; the setting simply will not persist */
    }
    window.dispatchEvent(new CustomEvent("cluster:changed", { detail: get() }));
    return probe();
  }

  function reset() {
    return set(DEFAULT_1, DEFAULT_2);
  }

  /** DB1 and DB2 live on PC1; the registry, ministry and ledger live on PC2. */
  function urlFor(dbHint) {
    return dbHint === "db1" || dbHint === "db2" ? state.pc1 : state.pc2;
  }

  /** Routed fetch: the owning node first, then the other, then same-origin. */
  async function call(endpoint, options = {}, dbHint = "db1") {
    const primary = urlFor(dbHint);
    const secondary = primary === state.pc1 ? state.pc2 : state.pc1;

    try {
      const res = await fetch(primary + endpoint, { mode: "cors", ...options });
      if (res.ok) return await res.json();
      throw new Error("HTTP " + res.status + " from " + primary);
    } catch (err) {
      try {
        const res2 = await fetch(secondary + endpoint, { mode: "cors", ...options });
        if (res2.ok) return await res2.json();
      } catch (e2) {
        try {
          const res3 = await fetch(endpoint, { ...options });
          if (res3.ok) return await res3.json();
        } catch (e3) {
          throw new Error("No node answered: " + err.message);
        }
      }
      throw err;
    }
  }

  async function probeOne(url) {
    const t0 = performance.now();
    try {
      const res = await fetch(url + "/health", { method: "GET", mode: "cors" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      let body = {};
      try {
        body = await res.json();
      } catch (e) {
        /* health may answer without a body */
      }
      return { online: true, ms: Math.round(performance.now() - t0), partitioned: !!body.simulated_partition };
    } catch (e) {
      return { online: false, ms: null, partitioned: false };
    }
  }

  async function probe() {
    const [a, b] = await Promise.all([probeOne(state.pc1), probeOne(state.pc2)]);
    state.pc1Online = a.online;
    state.pc1Ms = a.ms;
    state.pc2Online = b.online && !b.partitioned;
    state.pc2Ms = b.ms;
    state.partitioned = b.partitioned;

    renderChip();
    window.dispatchEvent(new CustomEvent("cluster:status", { detail: status() }));
    return status();
  }

  /* ----------------------------------------------------------------------
     Nav status chip + connection panel
     ---------------------------------------------------------------------- */
  function renderChip() {
    const chip = document.getElementById("navClusterBadge");
    if (!chip) return;

    const s = status();
    let cls = "badge";
    let dot = '<span class="dot"></span>';
    let label = "Not connected";

    if (s.allOnline) {
      cls = "badge badge-green";
      dot = '<span class="dot dot-green"></span>';
      label = "Both nodes online";
    } else if (state.partitioned) {
      cls = "badge badge-red";
      dot = '<span class="dot dot-red"></span>';
      label = "PC2 partitioned";
    } else if (s.anyOnline) {
      cls = "badge badge-amber";
      dot = '<span class="dot dot-amber"></span>';
      label = state.pc1Online ? "PC1 only" : "PC2 only";
    }

    chip.className = cls;
    chip.innerHTML = dot + " " + label;
    chip.style.cursor = "pointer";
    chip.setAttribute("title", "Change node addresses");
  }

  function closePanel() {
    const p = document.getElementById("clusterPanel");
    if (p) p.remove();
  }

  function openPanel() {
    if (document.getElementById("clusterPanel")) return closePanel();

    const s = status();
    const line = (name, url, online, ms) =>
      '<div class="kv"><span class="kv-key">' + name + "</span>" +
      '<span class="kv-val"><span class="badge ' +
      (online === true ? "badge-green" : online === false ? "badge-red" : "") + '">' +
      (online === true ? "online" + (ms != null ? ", " + ms + " ms" : "") : online === false ? "no answer" : "checking") +
      "</span></span></div>";

    const panel = document.createElement("div");
    panel.id = "clusterPanel";
    panel.className = "modal";
    panel.innerHTML =
      '<div class="modal-panel" style="max-width:520px;">' +
        '<div class="card-head">' +
          "<div><p class=\"eyebrow eyebrow-lime\">Connection</p>" +
          '<h3 class="display display-sm" style="margin-top:6px;">Where the data comes from</h3></div>' +
          '<button class="icon-btn" data-close aria-label="Close">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>' +
          "</button>" +
        "</div>" +
        '<p class="small muted" style="margin-bottom:16px;">' +
          "These two addresses are used by every page. Point them at other machines on the " +
          "network and the verification page will query those instead." +
        "</p>" +
        '<label class="eyebrow" for="clusterPc1" style="display:block; margin-bottom:8px;">Node PC1 — retail and distribution</label>' +
        '<input id="clusterPc1" class="field field-sm" spellcheck="false" value="' + state.pc1 + '">' +
        '<label class="eyebrow" for="clusterPc2" style="display:block; margin:14px 0 8px;">Node PC2 — registry, grievances and ledger</label>' +
        '<input id="clusterPc2" class="field field-sm" spellcheck="false" value="' + state.pc2 + '">' +
        '<div class="card card-inset card-pad-sm" style="margin-top:16px;">' +
          line("Node PC1", state.pc1, s.pc1Online, s.pc1Ms) +
          line("Node PC2", state.pc2, s.pc2Online, s.pc2Ms) +
        "</div>" +
        '<p class="xsmall faint" style="margin-top:12px;">' +
          "Saved in this browser only. Opening the site from a different machine's address gives that browser its own setting." +
        "</p>" +
        '<div class="row-wrap gap-2" style="margin-top:20px; justify-content:flex-end;">' +
          '<button class="btn btn-ghost btn-sm" data-reset>Reset to defaults</button>' +
          '<button class="btn btn-outline btn-sm" data-close>Cancel</button>' +
          '<button class="btn btn-primary btn-sm" data-save>Save and reconnect</button>' +
        "</div>" +
      "</div>";

    panel.addEventListener("click", (e) => {
      if (e.target === panel || e.target.closest("[data-close]")) return closePanel();

      if (e.target.closest("[data-save]")) {
        const a = document.getElementById("clusterPc1").value;
        const b = document.getElementById("clusterPc2").value;
        closePanel();
        set(a, b);
      }
      if (e.target.closest("[data-reset]")) {
        closePanel();
        reset();
      }
    });

    document.body.appendChild(panel);
  }

  document.addEventListener("DOMContentLoaded", () => {
    const chip = document.getElementById("navClusterBadge");
    if (chip) chip.addEventListener("click", openPanel);
    renderChip();
    probe();
  });

  return { get, set, reset, probe, status, call, urlFor, openPanel };
})();
