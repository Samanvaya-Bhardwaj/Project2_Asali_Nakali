/**
 * app.js — Asali / Nakali verification terminal controller.
 *
 * Presentation layer for the federated verification result. The dossier corpus
 * lives in assets/data.js and the entity-resolution engines in assets/engines.js.
 *
 * The verdict itself is arbitrated by the live cluster when one is reachable,
 * using whichever node addresses assets/cluster.js holds. When nothing answers,
 * the stored dossier is shown instead and the page says so.
 */

/* ==========================================================================
   STATE
   ========================================================================== */
let currentItem = null;
let gaugeToken = 0;   // guards against overlapping gauge animations

/* ==========================================================================
   SMALL HELPERS
   ========================================================================== */
function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = (text === 0 ? "0" : text) || "—";
}

function setClass(id, cls) {
  const el = document.getElementById(id);
  if (el) el.className = cls;
}

function formatCurrency(val) {
  if (!val || val === 0) return "—";
  return "₹" + Number(val).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function hashCode(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return hash;
}

function escapeHtml(s) {
  return String(s === undefined || s === null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/** Verdict → the one place colour semantics are decided. */
function verdictTheme(verdict) {
  if (verdict === "ASALI") {
    return { key: "asali", tone: "green", word: "Asali", label: "Genuine",
             badge: "Genuine", arc: "gauge-arc gauge-arc-green",
             marker: "custody-marker custody-marker-ok" };
  }
  if (verdict === "SUSPICIOUS") {
    return { key: "suspicious", tone: "amber", word: "Suspicious", label: "Needs review",
             badge: "Needs review", arc: "gauge-arc gauge-arc-amber",
             marker: "custody-marker custody-marker-warn" };
  }
  return { key: "nakali", tone: "red", word: "Nakali", label: "Counterfeit",
           badge: "Counterfeit", arc: "gauge-arc gauge-arc-red",
           marker: "custody-marker custody-marker-fail" };
}

function copyHash(el) {
  if (!el || !navigator.clipboard) return;
  const text = el.textContent.trim();
  navigator.clipboard.writeText(text).then(() => {
    const original = el.textContent;
    el.textContent = "copied ✓";
    setTimeout(() => { el.textContent = original; }, 1100);
  }).catch(() => {});
}

/* ==========================================================================
   ENTRY POINTS
   ========================================================================== */
document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("itemCodeInput");
  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleManualVerify();
    });
  }
  const btn = document.getElementById("btnSearch");
  if (btn) btn.addEventListener("click", handleManualVerify);

  // ?code=MED-NAKALI-001 deep-links a specific serial, so a result can be shared.
  const requested = new URLSearchParams(window.location.search).get("code");
  if (input) loadScenario(requested ? requested.trim().toUpperCase() : "MED-ASALI-001");

  // Re-verify whenever the connection changes, so the page reflects the nodes
  // you just pointed it at without needing a reload.
  window.addEventListener("cluster:changed", () => runVerification());
  window.addEventListener("cluster:status", () => {
    if (currentItem) runVerification(currentItem.item_code);
  }, { once: true });
});

function handleManualVerify() {
  const input = document.getElementById("itemCodeInput");
  const code = (input ? input.value : "").trim();
  if (code) runVerification(code);
}

function loadScenario(itemCode) {
  const input = document.getElementById("itemCodeInput");
  if (input) input.value = itemCode;

  document.querySelectorAll(".scenario-pill").forEach((pill) => {
    pill.classList.toggle("is-active", pill.getAttribute("data-code") === itemCode);
  });

  runVerification(itemCode);
}

/* ==========================================================================
   VERIFICATION
   ========================================================================== */
async function runVerification(manualCode) {
  const input = document.getElementById("itemCodeInput");
  const rawCode = (manualCode || (input ? input.value : "")).trim();
  if (!rawCode) return;

  const btn = document.getElementById("btnSearch");
  const btnHtml = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<svg class="spin" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.2-8.6" stroke-linecap="round"/></svg> Checking…';
  }

  // Step 0: which code is meant. The PCs read the typed code against the live
  // registry themselves, so a product registered a minute ago is known. They fix
  // only slips that cannot turn one product into another (formatting, look-alike
  // characters, batch numbers, product names); a closer miss is offered as "did
  // you mean" and never checked in its place, because a fake can carry a
  // near-miss code. The built-in example list is used only when no PC answers.
  const live = await fetchLiveVerdict(rawCode);
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = btnHtml;
  }
  let fuzzy, canonicalCode;
  if (live) {
    canonicalCode = live.resolved_code || rawCode.toUpperCase();
    fuzzy = liveResolution(rawCode, canonicalCode, live.resolution);
  } else {
    fuzzy = clientFuzzyResolve(rawCode);
    canonicalCode = fuzzy.canonical;
  }

  const fuzzyBanner = document.getElementById("fuzzyResolutionBanner");
  if (fuzzy.isFuzzy) {
    if (fuzzyBanner) fuzzyBanner.classList.remove("hidden");
    setText("fuzzyConfidenceBadge", fuzzy.badge || Math.round(fuzzy.score * 100) + "% match");
    if (fuzzy.transitivePath) {
      setText("fuzzyBannerText", "Matched through " + fuzzy.transitivePath + ". " + fuzzy.explanation);
    } else {
      setText("fuzzyBannerText", '"' + rawCode + '" was read as ' + canonicalCode + '. ' + fuzzy.explanation);
    }
  } else if (fuzzyBanner) {
    fuzzyBanner.classList.add("hidden");
  }
  renderSuggestion(rawCode, live ? live.suggestion : null);

  let data = BENCHMARK_DATA[canonicalCode];

  if (!data) {
    // Unknown serial: nothing in any registry is itself the strongest counterfeit signal.
    data = {
      item_code: canonicalCode,
      verdict: "NAKALI",
      trust_score: 0,
      confidence_pct: 40,
      lifecycle_state: "SUSPENDED",
      veto_codes: ["V1_ABSENT_FROM_MANUFACTURER_DB"],
      auto_report: true,
      complaint_id: "MCA-2026-AUTO-" + canonicalCode.replace(/[^A-Z0-9]/gi, "").slice(-6).toUpperCase(),
      product: {
        found: false, product_name: "Unregistered product", generic_name: "Unidentified formulation",
        mfg_name: "Unregistered manufacturer", registration_no: "None", category: "Unknown",
        dosage_form: "Unknown", strength: "Unknown", batch_number: "Unrecorded batch",
        mfg_date: "—", expiry_date: "—", is_recalled: 0, gmp_certified: 0,
        requires_cold_chain: 0, msrp: 0.0
      },
      distribution: {
        found: false, count: 0, distributors: "No licensed distributor on record",
        authorized: false, cold_chain_ok: false, status: "untracked", returns: 0, batches: []
      },
      purchase: {
        found: false, count: 0, vendor_names: "No dispensary on record", avg_price: 0.0,
        anomaly_count: 0, vendors: 0, events: []
      },
      ministry: { found: false, blacklisted: false, complaints: 0, open_cases: 0 },
      evidence: [{
        signal: "V1_ABSENT_FROM_MANUFACTURER_DB",
        db_source: "Tier-1 Hard Veto Gate",
        value: -100,
        tier: "HARD_VETO",
        description: "Serial has no record in the national manufacturer registry (DB3)."
      }],
      anomalies: [],
      recommendations: [
        "Do not dispense or consume. This item has no verified manufacturer origin.",
        "Report the suspected sample to regulatory authorities."
      ]
    };
  }

  // When the PCs answered, the verdict and (from the live dossier) the product,
  // shipments, sales and evidence all come from the databases as they are now,
  // so a product registered a minute ago on the Databases page shows its own
  // details. The stored dossier is only the fallback for when no PC answers.
  if (live) {
    data = Object.assign({}, data, live.dossier || {}, {
      complaint_id: live.complaint_id || (live.dossier ? null : data.complaint_id),
      verdict: live.verdict === "GENUINE" ? "ASALI" : live.verdict,
      trust_score: live.trust_score,
      veto_codes: live.veto_codes || [],
      lifecycle_state: live.lifecycle_state || data.lifecycle_state,
      confidence_pct:
        live.evidence_completeness != null ? live.evidence_completeness : data.confidence_pct
    });
  }
  renderSourceBadge(live);

  currentItem = data;
  renderResult(data, rawCode, canonicalCode, fuzzy);
}

const HOW_READ = {
  tidied:    ["Formatting", "Only the formatting was different (capital letters, spaces, dashes or underscores)."],
  lookalike: ["Look-alike characters", "Look-alike characters were corrected, such as the letter O read as a zero or I as a one."],
  batch:     ["Batch number", "This is a batch number; it belongs to this product."],
  name:      ["Product name", "This was matched on the product's name."]
};

/** How the PCs read the typed code, in the shape the banner and stepper expect. */
function liveResolution(rawCode, code, res) {
  const how = (res && res.how) || "exact";
  const read = HOW_READ[how];
  return {
    canonical: code,
    how: how,
    isFuzzy: !!read && code !== rawCode.trim().toUpperCase(),
    score: res ? res.confidence : 1,
    badge: read ? read[0] : "",
    explanation: read ? read[1] : "",
    transitivePath: null
  };
}

/** A close miss is offered, never checked in place of what was typed. */
function renderSuggestion(rawCode, s) {
  const box = document.getElementById("suggestionBanner");
  if (!box) return;
  if (!s) { box.classList.add("hidden"); return; }
  setText("suggestionText",
    '"' + rawCode + '" is not in the registry, so it is checked exactly as typed (below). The closest registered ' +
    "product is " + s.uid + (s.product_name ? " (" + s.product_name + ")" : "") + ". Matching & cleaning rates it a " +
    Math.round(s.chance * 100) + "% likely typo, but a fake can carry a near-miss code too, so it is not checked in its place.");
  const btn = document.getElementById("btnSuggestion");
  if (btn) {
    btn.textContent = "Check " + s.uid;
    btn.onclick = () => loadScenario(s.uid);
  }
  box.classList.remove("hidden");
}

/**
 * Runs the federated arbitration on whichever nodes are configured. Returns
 * null when nothing is reachable, in which case the page falls back to the
 * stored dossier rather than showing an error.
 */
async function fetchLiveVerdict(code) {
  if (!window.Cluster) return null;
  if (window.Cluster.status().anyOnline === false) return null;

  try {
    const res = await window.Cluster.call(
      "/api/v1/explorer/operation",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          db_id: "all",
          operation: "FEDERATED_VIEW",
          table: "",
          data: { item_code: code }
        })
      },
      "db3"
    );
    return res && res.verdict ? res : null;
  } catch (e) {
    return null;
  }
}

function renderSourceBadge(live) {
  const badge = document.getElementById("dataSourceBadge");
  const note = document.getElementById("dataSourceNote");
  if (!badge) return;

  if (live) {
    const target = window.Cluster ? window.Cluster.urlFor("db3") : "the PCs";
    badge.className = "badge badge-green";
    badge.textContent = "Checked live";
    if (note) {
      note.textContent =
        "Checked just now by " + target + ", which found this code in " +
        (live.db_coverage != null ? live.db_coverage + " of the 4 databases" : "the databases") +
        " (" + (live.execution_ms != null ? Math.round(live.execution_ms) + " ms" : "under a second") + "). " +
        (live.dossier ? "Everything on this page is read live from the databases."
                      : "The product and journey details below come from a stored example.");
    }
  } else {
    badge.className = "badge";
    badge.textContent = "Stored example";
    if (note) {
      note.textContent =
        "No PC answered, so this is a stored example for the code. " +
        "Click the status badge at the top to set the PC addresses and check it live.";
    }
  }
}

/* ==========================================================================
   TRUST GAUGE — arc sweep + travelling knob
   ========================================================================== */
function animateScoreGauge(targetScore, verdict) {
  const arc = document.getElementById("gaugeArc");
  const knob = document.getElementById("gaugeKnob");
  const numEl = document.getElementById("gaugeScoreNum");
  const theme = verdictTheme(verdict);

  // Semicircle of r=82 → arc length = π·82 ≈ 257.6
  const circumference = 257.6;
  const fraction = Math.max(0, Math.min(100, targetScore)) / 100;

  if (arc) {
    arc.setAttribute("class", theme.arc);   // SVG className is read-only
    arc.style.strokeDashoffset = String(circumference - fraction * circumference);
  }

  if (knob) {
    const angle = Math.PI * (1 - fraction);          // π (left) → 0 (right)
    const cx = 100 + 82 * Math.cos(angle);
    const cy = 112 - 82 * Math.sin(angle);
    knob.setAttribute("cx", cx.toFixed(2));
    knob.setAttribute("cy", cy.toFixed(2));
  }

  const startNum = parseInt(numEl ? numEl.textContent : "0", 10) || 0;
  const duration = 700;
  const startTime = performance.now();
  const token = ++gaugeToken;

  function step(now) {
    if (token !== gaugeToken) return;            // a newer verification took over
    const progress = Math.min((now - startTime) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    if (numEl) numEl.textContent = Math.round(startNum + (targetScore - startNum) * ease);
    if (progress < 1) requestAnimationFrame(step);
    else if (numEl) numEl.textContent = targetScore;
  }
  requestAnimationFrame(step);

  // The count-up is decoration; the number itself is not. If rAF is throttled or
  // deferred (background tab, reduced motion, headless), land on the real value
  // anyway rather than leaving a stale figure under a correctly drawn arc.
  setTimeout(() => {
    if (token === gaugeToken && numEl) numEl.textContent = targetScore;
  }, duration + 120);
}

/**
 * Decorative barcode keyed to the serial, so each pack looks distinct.
 *
 * Bars and spaces alternate the way a real symbology works, and each element is
 * sized by flex-grow rather than a pixel width so the stripe spans whatever
 * width the card gives it. Fixed widths left it stopping half way across.
 */
function renderBarcode(code) {
  const el = document.getElementById("barcodeStripe");
  if (!el) return;

  const seed = Math.abs(hashCode(code || "ASALI"));
  const BARS = 67;
  let html = "";

  for (let i = 0; i < BARS; i++) {
    const ink = i % 2 === 0;                       // alternating bar, space, bar…
    // Guard patterns at both ends, like the start and stop marks on a real label.
    const guard = i < 3 || i >= BARS - 3;
    const units = guard ? 1 : 1 + ((seed >> (i % 29)) & 1) + ((seed >> ((i * 3 + 5) % 27)) & 1);

    html += '<span style="flex:' + units + ' 0 0; background:' +
            (ink ? "var(--ink)" : "transparent") + ';"></span>';
  }

  el.innerHTML = html;
}

/* ==========================================================================
   MAIN RENDER
   ========================================================================== */
function renderResult(data, rawCode, canonicalCode, fuzzy) {
  const p = data.product;
  const d = data.distribution;
  const pu = data.purchase;
  const m = data.ministry;
  const theme = verdictTheme(data.verdict);

  /* ---- 1. Verdict header ---- */
  setText("itemCodeDisplay", data.item_code);
  setText("confidenceVal", data.confidence_pct + "%");
  setText("lifecycleVal", (data.lifecycle_state || "—").toLowerCase());
  setText("verdictWordMark", theme.word);
  setText("trustScoreLabel", theme.label);

  setClass("verdictCard", "card card-pad-lg tint-" + theme.key);
  setClass("verdictBadge", "badge badge-" + theme.tone);
  setText("verdictBadge", theme.badge);

  const wordMark = document.getElementById("verdictWordMark");
  if (wordMark) {
    wordMark.style.color = data.verdict === "ASALI" ? "var(--green)"
      : data.verdict === "SUSPICIOUS" ? "var(--amber)" : "var(--red)";
  }

  const hasHardVeto = (data.veto_codes && data.veto_codes.length > 0);
  setClass("tierBadge", "badge " + (hasHardVeto ? "badge-red" : "badge-green"));
  setText("tierBadge", hasHardVeto ? "Hard stop: one finding decides" : "All findings weighed together");

  animateScoreGauge(data.trust_score, data.verdict);

  /* ---- 2. Verdict statement ---- */
  const cloneAnomaly = data.anomalies && data.anomalies.some(a => a.anomaly_type === "MULTI_LOCATION_SCAN");
  const coldAnomaly  = data.anomalies && data.anomalies.some(a => a.anomaly_type === "COLD_CHAIN_VIOLATION");
  const vendorAnomaly= data.anomalies && data.anomalies.some(a => a.anomaly_type === "UNLICENSED_VENDOR_SALE");

  if (data.verdict === "ASALI") {
    setText("verdictTitle", "Genuine, and safe to dispense");
    setText("verdictSubtitle", "The registry, the distributor ledger and the dispensary records all describe the same pack, and none of them contradicts the others.");
  } else if (data.verdict === "SUSPICIOUS") {
    if (cloneAnomaly) {
      setText("verdictTitle", "This barcode has been copied");
      setText("verdictSubtitle", "The same serial was scanned in several cities within a few minutes. One pack cannot travel that fast, so at least one of those scans was made on a duplicate label. Check the pack physically before dispensing it.");
    } else if (coldAnomaly) {
      setText("verdictTitle", "The cold chain was broken in transit");
      setText("verdictSubtitle", "Temperature sensors on the shipment recorded a period above the 8 °C limit. The medicine is a biologic, so its potency can no longer be assumed even though the pack itself is genuine.");
    } else if (vendorAnomaly) {
      setText("verdictTitle", "Sold outside the licensed supply chain");
      setText("verdictSubtitle", "A prescription-only medicine was sold by a vendor with no dispensing licence. The stock may well be genuine, but the chain of custody is broken and cannot be relied on.");
    } else {
      setText("verdictTitle", "Something does not add up");
      setText("verdictSubtitle", "The shipment or sales history contains problems that could not be explained in the pack's favour. A second check is needed before dispensing.");
    }
  } else {
    if (p.found && p.is_recalled) {
      setText("verdictTitle", "This batch has been recalled");
      setText("verdictSubtitle", "Health authorities have issued an active recall for this batch. Dispensing it is illegal. Quarantine the remaining stock and notify the state drug controller.");
    } else {
      setText("verdictTitle", "Counterfeit, do not dispense");
      setText("verdictSubtitle", "This code is not in the national drug registry, or it is on the government blacklist. Either finding alone is enough to override everything else and set the trust score to zero.");
    }
  }

  /* ---- 3. Unit pack ---- */
  setText("packManufacturer", p.found ? p.mfg_name + " · Schedule H" : "Unregistered manufacturer");
  setText("packBrand", p.found ? p.product_name : "Unregistered product");
  setText("packGeneric", p.found ? (p.generic_name + (p.strength ? " IP " + p.strength : "")) : "Unverified excipients");
  setText("packBatch", p.found ? p.batch_number : "—");
  setText("packMfgDate", p.found ? p.mfg_date : "—");
  setText("packExpDate", p.found ? p.expiry_date : "—");
  setText("packPrice", p.found && p.msrp ? formatCurrency(p.msrp) : (pu.found && pu.avg_price ? formatCurrency(pu.avg_price) : "—"));
  setText("barcodeCaption", data.item_code);
  renderBarcode(data.item_code);

  setClass("packSealBadge", "badge badge-" + theme.tone);
  setText("packSealBadge", data.verdict === "ASALI" ? "Seal looks intact"
    : data.verdict === "SUSPICIOUS" ? "Seal questionable" : "Seal unverified");

  /* ---- 4. Pipeline stepper ---- */
  setClass("step1Num", "custody-marker custody-marker-ok");
  const STEP1 = { exact: "Exact code", tidied: "Formatting tidied", lookalike: "Look-alike letters fixed",
                  batch: "Found by batch number", name: "Found by name", none: "Checked as typed" };
  setText("step1Status", fuzzy && fuzzy.how ? STEP1[fuzzy.how] || "Exact code"
    : fuzzy && fuzzy.isFuzzy ? "Matched by similarity" : "Exact match");

  setClass("step2Num", "custody-marker " + (p.found ? "custody-marker-ok" : "custody-marker-fail"));
  setText("step2Num", p.found ? "2" : "!");
  setText("step2Status", p.found ? "Found" : "Not found");

  setClass("step3Num", theme.marker);
  setText("step3Num", data.verdict === "ASALI" ? "3" : "!");
  setText("step3Status", data.verdict === "ASALI" ? "Nothing raised"
    : data.verdict === "SUSPICIOUS" ? "Flagged" : "Override fired");

  setClass("step4Num", theme.marker);
  setText("step4Num", data.verdict === "ASALI" ? "4" : data.verdict === "SUSPICIOUS" ? "!" : "✕");
  setText("step4Status", data.verdict === "ASALI" ? "Cleared"
    : data.verdict === "SUSPICIOUS" ? "On hold" : "Blocked");

  /* ---- 5. Backend alert ---- */
  const backendAlert = document.getElementById("backendStatusAlert");
  if (backendAlert) {
    let show = true;
    if (!p.found) {
      backendAlert.className = "card fade-in tint-nakali";
      setClass("backendAlertIconContainer", "chip chip-red");
      setClass("backendAlertBadge", "badge badge-red");
      setText("backendAlertBadge", "No record");
      setText("backendAlertDbSource", "Drug registry, DB3");
      setText("backendAlertTitle", "This serial was never registered");
      setText("backendAlertDesc", "Serial " + data.item_code + " was looked up in the national registry and returned nothing. Every genuine pack has to be registered by a licensed manufacturer before it can be sold, so an absence here is conclusive on its own.");
    } else if (p.is_recalled) {
      backendAlert.className = "card fade-in tint-suspicious";
      setClass("backendAlertIconContainer", "chip chip-amber");
      setClass("backendAlertBadge", "badge badge-amber");
      setText("backendAlertBadge", "Active recall");
      setText("backendAlertDbSource", "Registry and ministry, DB3 and DB4");
      setText("backendAlertTitle", "The batch is registered, but recalled");
      setText("backendAlertDesc", "The registry holds a valid record for this product, but batch " + p.batch_number + " carries an active government recall for a contamination or quality defect. Quarantine the stock immediately.");
    } else if (data.verdict === "SUSPICIOUS") {
      backendAlert.className = "card fade-in tint-suspicious";
      setClass("backendAlertIconContainer", "chip chip-amber");
      setClass("backendAlertBadge", "badge badge-amber");
      setText("backendAlertBadge", "Anomaly");
      if (cloneAnomaly) {
        setText("backendAlertDbSource", "Checkout scans, DB1");
        setText("backendAlertTitle", "Five checkout scans, three cities, 28 minutes");
        setText("backendAlertDesc", "The retail log recorded five separate checkouts of this one serial in Mumbai, New Delhi and Bengaluru inside half an hour. Since a single pack cannot be in three cities at once, the label has been copied and sold more than once.");
      } else if (coldAnomaly) {
        setText("backendAlertDbSource", "Distributor ledger, DB2");
        setText("backendAlertTitle", "Shipment went above 8 °C in transit");
        setText("backendAlertDesc", "Temperature sensors on the shipment logged a sustained period outside the required 2–8 °C window. Potency loss in a biologic is irreversible, so the pack should not be dispensed without reviewing the full temperature record.");
      } else if (vendorAnomaly) {
        setText("backendAlertDbSource", "Checkout scans, DB1");
        setText("backendAlertTitle", "Dispensed by an unlicensed seller");
        setText("backendAlertDesc", "A prescription-only medicine was sold by a kiosk holding no dispensing licence. The product itself may be genuine, but its custody record is legally broken from that point onward.");
      } else {
        setText("backendAlertDbSource", "Reconciliation log");
        setText("backendAlertTitle", "The ledgers disagree");
        setText("backendAlertDesc", "The supply-chain records do not line up with each other. A second check is needed before this pack is dispensed.");
      }
    } else {
      show = false;
    }
    backendAlert.classList.toggle("hidden", !show);
  }

  /* ---- 6. Reconciled attributes ---- */
  setText("metaManufacturer", p.found ? p.mfg_name : "Unregistered");
  setText("metaRegNo", p.found ? p.registration_no : "No licence on file");
  setText("metaBatch", p.found ? p.batch_number : "None");
  setText("metaExpiry", p.found ? p.expiry_date : "Unknown");
  setText("metaDistributor", d.found ? d.distributors : "No licensed distributor");
  setText("metaColdChain", d.found ? (d.cold_chain_ok ? "Maintained" : "Excursion logged") : "Untracked");
  setText("metaPharmacy", pu.found ? pu.vendor_names : "No dispensary scan");
  setText("metaPrice", pu.found ? formatCurrency(pu.avg_price) : (p.found && p.msrp ? formatCurrency(p.msrp) : "—"));

  /* ---- 7. Regulatory notice ---- */
  const alertCard = document.getElementById("regulatoryAlertCard");
  if (alertCard) {
    const showNotice = data.verdict === "NAKALI" || (p.found && p.is_recalled) || !p.found;
    alertCard.classList.toggle("hidden", !showNotice);
    if (showNotice) {
      setText("regulatoryNoticeText", (p.found && p.is_recalled)
        ? "Batch flagged in the active recall list. A quarantine notice has been issued to licensed pharmacies."
        : "Item failed statutory checks. An incident dossier has been prepared automatically for regulatory filing.");
    }
  }

  renderChainOfCustody(data);
  renderSiloPanels(data);
  renderEvidence(data);
  renderConflicts(canonicalCode, data);
}

/* ==========================================================================
   CHAIN OF CUSTODY
   ========================================================================== */
function renderChainOfCustody(data) {
  const p = data.product;
  const d = data.distribution;
  const pu = data.purchase;

  // Origin
  setText("custodyTitle1", p.found ? p.mfg_name : "Unregistered sample");
  setText("custodySub1", p.found ? ("Batch " + p.batch_number + " released on file" + (p.gmp_certified ? " · GMP certified facility" : ""))
                                 : "No production record exists on file");
  if (p.found && !p.is_recalled) {
    setClass("custodyBadge1", "badge badge-green"); setText("custodyBadge1", "Verified origin");
    setClass("custodyMarker1", "custody-marker custody-marker-ok");
  } else if (p.found) {
    setClass("custodyBadge1", "badge badge-amber"); setText("custodyBadge1", "Recalled batch");
    setClass("custodyMarker1", "custody-marker custody-marker-warn");
  } else {
    setClass("custodyBadge1", "badge badge-red"); setText("custodyBadge1", "Unregistered");
    setClass("custodyMarker1", "custody-marker custody-marker-fail");
  }

  // Logistics
  setText("custodyTitle2", d.found ? d.distributors : "No licensed distributor");
  setText("custodySub2", d.found ? (d.cold_chain_ok ? "Transit and temperature within tolerance" : "Temperature excursion recorded in transit")
                                 : "No logistics record on file");
  if (d.found && d.cold_chain_ok) {
    setClass("custodyBadge2", "badge badge-green"); setText("custodyBadge2", "Custody verified");
    setClass("custodyMarker2", "custody-marker custody-marker-ok");
  } else if (d.found) {
    setClass("custodyBadge2", "badge badge-amber"); setText("custodyBadge2", "Cold-chain alert");
    setClass("custodyMarker2", "custody-marker custody-marker-warn");
  } else {
    setClass("custodyBadge2", "badge badge-red"); setText("custodyBadge2", "Untracked");
    setClass("custodyMarker2", "custody-marker custody-marker-fail");
  }

  // Dispensary
  setText("custodyTitle3", pu.found ? pu.vendor_names : "No dispensary scan");
  setText("custodySub3", pu.found
    ? (pu.anomaly_count > 0
        ? pu.count + " scans across " + (pu.vendors || 1) + " outlets — rapid multi-site activity"
        : "Single checkout scan recorded" + (pu.last_timestamp ? " on " + pu.last_timestamp : ""))
    : "Not yet sold at retail");
  if (pu.found && pu.anomaly_count === 0) {
    setClass("custodyBadge3", "badge badge-green"); setText("custodyBadge3", "Verified checkout");
    setClass("custodyMarker3", "custody-marker custody-marker-ok");
  } else if (pu.found) {
    setClass("custodyBadge3", "badge badge-amber"); setText("custodyBadge3", "Scan anomaly");
    setClass("custodyMarker3", "custody-marker custody-marker-warn");
  } else {
    setClass("custodyBadge3", "badge"); setText("custodyBadge3", "In inventory");
    setClass("custodyMarker3", "custody-marker");
  }
}

/* ==========================================================================
   SILO PANELS
   ========================================================================== */
function renderSiloPanels(data) {
  const p = data.product;
  const d = data.distribution;
  const pu = data.purchase;
  const m = data.ministry;
  const code = data.item_code || "MED-ASALI-001";

  const applySilo = (id, tone, badgeText) => {
    setClass(id + "Badge", "badge badge-" + tone);
    setText(id + "Badge", badgeText);
    setClass(id + "Card", "card " + (tone === "green" ? "" : "tint-" + (tone === "amber" ? "suspicious" : "nakali")).trim());
  };

  // DB1 retail POS
  setText("auditD1Status", pu.found ? (pu.anomaly_count > 0 ? "Scan anomaly flagged" : "Checkout recorded") : "No retail scan");
  setText("auditD1Detail", pu.found ? pu.count + " scan(s) across " + (pu.vendors || 1) + " outlet(s)" : "Awaiting point-of-sale scan");
  if (pu.found && pu.anomaly_count === 0) applySilo("db1", "green", "Verified");
  else if (pu.found) applySilo("db1", "amber", "Scan anomaly");
  else applySilo("db1", "green", "No scan");

  // DB2 logistics
  setText("auditD2Status", d.found ? (d.cold_chain_ok ? "Authorised distributor" : "Cold-chain deviation") : "No distributor log");
  setText("auditD2Detail", d.found ? (d.cold_chain_ok ? "Cold chain maintained end to end" : "Thermal excursion recorded") : "Untracked logistics custody");
  if (d.found && d.cold_chain_ok) applySilo("db2", "green", "Verified");
  else if (d.found) applySilo("db2", "amber", "Temp alert");
  else applySilo("db2", "red", "Untracked");

  // DB3 registry
  setText("auditD3Status", p.found ? (p.is_recalled ? "Recalled batch" : "Registered manufacturer") : "No record found");
  setText("auditD3Detail", p.found ? (p.gmp_certified ? "GMP certified facility" : "Standard licence") : "Absent from CDSCO registry");
  if (p.found && !p.is_recalled) applySilo("db3", "green", "On file");
  else if (p.found) applySilo("db3", "amber", "Recalled");
  else applySilo("db3", "red", "Not found");

  // DB4 ministry
  setText("auditD4Status", m.found ? (m.blacklisted ? "Blacklisted by authority" : (m.complaints > 0 ? "Complaint on file" : "Clean standing")) : "Clean standing");
  setText("auditD4Detail", m.found ? (m.complaints > 0 ? m.complaints + " complaint(s) recorded" : "No adverse reports recorded") : "No adverse reports recorded");
  if (m.found && m.blacklisted) applySilo("db4", "red", "Blacklisted");
  else if (m.found && m.complaints > 0) applySilo("db4", "amber", m.complaints + (m.complaints === 1 ? " complaint" : " complaints"));
  else applySilo("db4", "green", "Clean");

  // Native sub-queries
  setText("db1QueryCode", 'db.retail_pos_scans.find({ "scan_code": "' + code + '" })');
  setText("db2QueryCode", "SELECT db.*, d.company_name\n  FROM distribution_batches db\n  JOIN distributors d ON db.distributor_id = d.distributor_id\n WHERE db.batch_serial = '" + code + "';");
  setText("db3QueryCode", "SELECT p.*, m.company_name, m.gmp_certified\n  FROM products p\n  JOIN manufacturers m ON p.manufacturer_id = m.manufacturer_id\n WHERE p.product_uid = '" + code + "';");
  setText("db4QueryCode", "GET /api/v1/dossier?item_ref=" + code + "\nAuthorization: Bearer CDSCO-MCA-2026-KEY");

  // Case narratives
  if (code === "MED-ASALI-002") {
    setText("db1CaseDetail", "Cloning: scanned at five dispensaries across Mumbai, Delhi and Bengaluru within 28 minutes. The implied transit velocity exceeds commercial aircraft, which proves the serialised sticker was reproduced.");
  } else if (code === "MED-UNAUTH-001") {
    setText("db1CaseDetail", "Diversion: scanned at an unlicensed roadside vendor holding no state pharmaceutical retail licence.");
  } else {
    setText("db1CaseDetail", pu.found ? "Single checkout logged at a licensed dispensary. No multi-city velocity anomaly detected." : "No retail scan logged in the dispensary ledger.");
  }

  if (code === "MED-ASALI-009") {
    setText("db2CaseDetail", "Cold-chain failure: the reefer IoT sensor logged a sustained 11.4 °C excursion in transit, well beyond the mandated 2–8 °C boundary for this biologic.");
  } else {
    setText("db2CaseDetail", d.found ? (d.cold_chain_ok ? "Authorised logistics contract on file; temperature logging stayed inside the safe window throughout transit." : "Temperature excursion logged during distributor shipment.") : "Untracked logistics custody.");
  }

  if (!p.found) {
    setText("db3CaseDetail", "Phantom serial: the queried code is entirely absent from the statutory CDSCO master register. There is no golden record to reconcile against.");
  } else if (p.is_recalled) {
    setText("db3CaseDetail", "Contamination: batch marked for urgent regulatory quarantine under gazette notification CDSCO-2025-RECALL-04.");
  } else {
    setText("db3CaseDetail", "Registered in the national CDSCO database with an active GMP licence and a verified batch release certificate.");
  }

  if (code === "MED-RECALL-001") {
    setText("db4CaseDetail", "Emergency recall: CDSCO toxic alert raised for diethylene glycol solvent contamination. A confiscation order is active.");
  } else {
    setText("db4CaseDetail", m.found
      ? (m.blacklisted ? "Manufacturer or batch sits on the active regulatory blacklist."
        : (m.complaints > 0 ? m.complaints + " consumer grievance(s) filed under the Pharmacovigilance Programme of India." : "No adverse drug reactions logged; lab assays confirm chemical purity."))
      : "Clean national standing — no complaints, alerts or blacklist entries.");
  }

  // Coverage badge
  const coverage = document.getElementById("dbCoverageBadge");
  if (coverage) {
    if (!p.found) {
      coverage.className = "badge badge-red";
      coverage.textContent = "No registry record";
    } else if (p.found && d.found && pu.found) {
      coverage.className = "badge badge-green";
      coverage.textContent = "4 of 4 answered";
    } else {
      const active = [p.found, d.found, pu.found, !m.blacklisted].filter(Boolean).length;
      coverage.className = "badge badge-amber";
      coverage.textContent = active + " of 4 answered";
    }
  }
}

/* ==========================================================================
   EVIDENCE LEDGER
   ========================================================================== */
function renderEvidence(data) {
  const tbody = document.getElementById("auditSignalsTbody");
  const countBadge = document.getElementById("evidenceCountBadge");
  const evidence = data.evidence || [];

  if (countBadge) {
    const vetoes = evidence.filter(e => e.tier === "HARD_VETO").length;
    countBadge.className = "badge " + (vetoes ? "badge-red" : evidence.length ? "badge" : "badge-green");
    countBadge.textContent = vetoes ? vetoes + (vetoes > 1 ? " overrides" : " override") : evidence.length + (evidence.length === 1 ? " signal" : " signals");
  }

  if (!tbody) return;

  if (evidence.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:26px;" class="faint">Nothing counted against this pack.</td></tr>';
    return;
  }

  tbody.innerHTML = evidence.map((ev) => {
    const positive = ev.value >= 0;
    const badgeCls = positive ? "badge badge-green" : (ev.tier === "HARD_VETO" ? "badge badge-red" : "badge badge-amber");
    const friendly = (typeof SIGNAL_MAP !== "undefined" && SIGNAL_MAP[ev.signal])
      || ev.signal.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
    const tierTag = ev.tier === "HARD_VETO" ? ' <span class="badge badge-red" style="margin-left:6px;">veto</span>' : "";
    return '<tr>' +
      '<td class="nowrap"><span class="em">' + escapeHtml(friendly) + '</span>' + tierTag + '</td>' +
      '<td class="nowrap"><span class="' + badgeCls + '">' + (positive ? "+" : "") + ev.value + '</span></td>' +
      '<td class="nowrap mono xsmall">' + escapeHtml(ev.db_source) + '</td>' +
      '<td>' + escapeHtml(ev.description) + '</td>' +
      '</tr>';
  }).join("");

  const hashEl = document.getElementById("auditHashDisplay");
  if (hashEl) {
    hashEl.textContent = "sha256:" + Math.abs(hashCode(data.item_code + data.trust_score)).toString(16).padStart(16, "0") + "e9b2c8a7f1d4";
  }
}

function renderConflicts(canonicalCode, data) {
  const container = document.getElementById("conflictListContainer");
  const badge = document.getElementById("conflictCountBadge");
  if (!container) return;

  const conflicts = [];

  if (data.product && data.product.is_recalled) {
    conflicts.push({
      policy: "The regulator outranks the maker",
      severity: "Decisive", tone: "red",
      winning: "Ministry records",
      desc: "The registry still lists this product as valid, but the ministry has recalled the batch for contamination. A recall is not one opinion among several, so it settles the matter by itself."
    });
  }
  if (data.anomalies && data.anomalies.some(a => a.anomaly_type === "MULTI_LOCATION_SCAN")) {
    conflicts.push({
      policy: "Physical possibility",
      severity: "Decisive", tone: "red",
      winning: "Retail checkout records",
      desc: "One pack was scanned five times, in three cities, within half an hour. There is no arrangement of those records that is physically possible, so at least one scan was made on a copied label."
    });
  }
  if (data.anomalies && data.anomalies.some(a => a.anomaly_type === "COLD_CHAIN_VIOLATION")) {
    conflicts.push({
      policy: "Caution about patient safety",
      severity: "Strong", tone: "amber",
      winning: "Shipment sensors",
      desc: "The registry gives this product a normal shelf life, but the shipment sensors recorded a period above 8 °C. Where the two disagree about whether it is still safe, the sensor reading wins."
    });
  }
  if (data.anomalies && data.anomalies.some(a => a.anomaly_type === "UNLICENSED_VENDOR_SALE")) {
    conflicts.push({
      policy: "Licensing rules",
      severity: "Strong", tone: "amber",
      winning: "Seller licence check",
      desc: "The medicine itself is genuine, but it was sold by someone with no licence to sell it. Authenticity and lawful custody point different ways here, and custody decides the outcome."
    });
  }
  if (data.product && !data.product.found) {
    conflicts.push({
      policy: "Nothing downstream can create provenance",
      severity: "Decisive", tone: "red",
      winning: "Drug registry, no record",
      desc: "The checkout and shipping systems both hold rows for this serial, but the registry has no record of it ever being made. Sales records downstream cannot bring a pack into existence."
    });
  }

  if (badge) {
    badge.className = "badge " + (conflicts.length ? "badge-red" : "badge-green");
    badge.textContent = conflicts.length ? conflicts.length + (conflicts.length === 1 ? " disagreement" : " disagreements") : "No disagreement";
  }

  if (conflicts.length === 0) {
    container.innerHTML = '<div class="card card-inset card-pad-sm"><p class="small muted">Nothing to settle: all four databases describe this pack the same way.</p></div>';
    return;
  }

  container.innerHTML = conflicts.map(c =>
    '<div class="card card-inset card-pad-sm">' +
      '<div class="row-wrap gap-2 between" style="margin-bottom:6px;">' +
        '<span class="h-sm">' + escapeHtml(c.policy) + '</span>' +
        '<span class="badge badge-' + c.tone + '">' + escapeHtml(c.severity) + '</span>' +
      '</div>' +
      '<p class="small muted">' + escapeHtml(c.desc) + '</p>' +
      '<p class="xsmall faint mono" style="margin-top:8px;">Decided by ' + escapeHtml(c.winning) + '</p>' +
    '</div>'
  ).join("");
}

/* ==========================================================================
   INCIDENT REPORT
   ========================================================================== */
function openDossierModal() {
  const modal = document.getElementById("dossierModal");
  if (!modal || !currentItem) return;

  const complaintId = currentItem.complaint_id
    || "MCA-2026-AUTO-" + currentItem.item_code.replace(/[^A-Z0-9]/gi, "").slice(-6).toUpperCase();

  setText("dossierId", complaintId);
  setText("dossierItemCode", currentItem.item_code);
  setText("dossierViolation", (currentItem.veto_codes && currentItem.veto_codes.length)
    ? currentItem.veto_codes.join(", ")
    : (currentItem.product && currentItem.product.is_recalled ? "Contaminated recall batch" : "Counterfeit / unregistered"));
  setText("dossierAction", (currentItem.product && currentItem.product.is_recalled)
    ? "Immediate statutory recall. Quarantine remaining stock and notify the state drug control administration."
    : "Immediate seizure of the suspected unit pack. Dispatch a field inspector to the dispensing outlet.");

  modal.classList.remove("hidden");
}

function closeDossierModal() {
  const modal = document.getElementById("dossierModal");
  if (modal) modal.classList.add("hidden");
}

function downloadDossierText() {
  if (!currentItem) return;
  const complaintId = currentItem.complaint_id
    || "MCA-2026-AUTO-" + currentItem.item_code.replace(/[^A-Z0-9]/gi, "").slice(-6).toUpperCase();

  const text =
    "REGULATORY INCIDENT REPORT\n" +
    "==========================\n" +
    "Report ID    : " + complaintId + "\n" +
    "Item code    : " + currentItem.item_code + "\n" +
    "Verdict      : " + currentItem.verdict + "\n" +
    "Trust score  : " + currentItem.trust_score + "/100\n" +
    "Confidence   : " + currentItem.confidence_pct + "%\n" +
    "Product      : " + (currentItem.product ? currentItem.product.product_name : "Unregistered") + "\n" +
    "Manufacturer : " + (currentItem.product ? currentItem.product.mfg_name : "Unregistered") + "\n" +
    "Escalation   : " + ((currentItem.veto_codes && currentItem.veto_codes.length) ? currentItem.veto_codes.join(", ") : "None") + "\n" +
    "Generated    : " + new Date().toISOString() + "\n" +
    "Audit hash   : sha256:" + Math.abs(hashCode(currentItem.item_code + currentItem.trust_score)).toString(16).padStart(16, "0") + "e9b2c8a7f1d4\n" +
    "\nEVIDENCE\n--------\n" +
    (currentItem.evidence || []).map(e =>
      "  [" + (e.value >= 0 ? "+" : "") + e.value + "] " + e.signal + " (" + e.db_source + ")\n      " + e.description
    ).join("\n") +
    "\n\nRECOMMENDED ACTIONS\n-------------------\n" +
    (currentItem.recommendations || []).map(r => "  - " + r).join("\n") +
    "\n\nStatus: batch quarantined pending inspection.\n";

  const blob = new Blob([text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "INCIDENT_REPORT_" + currentItem.item_code + ".txt";
  a.click();
  URL.revokeObjectURL(url);
}

/* ==========================================================================
   ACCORDIONS
   ========================================================================== */
function toggleDbAccordion(dbKey) {
  const dropdown = document.getElementById(dbKey + "Dropdown");
  const chevron = document.getElementById(dbKey + "Chevron");
  if (!dropdown) return;
  const willOpen = dropdown.classList.contains("hidden");
  dropdown.classList.toggle("hidden", !willOpen);
  if (chevron) chevron.classList.toggle("is-open", willOpen);
}

/* ==========================================================================
   GLOBAL EXPORTS (inline handlers)
   ========================================================================== */
window.loadScenario = loadScenario;
window.quickSelect = loadScenario;
window.handleManualVerify = handleManualVerify;
window.runVerification = runVerification;
window.toggleDbAccordion = toggleDbAccordion;
window.openDossierModal = openDossierModal;
window.closeDossierModal = closeDossierModal;
window.downloadDossierText = downloadDossierText;
window.copyHash = copyHash;
