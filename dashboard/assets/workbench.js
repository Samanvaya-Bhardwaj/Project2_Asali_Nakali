/**
 * workbench.js — the integration tools shown on the explorer page.
 *
 * Three of the problems the mediator has to solve are easier to understand by
 * operating them than by reading about them, so each one gets a small sandbox:
 * entity resolution, unit conversion, and schema drift. Depends on
 * assets/data.js and assets/engines.js for the corpus and the string metrics.
 */

let resolvedTarget = "MED-ASALI-002";

function wbSetText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = (text === 0 ? "0" : text) || "—";
}

function wbEscape(s) {
  return String(s === undefined || s === null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/* --------------------------------------------------------------------------
   Entity resolution
   -------------------------------------------------------------------------- */
function testFuzzyPreset(presetCode) {
  const input = document.getElementById("fuzzyTestInput");
  if (input) input.value = presetCode;
  runFuzzyResolution();
}

function runFuzzyResolution() {
  const input = document.getElementById("fuzzyTestInput");
  const raw = (input ? input.value : "").trim();
  if (!raw) return;

  const res = clientFuzzyResolve(raw);
  resolvedTarget = res.canonical;

  wbSetText("fuzzyJwMetric", (res.score * 100).toFixed(1) + "%");
  wbSetText("fuzzyLevMetric", res.levenshtein + (res.levenshtein === 1 ? " edit" : " edits"));
  wbSetText("fuzzySoundexMetric", res.soundex);
  wbSetText("fuzzyTargetMetric", res.canonical);
  wbSetText("fuzzyExplanationText", res.explanation);

  const link = document.getElementById("btnVerifyResolved");
  if (link) {
    link.textContent = "Check " + res.canonical + " on the Check a medicine page";
    link.setAttribute("href", "verify.html?code=" + encodeURIComponent(res.canonical));
  }
}

/* --------------------------------------------------------------------------
   Units and semantics
   -------------------------------------------------------------------------- */
function testUnitPreset(presetVal) {
  const input = document.getElementById("semanticInput");
  if (input) input.value = presetVal;
  runUnitConversion();
}

function runUnitConversion() {
  const input = document.getElementById("semanticInput");
  const val = (input ? input.value : "").trim();
  const out = document.getElementById("semanticOutputBox");
  if (!out) return;

  if (!val) {
    out.textContent = "Enter a value to convert.";
    return;
  }

  const emit = (text, tone) => {
    out.innerHTML = '<span style="color:var(--' + (tone || "lime") + ');">' + wbEscape(text) + "</span>";
  };

  const fMatch = val.match(/([0-9.]+)\s*(?:°?\s*F|deg\s*F)/i);
  if (fMatch) {
    const f = parseFloat(fMatch[1]);
    const c = ((f - 32) * 5 / 9).toFixed(1);
    const breach = parseFloat(c) > 8.0;
    emit(f + " °F becomes " + c + " °C. " +
         (breach ? "That is above the 8 °C limit, so the shipment breached its cold chain."
                 : "That is inside the required 2–8 °C window."),
         breach ? "red" : "green");
    return;
  }

  const kMatch = val.match(/([0-9.]+)\s*K\b/i);
  if (kMatch) {
    const k = parseFloat(kMatch[1]);
    const c = (k - 273.15).toFixed(1);
    const breach = parseFloat(c) > 8.0;
    emit(k + " K becomes " + c + " °C. " +
         (breach ? "That is above the 8 °C limit, so the shipment breached its cold chain."
                 : "That is inside the required 2–8 °C window."),
         breach ? "red" : "green");
    return;
  }

  const usdMatch = val.match(/\$([0-9.]+)/) || val.match(/([0-9.]+)\s*USD/i);
  if (usdMatch) {
    const usd = parseFloat(usdMatch[1]);
    emit("$" + usd.toFixed(2) + " becomes ₹" + (usd * 83.0).toFixed(2) + " at the stored rate of 83.00.");
    return;
  }

  if (/^[0-9]{13}$/.test(val)) {
    emit(val + " is a computer timestamp (milliseconds since 1970). It becomes " +
         new Date(parseInt(val, 10)).toISOString() + ".");
    return;
  }

  const dateMatch = val.match(/^([0-3]?[0-9])[\/\-]([0-1]?[0-9])[\/\-](20[0-9]{2})$/);
  if (dateMatch) {
    emit(val + " is written day first, as the government gazette does. It becomes " +
         dateMatch[3] + "-" + dateMatch[2].padStart(2, "0") + "-" + dateMatch[1].padStart(2, "0") + ".");
    return;
  }

  emit("No unit recognised, so it is stored as plain text: " + val.toUpperCase() + ".");
}

/* --------------------------------------------------------------------------
   Schema drift
   -------------------------------------------------------------------------- */
function testSchemaVersion(ver) {
  const v2 = (ver === "v2");

  const badge = document.getElementById("schemaVersionBadge");
  if (badge) {
    badge.className = "badge " + (v2 ? "badge-amber" : "");
    badge.textContent = v2 ? "Version 2, GS1 digital link" : "Version 1, original format";
  }

  const v1Pill = document.getElementById("schemaV1Pill");
  const v2Pill = document.getElementById("schemaV2Pill");
  if (v1Pill) v1Pill.classList.toggle("is-active", !v2);
  if (v2Pill) v2Pill.classList.toggle("is-active", v2);

  const note = document.getElementById("schemaDriftNote");

  if (v2) {
    wbSetText("schemaPayloadDisplay", JSON.stringify({
      digital_link_uri: "https://id.gs1.org/01/08901234567890/21/MED-ASALI-001",
      price_minor_units: 23000,
      currency_iso4217: "INR",
      facility_gln: "8901234567890",
      facility_tree: { name: "Apollo Pharmacy Store #104", division: "Retail Dispensary East", state_code: "MH" }
    }, null, 2));
    wbSetText("schemaAdaptedDisplay", JSON.stringify({
      scan_code: "MED-ASALI-001",
      price_paid_inr: 230.0,
      vendor_name: "Apollo Pharmacy Store #104",
      schema_version: "v2.0"
    }, null, 2));
    if (note) {
      note.textContent = "The serial is now buried inside a GS1 URI, the price arrives in paise rather " +
        "than rupees, and the outlet is a nested tree instead of a name. The adapter pulls all three back " +
        "into the same standard row, so nothing else in the system has to change.";
    }
  } else {
    wbSetText("schemaPayloadDisplay", JSON.stringify({
      scan_code: "MED-ASALI-001",
      price_paid: 230.0,
      currency: "INR",
      vendor_name: "Apollo Pharmacy"
    }, null, 2));
    wbSetText("schemaAdaptedDisplay", JSON.stringify({
      scan_code: "MED-ASALI-001",
      price_paid_inr: 230.0,
      vendor_name: "Apollo Pharmacy",
      schema_version: "v1.0"
    }, null, 2));
    if (note) {
      note.textContent = "The original format maps across almost unchanged. Switch to version 2 to see " +
        "what happens when a database changes its format without warning.";
    }
  }
}

/* --------------------------------------------------------------------------
   Init
   -------------------------------------------------------------------------- */
document.addEventListener("DOMContentLoaded", () => {
  const fuzzyInput = document.getElementById("fuzzyTestInput");
  if (fuzzyInput) {
    fuzzyInput.addEventListener("keydown", (e) => { if (e.key === "Enter") runFuzzyResolution(); });
    runFuzzyResolution();
  }

  const semanticInput = document.getElementById("semanticInput");
  if (semanticInput) {
    semanticInput.addEventListener("keydown", (e) => { if (e.key === "Enter") runUnitConversion(); });
    runUnitConversion();
  }

  if (document.getElementById("schemaPayloadDisplay")) testSchemaVersion("v1");
});

window.testFuzzyPreset = testFuzzyPreset;
window.runFuzzyResolution = runFuzzyResolution;
window.testUnitPreset = testUnitPreset;
window.runUnitConversion = runUnitConversion;
window.testSchemaVersion = testSchemaVersion;
