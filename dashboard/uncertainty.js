/**
 * uncertainty.js: the phase 2 page.
 *
 * Talks to /api/v1/uncertainty/* on the nodes through Cluster.call, and to the
 * existing explorer operation endpoint for the insert / modify / delete tests.
 * Every write in this file goes to node PC1, so the read that follows it sees
 * the same files even when the two nodes run on different machines.
 */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (x, d = 1) => (x == null ? "—" : (x * 100).toFixed(d) + "%");
  const num = (x, d = 3) => (x == null ? "—" : Number(x).toFixed(d));

  const api = (path, opts) => Cluster.call("/api/v1/uncertainty/" + path, opts || {}, "db1");
  const post = (path, body) => api(path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {})
  });
  const explorerOp = (db_id, operation, table, data) => Cluster.call("/api/v1/explorer/operation", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ db_id, operation, table, data })
  }, "db1");

  const S = { catalog: null, samples: [], scan: null, page: 0, pageSize: 40, bench: null, tests: {} };

  const FEATURE_LABEL = {
    code: "code", custody: "custody", price: "price", date: "dates", label_brand: "label brand",
    label_strength: "label strength", label_batch: "label batch", label_expiry: "label expiry",
    label_mrp: "label MRP", mfr: "manufacturer", auth: "distributor", dest: "destination", sold_at_dest: "sold at destination", brand_mention: "brand in text",
    vendor_mention: "shop in text"
  };
  const DECISION = {
    EXACT: ["ok", "badge-green", "Registered code"],
    AUTO_LINK: ["ok", "badge-green", "Linked automatically"],
    REVIEW: ["warn", "badge-amber", "Needs a person"],
    VALID_BUT_WRONG: ["warn", "badge-amber", "Valid code, probably the wrong product"],
    NO_MATCH: ["bad", "badge-red", "No registered product: likely counterfeit"]
  };

  /* ------------------------------------------------------------------ helpers */

  /** Marks the characters of b that an alignment with a does not keep. */
  function diffMark(a, b) {
    a = String(a || "").toUpperCase();
    b = String(b || "");
    const B = b.toUpperCase();
    if (!a || !b || a === B) return esc(b);
    const n = a.length, m = B.length;
    const d = Array.from({ length: n + 1 }, (_, i) => [i].concat(Array(m).fill(0)));
    for (let j = 0; j <= m; j++) d[0][j] = j;
    for (let i = 1; i <= n; i++)
      for (let j = 1; j <= m; j++)
        d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === B[j - 1] ? 0 : 1));
    const keep = Array(m).fill(false);
    let i = n, j = m;
    while (i > 0 && j > 0) {
      if (a[i - 1] === B[j - 1] && d[i][j] === d[i - 1][j - 1]) { keep[j - 1] = true; i--; j--; }
      else if (d[i][j] === d[i - 1][j - 1] + 1) { i--; j--; }
      else if (d[i][j] === d[i - 1][j] + 1) { i--; }
      else { j--; }
    }
    let out = "";
    for (let k = 0; k < m; k++) out += keep[k] ? esc(b[k]) : '<span class="u-diff">' + esc(b[k]) + "</span>";
    return out;
  }

  function chip(feature, value, weight) {
    const cls = weight > 0.5 ? "pos" : weight < -0.5 ? "neg" : "neu";
    let v = String(value);
    if (feature === "code") v = v.split(":")[1].replace(/^L\d_/, "").replace(/_/g, " ");
    else v = v.replace(/_/g, " ");
    const w = weight == null ? "" : " " + (weight >= 0 ? "+" : "") + Number(weight).toFixed(1);
    return '<span class="u-chip ' + cls + '" title="' + esc(feature + " = " + value + ", " + w + " bits") + '">' +
      esc((FEATURE_LABEL[feature] || feature) + ": " + v) + '<span class="mono">' + esc(w) + "</span></span>";
  }

  function bar(p, tone) {
    const w = Math.max(0, Math.min(1, p || 0)) * 100;
    const colour = tone || (p >= 0.9 ? "var(--green)" : p >= 0.5 ? "var(--amber)" : "var(--red)");
    return '<div class="row gap-2"><div class="u-mini-track grow"><div class="u-mini-fill" style="width:' + w.toFixed(1) +
      "%; background:" + colour + '"></div></div><span class="mono xsmall tnum">' + num(p) + "</span></div>";
  }

  function setBusy(btn, busy, label) {
    if (!btn) return;
    if (busy) { btn.dataset.label = btn.textContent; btn.textContent = label || "Working…"; btn.disabled = true; }
    else { btn.textContent = btn.dataset.label || btn.textContent; btn.disabled = false; }
  }

  function errorCard(where, err) {
    where.innerHTML = '<div class="u-banner bad"><p class="small"><strong>Request failed.</strong> ' + esc(err.message || err) +
      '</p><p class="u-muted-note" style="margin-top:6px;">Is a node running? <span class="u-code">python scripts/run_cluster.py --mode all</span></p></div>';
  }

  /* ------------------------------------------------------------------ catalogue */

  async function loadCatalog() {
    const c = await api("catalog");
    S.catalog = c;
    $("statProducts").textContent = c.products.length;
    $("statVendors").textContent = c.vendors.length;
    const opts = c.vendors.map((v) => '<option value="' + esc(v.id) + '">' + esc(v.id + " · " + v.name + " · " + (v.city || "")) +
      (v.active ? "" : " (unlicensed)") + "</option>").join("");
    $("mVendor").innerHTML = '<option value="">— unknown —</option>' + opts;
    $("tVendor").innerHTML = opts;
    $("tVendor").value = "VND-001";
    $("productList").innerHTML = c.products.map((p) => '<option value="' + esc(p.uid) + '">' + esc(p.name) + "</option>").join("");
  }

  async function loadSamples() {
    const s = await api("samples");
    S.samples = s.samples || [];
    $("mSample").innerHTML = '<option value="">Pick a captured pack (' + s.total + " on file)…</option>" +
      S.samples.map((x, i) => '<option value="' + i + '">' + esc((x.image ? "📷 " : "") + x.event_id + " · " + x.scan_code) + "</option>").join("");
  }

  /* ------------------------------------------------------------------ match */

  function matchQuery() {
    const ch = $("mChannel").value;
    const q = new URLSearchParams({
      code: $("mCode").value.trim(), channel: ch === "scan" ? "scan" : ch, vendor_id: $("mVendor").value,
      price: $("mPrice").value.trim(), qty: $("mQty").value.trim(), date: $("mDate").value.trim(),
      label: $("mLabel").value.trim(), compare: "1", limit: "8"
    });
    return q.toString();
  }

  async function runMatch() {
    const btn = $("btnMatch");
    setBusy(btn, true, "Matching…");
    try {
      const r = await api("match?" + matchQuery());
      if (r.error) throw new Error(r.error);
      renderMatch(r);
    } catch (e) {
      errorCard($("matchResult"), e);
    } finally {
      setBusy(btn, false);
    }
  }

  function renderMatch(r) {
    const [tone, badge, title] = DECISION[r.decision] || ["warn", "", r.decision];
    const best = (r.candidates || []).find((c) => c.uid === r.best_uid);
    let h = '<div class="u-banner ' + tone + '">' +
      '<div class="row-wrap gap-2 between"><span class="badge ' + badge + '">' + esc(title) + "</span>" +
      '<span class="u-muted-note">' + esc(r.catalogue_size) + " products · " + esc(r.elapsed_ms) + " ms</span></div>";
    if (best) {
      h += '<p class="display display-sm" style="margin-top:10px;">' + esc(best.uid) +
        ' <span class="hl-muted" style="font-size:0.7em;">' + esc(best.product_name) + "</span></p>";
    } else if (r.decision === "NO_MATCH") {
      h += '<p class="display display-sm" style="margin-top:10px;">' + esc(r.code || r.raw_code) + "</p>";
    }
    h += '<p class="small" style="margin-top:8px;">' + esc(r.explanation) + "</p>";
    (r.notes || []).forEach((n) => { h += '<p class="u-muted-note" style="margin-top:4px;">' + esc(n) + "</p>"; });
    h += '<div class="u-two" style="margin-top:12px;"><div><p class="u-muted-note">Probability of the best candidate</p>' +
      bar(r.best_posterior) + '</div><div><p class="u-muted-note">Probability it is no registered product</p>' +
      bar(r.p_none, r.p_none >= 0.5 ? "var(--red)" : "var(--ink-faint)") + "</div></div></div>";

    if (r.label && Object.keys(r.label).length) {
      h += '<div class="card card-inset card-pad-sm" style="margin-top:12px;"><p class="eyebrow">Read off the label</p>';
      ["brand", "strength", "batch", "expiry", "mrp", "code"].forEach((k) => {
        if (r.label[k]) h += '<div class="kv"><span class="kv-key">' + k + '</span><span class="kv-val mono">' + esc(r.label[k]) + "</span></div>";
      });
      h += "</div>";
    }

    h += '<p class="eyebrow" style="margin:18px 0 8px;">Candidates · normalised query <span class="u-code">' + esc(r.code) + "</span></p>";
    if (!r.candidates || !r.candidates.length) {
      h += '<p class="small muted">No registered product shares enough of this code to be a candidate.</p>';
    } else {
      h += '<div class="table-wrap"><table class="data"><thead><tr><th>#</th><th>Registered product</th><th>Code distance</th>' +
        '<th>Evidence (bits)</th><th class="u-cell-right">Weight</th><th>Posterior</th></tr></thead><tbody>';
      r.candidates.forEach((c, i) => {
        const chips = Object.keys(c.features).map((f) => chip(f, c.features[f], c.weights[f])).join("");
        h += "<tr" + (c.uid === r.best_uid ? ' class="u-row-chosen"' : "") + "><td>" + (i + 1) + "</td>" +
          '<td><span class="u-code">' + diffMark(r.code, c.uid) + "</span><br><span class=\"xsmall\">" + esc(c.product_name) +
          " · MRP " + esc(c.mrp) + "</span></td>" +
          '<td class="nowrap"><span class="mono">' + num(c.code_distance, 2) + '</span><br><span class="xsmall faint">' +
          esc(c.code_level.replace(/^L\d_/, "").replace(/_/g, " ")) + "</span></td>" +
          "<td>" + chips + "</td>" +
          '<td class="u-cell-right mono">' + num(c.total_weight, 1) + "</td>" +
          "<td style=\"min-width:120px;\">" + bar(c.posterior) + "</td></tr>";
      });
      h += "</tbody></table></div>";
      h += '<p class="u-muted-note" style="margin-top:8px;">Highlighted characters differ from the query. Each chip is one ' +
        "Fellegi-Sunter comparison: log<sub>2</sub>(P(value | same product) / P(value | different product)).</p>";
    }

    if (r.algorithms) {
      h += '<details class="u-details" style="margin-top:14px;"><summary class="btn btn-ghost btn-sm">How each string metric alone ranks this code</summary>' +
        '<div class="table-wrap" style="margin-top:10px;"><table class="data"><thead><tr><th>Metric</th><th>1st</th><th>2nd</th><th>3rd</th><th class="u-cell-right">Tied at top</th></tr></thead><tbody>';
      r.algorithms.forEach((a) => {
        h += "<tr><td><strong>" + esc(a.algorithm) + "</strong></td>" + a.top.map((t) =>
          '<td class="nowrap"><span class="u-code">' + diffMark(r.code, t.uid) + '</span> <span class="xsmall faint">' + num(t.score) + "</span></td>").join("") +
          '<td class="u-cell-right mono">' + esc(a.ties_at_top) + "</td></tr>";
      });
      h += "</tbody></table></div><p class=\"u-muted-note\" style=\"margin-top:6px;\">None of these can say \"no product\": " +
        "each always returns its nearest code, which for a counterfeit is a real product.</p></details>";
    }
    $("matchResult").innerHTML = h;
  }

  function fillMatch(o) {
    $("mCode").value = o.code || "";
    $("mChannel").value = o.channel || "manual";
    $("mVendor").value = o.vendor || "";
    $("mPrice").value = o.price == null ? "" : o.price;
    $("mQty").value = o.qty == null ? "" : o.qty;
    $("mDate").value = o.date || "";
    $("mLabel").value = o.label || "";
    const img = $("mPreview");
    if (o.image) { img.src = o.image; img.classList.remove("hidden"); $("btnOcr").disabled = false; }
    else { img.classList.add("hidden"); img.removeAttribute("src"); $("btnOcr").disabled = true; }
  }

  function sampleToQuery(x) {
    return { code: x.scan_code, channel: x.scan_method === "ocr" ? "ocr" : x.scan_method === "manual" ? "manual" : "scan",
      vendor: x.vendor_id, price: x.price_paid, qty: x.quantity, date: x.date, label: x.label_text, image: x.image };
  }

  function demo(kind) {
    document.querySelectorAll("[data-demo]").forEach((b) => b.classList.toggle("is-active", b.dataset.demo === kind));
    if (kind === "ciplox") {
      fillMatch({ code: "MED-ASAL1-OO7", channel: "manual", vendor: "VND-005", price: 95, qty: 1, date: "2025-06-02 11:20" });
    } else if (kind === "novamox") {
      const x = S.samples.find((s) => s.event_id === "PE-G-DEMO-02");
      fillMatch(x ? sampleToQuery(x) : { code: "MED-ASALI-0O1", channel: "ocr", vendor: "VND-001", price: 115, qty: 1, date: "2025-03-14 18:05" });
    } else if (kind === "fake") {
      fillMatch({ code: "MED-ASALI-011", channel: "scan", vendor: "VND-007", price: 30, qty: 1, date: "2025-05-10 19:00" });
    } else if (S.samples.length) {
      fillMatch(sampleToQuery(S.samples[Math.floor(Math.random() * S.samples.length)]));
    }
    runMatch();
  }

  /* ------------------------------------------------------------------ OCR */

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src; s.onload = resolve; s.onerror = () => reject(new Error("could not load " + src));
      document.head.appendChild(s);
    });
  }

  async function runOcr() {
    const img = $("mPreview");
    if (!img.src) return;
    const status = $("ocrStatus");
    const btn = $("btnOcr");
    setBusy(btn, true, "Reading…");
    try {
      if (!window.Tesseract) {
        status.textContent = "Loading the OCR engine…";
        await loadScript("https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js");
      }
      const worker = await Tesseract.createWorker("eng", 1, {
        logger: (m) => { if (m.status) status.textContent = m.status + (m.progress ? " " + Math.round(m.progress * 100) + "%" : ""); }
      });
      const { data } = await worker.recognize(img);
      await worker.terminate();
      const lines = data.text.split(/\n+/).map((l) => l.trim()).filter(Boolean);
      $("mLabel").value = lines.join(" | ");
      const code = data.text.toUpperCase().match(/M[E3F][D0O][\s\-_.]?[A-Z0-9]{3,8}[\s\-_.]?[A-Z0-9]{2,4}/);
      if (code) $("mCode").value = code[0];
      $("mChannel").value = "ocr";
      status.textContent = "OCR read " + lines.length + " line(s), confidence " + Math.round(data.confidence) + "%. Running the match…";
      runMatch();
    } catch (e) {
      status.textContent = "OCR unavailable (" + e.message + "). Offline? Use the recorded reading in the text box.";
    } finally {
      setBusy(btn, false);
    }
  }

  /* ------------------------------------------------------------------ reverse */

  async function runReverse(uid) {
    uid = (uid || $("rUid").value).trim();
    if (!uid) return;
    $("rUid").value = uid;
    const out = $("reverseResult");
    out.innerHTML = '<p class="small muted">Searching every silo…</p>';
    try {
      const r = await api("reverse?uid=" + encodeURIComponent(uid));
      if (!r.found) { out.innerHTML = '<div class="u-banner warn"><p class="small">' + esc(r.message) + "</p></div>"; return; }
      const p = r.product;
      let h = '<div class="bento" style="gap:12px;">' +
        '<div class="col-4"><div class="card card-inset card-pad-sm" style="height:100%;"><p class="eyebrow">Registered product</p>' +
        '<p class="h-md" style="margin-top:6px;">' + esc(p.product_name) + '</p><p class="u-code small">' + esc(p.product_uid) + "</p>" +
        '<div class="kv"><span class="kv-key">Batch</span><span class="kv-val mono">' + esc(p.batch_number) + "</span></div>" +
        '<div class="kv"><span class="kv-key">Maker</span><span class="kv-val">' + esc(p.manufacturer_name || p.manufacturer_id) + "</span></div>" +
        '<div class="kv"><span class="kv-key">MRP</span><span class="kv-val">Rs ' + esc(p.msrp_kes) + "</span></div>" +
        '<div class="kv"><span class="kv-key">Shipped to</span><span class="kv-val mono xsmall">' + esc(r.shipped_to.join(", ") || "nobody") + "</span></div></div></div>" +
        '<div class="col-8"><div class="bento" style="gap:10px;">' +
        ['total', 'exact', 'noisy'].map((k) => '<div class="col-4"><div class="card card-inset card-pad-sm"><p class="stat-num">' + r.counts[k] +
          '</p><p class="xsmall faint">' + ({ total: "records found", exact: "stored exactly", noisy: "stored with a damaged code" }[k]) + "</p></div></div>").join("") +
        "</div><p class=\"u-muted-note\" style=\"margin-top:10px;\">By silo: " +
        Object.keys(r.counts.by_source).map((k) => esc(k.toUpperCase() + " " + r.counts.by_source[k])).join(" · ") + "</p></div></div>";
      h += '<div class="table-wrap u-scroll" style="margin-top:14px;"><table class="data"><thead><tr><th>Silo</th><th>Record</th>' +
        '<th>Stored code</th><th>Posterior</th><th>Matcher\'s decision</th><th>Context</th></tr></thead><tbody>';
      r.records.forEach((x) => {
        const verdict = x.points_here ? '<span class="badge badge-green">points here</span>' :
          '<span class="badge badge-amber">' + esc(x.decision) + (x.best_uid ? " → " + esc(x.best_uid) : "") + "</span>";
        h += "<tr><td class=\"nowrap\">" + esc(x.db_id.toUpperCase() + " " + x.table) + '</td><td class="mono xsmall">' + esc(x.key) + "</td>" +
          '<td><span class="u-code">' + (x.exact ? esc(x.stored_code) : diffMark(r.uid, x.stored_code)) + "</span>" +
          '<br><span class="xsmall faint">' + esc(x.channel) + "</span></td>" +
          '<td style="min-width:110px;">' + bar(x.posterior) + "</td><td>" + verdict + "</td>" +
          '<td class="xsmall">' + esc(x.summary) + "</td></tr>";
      });
      h += "</tbody></table></div>";
      out.innerHTML = h;
    } catch (e) {
      errorCard(out, e);
    }
  }

  /* ------------------------------------------------------------------ benchmark */

  async function loadBenchmark() {
    try {
      const b = await api("benchmark");
      S.bench = b;
      renderBenchmark(b);
    } catch (e) {
      errorCard($("benchResult"), e);
    }
  }

  function renderBenchmark(b) {
    const out = $("benchResult");
    if (b.missing) {
      out.innerHTML = '<div class="card card-pad-lg"><p class="small">' + esc(b.message) + "</p></div>";
      return;
    }
    const ms = b.methods;
    const chosen = ms.find((m) => /chosen/.test(m.name)) || ms[ms.length - 1];
    const strings = ms.filter((m) => m.family.indexOf("string") === 0);
    const bestString = strings.slice().sort((a, b2) => (b2.top1_noisy || 0) - (a.top1_noisy || 0))[0];
    const codeOnly = ms.find((m) => /code only/.test(m.name));
    const jw = ms.find((m) => m.name === "Jaro-Winkler");
    const lev = ms.find((m) => m.name === "Levenshtein");
    const sx = ms.find((m) => m.name === "Soundex");
    const d = b.dataset;
    $("statThreshold").textContent = b.thresholds ? b.thresholds.link : "—";

    let h = '<div class="card card-pad-lg">' +
      '<p class="small muted">Held-out test split: <strong>' + d.test + "</strong> records (" + d.test_positives + " genuine, " +
      d.test_counterfeits + " counterfeit) against a registry of " + d.catalogue_size + " products. Parameters, substitution costs " +
      "and thresholds were fitted on a separate training split of " + d.train + " records. Generated " + esc(b.generated_at) + ".</p>" +
      (d.cleansing_changes_applied ? '<p class="small" style="margin-top:6px; color:var(--amber-ink);">Measured after ' + d.cleansing_changes_applied +
        " cleansing change(s) had been applied, so fewer damaged records remained. Rebuild the data for the reference numbers.</p>" : "");
    h += '<div class="table-wrap" style="margin-top:14px;"><table class="data"><thead><tr><th>Method</th>' +
      '<th class="u-cell-right">Top-1, all</th><th class="u-cell-right">Top-1, damaged codes</th><th class="u-cell-right">Recall@5</th>' +
      '<th class="u-cell-right">Link precision</th><th class="u-cell-right">Link recall</th><th class="u-cell-right">F1</th>' +
      '<th class="u-cell-right">Fakes linked to a real product</th></tr></thead><tbody>';
    ms.forEach((m) => {
      h += "<tr" + (m === chosen ? ' class="u-row-chosen"' : "") + "><td><strong>" + esc(m.name) + '</strong><br><span class="xsmall faint">' +
        esc(m.family) + "</span></td>" +
        ["top1", "top1_noisy", "recall_at_5", "precision", "recall", "f1", "false_link_rate_fakes"].map((k) =>
          '<td class="u-heat">' + pct(m[k]) + "</td>").join("") + "</tr>";
    });
    h += "</tbody></table></div>";

    const pts = [];
    if (chosen && bestString)
      pts.push("Best string metric on damaged codes is <strong>" + esc(bestString.name) + "</strong> at " + pct(bestString.top1_noisy) +
        " top-1; the chosen model reaches <strong>" + pct(chosen.top1_noisy) + "</strong>.");
    if (jw && lev)
      pts.push("At their best thresholds, Jaro-Winkler links <strong>" + pct(jw.false_link_rate_fakes) + "</strong> and Levenshtein <strong>" +
        pct(lev.false_link_rate_fakes) + "</strong> of counterfeit codes to a real product. A string metric has no way to say “none”. " +
        "The chosen model links <strong>" + pct(chosen.false_link_rate_fakes) + "</strong>, and catches " + pct(chosen.fakes_caught) + " of them outright.");
    if (sx) pts.push("Soundex ties on " + pct(sx.tied_top1_rate) + " of queries: phonetic codes are for names, not serial numbers.");
    if (codeOnly) pts.push("Context (custody, price, dates, label) lifts top-1 on damaged codes from " + pct(codeOnly.top1_noisy) +
      " (code evidence only) to " + pct(chosen.top1_noisy) + ", resolving codes that land on a sibling batch.");
    if (chosen.review_rate != null) pts.push(pct(chosen.review_rate) + " of records are left to a person; for those, the top candidate is right " +
      pct(chosen.review_top1_correct) + " of the time.");
    h += '<ul class="small" style="margin:16px 0 0 18px; line-height:1.7;">' + pts.map((p) => "<li>" + p + "</li>").join("") + "</ul></div>";

    // per noise kind
    const kinds = Object.keys(chosen.by_kind || {});
    h += '<div class="bento" style="gap:14px; margin-top:14px;">';
    h += '<div class="col-7"><div class="card card-pad-lg" style="height:100%;"><p class="eyebrow">Top-1 by kind of damage (test split)</p>' +
      '<div class="table-wrap" style="margin-top:10px;"><table class="data"><thead><tr><th>Damage</th>' +
      ms.map((m) => '<th class="u-cell-right" title="' + esc(m.name) + '">' + esc(shortName(m.name)) + "</th>").join("") + "</tr></thead><tbody>";
    kinds.forEach((k) => {
      h += "<tr><td>" + esc(k.replace(/_/g, " ")) + "</td>" + ms.map((m) => {
        const v = (m.by_kind || {})[k];
        return '<td class="u-heat" style="' + heat(v) + '">' + (v == null ? "—" : Math.round(v * 100)) + "</td>";
      }).join("") + "</tr>";
    });
    h += "</tbody></table></div></div></div>";

    h += '<div class="col-5"><div class="card card-pad-lg" style="height:100%;"><p class="eyebrow">Learned confusions (cheapest substitutions)</p>' +
      '<div class="table-wrap" style="margin-top:10px;"><table class="data"><thead><tr><th>Printed</th><th>Recorded as</th><th class="u-cell-right">Cost</th><th class="u-cell-right">Seen in training</th></tr></thead><tbody>' +
      (b.confusions || []).map((c) => '<tr><td class="u-code">' + esc(c.truth) + '</td><td class="u-code">' + esc(c.observed) +
        '</td><td class="u-cell-right mono">' + num(c.cost, 2) + '</td><td class="u-cell-right mono">' + esc(c.seen) + "</td></tr>").join("") +
      "</tbody></table></div><p class=\"u-muted-note\" style=\"margin-top:8px;\">Any other substitution costs 1.0, a transposition 0.6, a dropped separator 0.1.</p></div></div>";
    h += "</div>";

    // weights + names + blocking
    const w1 = (b.weights || {}).db1 || {};
    h += '<div class="bento" style="gap:14px; margin-top:14px;">';
    h += '<div class="col-7"><div class="card card-pad-lg" style="height:100%;"><p class="eyebrow">Fellegi-Sunter weights for a checkout (DB1), in bits</p>' +
      '<div class="table-wrap u-scroll" style="margin-top:10px; max-height:380px;"><table class="data"><thead><tr><th>Evidence</th><th>Value</th><th class="u-cell-right">Weight</th></tr></thead><tbody>';
    Object.keys(w1).forEach((f) => {
      Object.keys(w1[f]).sort((a, b2) => w1[f][b2] - w1[f][a]).forEach((v) => {
        const wt = w1[f][v];
        h += "<tr><td>" + esc(FEATURE_LABEL[f] || f) + '</td><td class="mono xsmall">' + esc(v) + '</td><td class="u-cell-right mono" style="color:' +
          (wt > 0 ? "var(--green-ink)" : "var(--red-ink)") + '">' + (wt > 0 ? "+" : "") + num(wt, 2) + "</td></tr>";
      });
    });
    h += "</tbody></table></div></div></div>";
    const nm = b.names || { methods: [] };
    h += '<div class="col-5"><div class="stack gap-3" style="height:100%;"><div class="card card-pad-lg"><p class="eyebrow">Brand names (label text, complaints)</p>' +
      '<p class="u-muted-note" style="margin-top:4px;">' + esc(nm.n_queries) + " misspelt names against " + esc(nm.n_brands) + " brands.</p>" +
      '<div class="table-wrap" style="margin-top:8px;"><table class="data"><tbody>' +
      nm.methods.slice().sort((a, b2) => b2.top1 - a.top1).map((m) => "<tr><td>" + esc(m.name) + '</td><td class="u-cell-right mono">' + pct(m.top1) + "</td></tr>").join("") +
      "</tbody></table></div><p class=\"u-muted-note\" style=\"margin-top:8px;\">For names every edit metric is within a point of the best; " +
      "what fails is Soundex on its own. The matcher compares brand names with Jaro-Winkler; codes use the learned distance.</p></div>" +
      '<div class="card card-pad-lg"><p class="eyebrow">Blocking</p>' +
      '<div class="kv"><span class="kv-key">Method</span><span class="kv-val xsmall">' + esc(b.blocking.method) + "</span></div>" +
      '<div class="kv"><span class="kv-key">True product kept in block</span><span class="kv-val mono">' + pct(b.blocking.pairs_completeness, 2) + "</span></div>" +
      '<div class="kv"><span class="kv-key">Comparisons avoided</span><span class="kv-val mono">' + pct(b.blocking.reduction_ratio) + "</span></div>" +
      '<div class="kv"><span class="kv-key">Mean candidates per record</span><span class="kv-val mono">' + esc(b.blocking.mean_block_size) + "</span></div>" +
      '<div class="kv"><span class="kv-key">Thresholds (link / none)</span><span class="kv-val mono">' + esc(b.thresholds.link + " / " + b.thresholds.none) + "</span></div></div></div></div>";
    h += "</div>";
    out.innerHTML = h;
  }

  function shortName(n) {
    return { "Levenshtein": "Lev", "Damerau-Levenshtein": "DL", "Jaro-Winkler": "JW", "Bigram Jaccard": "Jacc",
      "Soundex": "Sdx", "Learned OCR distance": "OCR-d", "Fellegi-Sunter, code only": "FS code",
      "Fellegi-Sunter + context (chosen)": "FS+ctx" }[n] || n;
  }

  function heat(v) {
    if (v == null) return "";
    const a = Math.max(0, Math.min(1, v));
    return "background: rgba(" + (a > 0.5 ? "61,220,132," + ((a - 0.5) * 0.5).toFixed(2) : "255,77,61," + ((0.5 - a) * 0.5).toFixed(2)) + ");";
  }

  async function retrain() {
    const btn = $("btnRetrain");
    setBusy(btn, true, "Training…");
    try {
      await post("train", { quick: false });
      const t0 = Date.now();
      for (;;) {
        await new Promise((r) => setTimeout(r, 3000));
        const s = await api("train_status");
        $("trainStatus").textContent = s.running ? "Fitting and benchmarking… " + Math.round((Date.now() - t0) / 1000) + " s" :
          s.error ? "Failed: " + s.error : "Finished " + (s.finished_at || "");
        if (!s.running) break;
      }
      await loadBenchmark();
    } catch (e) {
      $("trainStatus").textContent = "Failed: " + e.message;
    } finally {
      setBusy(btn, false);
    }
  }

  /* ------------------------------------------------------------------ cleanse */

  async function runScan() {
    const btn = $("btnScan");
    setBusy(btn, true, "Scanning…");
    $("scanStatus").textContent = "Scanning every record in DB1, DB2, DB3 and DB4…";
    try {
      const r = await api("scan");
      if (r.error) throw new Error(r.error);
      S.scan = r;
      S.page = 0;
      renderScan();
      $("btnApply").disabled = !r.summary.auto && !r.summary.retain;
    } catch (e) {
      $("scanStatus").textContent = "Scan failed: " + e.message;
    } finally {
      setBusy(btn, false);
    }
  }

  function renderScan() {
    const r = S.scan;
    const s = r.summary;
    const rs = r.records_scanned;
    $("scanStatus").innerHTML = "Scanned " + esc(Object.keys(rs).map((k) => rs[k] + " " + k.replace(/_/g, " ")).join(", ")) +
      " in " + esc(r.elapsed_ms) + " ms. <strong>" + s.total_open + "</strong> open: " + s.auto + " automatic, " + s.review +
      " for review, " + s.retain + " to quarantine" + (s.dismissed ? ", " + s.dismissed + " dismissed" : "") + ".";
    let h = "";
    Object.keys(s.categories).forEach((k) => {
      const c = s.by_category[k];
      const open = c.AUTO + c.REVIEW + c.RETAIN;
      h += '<div class="col-3"><div class="u-tile' + ($("fCategory").value === k ? " is-active" : "") + '" data-cat="' + k + '">' +
        '<p class="num">' + open + '</p><p class="small" style="margin-top:2px;"><strong>' + esc(s.categories[k].label) + "</strong></p>" +
        '<p class="u-muted-note" style="margin-top:4px;">' + esc(s.categories[k].description) + "</p>" +
        '<p class="xsmall faint" style="margin-top:6px;">' + c.AUTO + " auto · " + c.REVIEW + " review · " + c.RETAIN + " quarantine</p></div></div>";
    });
    const acc = r.accuracy_vs_ground_truth;
    if (acc && acc.available) {
      const line = (k, label) => acc[k] && acc[k].n ? '<div class="kv"><span class="kv-key">' + label + '</span><span class="kv-val mono">' +
        acc[k].correct + " / " + acc[k].n + " (" + pct(acc[k].precision) + ")</span></div>" : "";
      h += '<div class="col-3"><div class="u-tile" style="cursor:default;"><p class="small"><strong>Checked against ground truth</strong></p>' +
        line("auto", "Automatic links correct") + line("review", "Review suggestions correct") + line("retain", "Quarantined that are fakes") +
        '<p class="u-muted-note" style="margin-top:6px;">The generator\'s labels are never used to decide; only to score.</p></div></div>';
    }
    $("scanTiles").innerHTML = h;
    const cats = $("fCategory");
    if (cats.options.length <= 1) {
      Object.keys(s.categories).forEach((k) => {
        const o = document.createElement("option");
        o.value = k; o.textContent = s.categories[k].label;
        cats.appendChild(o);
      });
    }
    renderIssues();
  }

  function filteredIssues() {
    if (!S.scan) return [];
    const dec = $("fDecision").value, cat = $("fCategory").value, q = $("fSearch").value.trim().toUpperCase();
    return S.scan.issues.filter((i) => {
      if (dec === "open" && !["AUTO", "REVIEW", "RETAIN"].includes(i.decision)) return false;
      if (dec !== "open" && dec !== "all" && i.decision !== dec) return false;
      if (cat && i.category !== cat) return false;
      if (q && (String(i.current) + " " + String(i.proposed) + " " + i.pk_val + " " + i.table).toUpperCase().indexOf(q) < 0) return false;
      return true;
    });
  }

  function renderIssues() {
    const rows = filteredIssues();
    const pages = Math.max(1, Math.ceil(rows.length / S.pageSize));
    S.page = Math.min(S.page, pages - 1);
    const slice = rows.slice(S.page * S.pageSize, (S.page + 1) * S.pageSize);
    $("issueCount").textContent = rows.length + " issue(s)";
    $("pageInfo").textContent = "page " + (S.page + 1) + " of " + pages;
    if (!slice.length) { $("issueRows").innerHTML = '<tr><td colspan="7" class="muted">Nothing here.</td></tr>'; return; }
    const badge = { AUTO: "badge-green", REVIEW: "badge-amber", RETAIN: "badge-red", DISMISSED: "" };
    $("issueRows").innerHTML = slice.map((i) => {
      const cur = i.current == null ? "∅" : String(i.current);
      const prop = i.proposed == null ? (i.decision === "RETAIN" ? "quarantine flag" : "—") : String(i.proposed);
      let action = '<span class="badge ' + (badge[i.decision] || "") + '">' + esc(i.decision.toLowerCase()) + "</span>";
      if (i.decision === "REVIEW") {
        const opts = (i.candidates || []).map((c) => '<option value="' + esc(c.uid) + '"' + (c.uid === i.proposed ? " selected" : "") + ">" +
          esc(c.uid + " (" + num(c.posterior, 2) + ")") + "</option>").join("");
        action += '<div class="stack gap-2" style="margin-top:6px; min-width:170px;">' +
          (opts ? '<select class="field field-sm u-select" data-pick="' + i.issue_id + '">' + opts + "</select>" : "") +
          '<div class="row-wrap gap-2"><button class="btn btn-primary btn-sm" data-accept="' + i.issue_id + '">Accept</button>' +
          (i.can_quarantine ? '<button class="btn btn-danger btn-sm" data-quarantine="' + i.issue_id + '" title="No registered product: flag it as counterfeit evidence">Counterfeit</button>' : "") +
          '<button class="btn btn-ghost btn-sm" data-reject="' + i.issue_id + '">Keep as is</button></div></div>';
      }
      const why = String(i.explanation || "");
      return "<tr><td class=\"nowrap\"><strong>" + esc(i.category_label) + '</strong><br><span class="xsmall faint">' + esc(i.method) + "</span></td>" +
        '<td class="mono xsmall nowrap">' + esc(i.db_id + "." + i.table) + "<br>" + esc(i.pk_val) + (i.column !== "*" ? " · " + esc(i.column) : "") + "</td>" +
        '<td><span class="u-code">' + esc(cur) + "</span></td>" +
        '<td><span class="u-code">' + (i.proposed && i.current ? diffMark(cur, prop) : esc(prop)) + "</span>" +
        (i.truth ? '<br><span class="xsmall ' + (String(i.truth) === prop || (i.truth === "COUNTERFEIT" && i.decision === "RETAIN") ? "faint" : "") +
          '">truth: ' + esc(i.truth) + "</span>" : "") + "</td>" +
        '<td style="min-width:110px;">' + bar(i.confidence) + "</td><td>" + action + "</td>" +
        '<td class="xsmall" style="max-width:420px;">' + (why.length > 160 ? '<details class="u-details"><summary>' + esc(why.slice(0, 160)) +
          '… <span class="faint">more</span></summary>' + esc(why) + "</details>" : esc(why)) + "</td></tr>";
    }).join("");
  }

  async function applyAuto() {
    const btn = $("btnApply");
    setBusy(btn, true, "Applying…");
    try {
      const r = await post("apply", { mode: "auto" });
      if (r.error) throw new Error(r.error);
      showApply(r, "Automatic fixes applied");
      await Promise.all([runScan(), loadLineage()]);
    } catch (e) {
      errorCard($("applyResult"), e);
    } finally {
      setBusy(btn, false);
    }
  }

  function showApply(r, title) {
    const a = r.after || {};
    $("applyResult").innerHTML = '<div class="u-banner ok"><div class="row-wrap gap-2 between"><p class="small"><strong>' + esc(title) +
      "</strong> · run <span class=\"u-code\">" + esc(r.run_id) + "</span> · " + r.issues_applied + " issue(s), " + r.changes_applied +
      " change(s)" + (r.changes_skipped ? ", " + r.changes_skipped + " skipped" : "") + "</p>" +
      '<button class="btn btn-ghost btn-sm" data-undo="' + esc(r.run_id) + '">Undo this run</button></div>' +
      '<p class="u-muted-note" style="margin-top:6px;">' + Object.keys(r.by_category || {}).map((k) => esc(k.replace(/_/g, " ") + ": " + r.by_category[k])).join(" · ") + "</p>" +
      '<p class="small" style="margin-top:8px;">After the run: <strong>' + (a.auto || 0) + "</strong> automatic issues left, <strong>" + (a.review || 0) +
      "</strong> waiting for review, <strong>" + (a.retain || 0) + "</strong> still to quarantine.</p></div>";
  }

  async function decide(issueId, decision, uid) {
    try {
      const r = await post("decide", { issue_id: issueId, decision: decision, uid: uid });
      if (r.success === false) throw new Error(r.error || "decision failed");
      if (r.run_id) showApply(r, decision === "quarantine" ? "Quarantined as counterfeit evidence" : "Review accepted");
      await Promise.all([runScan(), loadLineage()]);
    } catch (e) {
      errorCard($("applyResult"), e);
    }
  }

  /* ------------------------------------------------------------------ lineage */

  async function loadLineage() {
    const out = $("lineageResult");
    try {
      const l = await api("lineage?limit=80");
      if (!l.runs.length) { out.innerHTML = '<p class="muted small">Nothing applied yet. Every change a cleansing run makes is recorded here with its old value.</p>'; return; }
      let h = '<div class="table-wrap"><table class="data"><thead><tr><th>Run</th><th>When</th><th>Mode</th><th class="u-cell-right">Issues</th>' +
        '<th class="u-cell-right">Changes</th><th>Status</th><th></th></tr></thead><tbody>';
      l.runs.forEach((r) => {
        h += '<tr><td class="mono xsmall">' + esc(r.run_id) + "</td><td class=\"xsmall\">" + esc(r.started_at) + "</td><td>" + esc(r.mode + " · " + r.actor) +
          '</td><td class="u-cell-right">' + r.issues_applied + '</td><td class="u-cell-right">' + r.changes_applied + "</td><td>" +
          (r.undone_at ? '<span class="badge">undone ' + esc(r.undone_at) + "</span>" : '<span class="badge badge-green">applied</span>') + "</td><td>" +
          (r.undone_at ? "" : '<button class="btn btn-ghost btn-sm" data-undo="' + esc(r.run_id) + '">Undo</button>') + "</td></tr>";
      });
      h += '</tbody></table></div><p class="eyebrow" style="margin:18px 0 8px;">Latest changes</p><div class="table-wrap u-scroll" style="max-height:360px;"><table class="data"><thead><tr>' +
        "<th>Run</th><th>Category</th><th>Where</th><th>Change</th><th>Old → new</th></tr></thead><tbody>";
      l.actions.forEach((a) => {
        const oldv = a.old_value == null ? "∅" : JSON.parse(a.old_value);
        const newv = a.new_value == null ? (a.action === "DELETE" ? "row deleted (snapshot kept)" : "∅") : JSON.parse(a.new_value);
        h += '<tr><td class="mono xsmall">' + esc(a.run_id.slice(-9)) + "</td><td class=\"xsmall\">" + esc(a.category) + '</td><td class="mono xsmall">' +
          esc(a.db_id + "." + a.table_name + " " + a.pk_val) + "</td><td class=\"xsmall\">" + esc(a.action + (a.column_name ? " " + a.column_name : "")) +
          '</td><td class="xsmall"><span class="u-code">' + esc(oldv) + "</span> → <span class=\"u-code\">" + esc(newv) + "</span></td></tr>";
      });
      out.innerHTML = h + "</tbody></table></div>";
    } catch (e) {
      errorCard(out, e);
    }
  }

  async function undo(runId) {
    if (!confirm("Revert every change made by " + runId + "?")) return;
    try {
      const r = await post("undo", { run_id: runId });
      if (!r.success) throw new Error(r.error);
      $("applyResult").innerHTML = '<div class="u-banner warn"><p class="small">Reverted ' + r.actions_reverted + " change(s) of <span class=\"u-code\">" +
        esc(runId) + "</span>.</p></div>";
      await Promise.all([loadLineage(), S.scan ? runScan() : null]);
    } catch (e) {
      errorCard($("applyResult"), e);
    }
  }

  /* ------------------------------------------------------------------ tests */

  function assessment(where, res) {
    if (!res.success) { where.innerHTML = '<div class="u-banner bad"><p class="small">' + esc(res.error || "write failed") + "</p></div>"; return; }
    const q = res.data_quality;
    if (!q) { where.innerHTML = '<div class="u-banner ok"><p class="small">Written. ' + esc(res.data_quality_error || "") + "</p></div>"; return; }
    const [tone, badge, title] = DECISION[q.decision] || ["warn", "", q.decision];
    where.innerHTML = '<div class="u-banner ' + tone + '"><p class="small">Written. The write response already carries the matcher\'s reading:</p>' +
      '<p style="margin-top:8px;"><span class="badge ' + badge + '">' + esc(title) + "</span> " +
      (q.best_uid ? '<span class="u-code">' + esc(q.best_uid) + "</span> · p = " + num(q.posterior) : "p(no product) = " + num(q.p_none)) + "</p>" +
      '<p class="xsmall" style="margin-top:6px;">' + esc(q.explanation) + "</p></div>";
  }

  async function testInsert() {
    const id = "PE-TEST-" + (Date.now() % 1e7);
    const data = { event_id: id, scan_code: $("tCode").value, scan_timestamp: $("tDate").value, vendor_id: $("tVendor").value,
      customer_age_group: "adult", quantity_bought: 1, price_paid: parseFloat($("tPrice").value) || 0, currency: "INR",
      payment_method: "cash", scan_method: $("tMethod").value, device_id: "POS-TEST", anomaly_flag: 0,
      notes: "Inserted from the uncertainty test panel" };
    const res = await explorerOp("db1", "INSERT", "purchase_events", data);
    assessment($("tInsertOut"), res);
    if (res.success) { S.tests.insert = id; $("btnInsertUndo").disabled = false; }
  }

  async function testFake() {
    const id = "PE-TEST-F" + (Date.now() % 1e7);
    const data = { event_id: id, scan_code: "MED-ASALI-011", scan_timestamp: "2025-05-10 19:00:00", vendor_id: "VND-007",
      customer_age_group: "adult", quantity_bought: 1, price_paid: 30, currency: "INR", payment_method: "cash",
      scan_method: "barcode", device_id: "POS-007-X", anomaly_flag: 0, notes: "Counterfeit test from the uncertainty page" };
    const res = await explorerOp("db1", "INSERT", "purchase_events", data);
    assessment($("tFakeOut"), res);
    if (res.success) { S.tests.fake = id; $("btnFakeUndo").disabled = false; }
  }

  async function deleteEvent(key, btn, out) {
    const id = S.tests[key];
    if (!id) return;
    const res = await explorerOp("db1", "DELETE", "purchase_events", { _key_column: "event_id", _key_value: id });
    $(out).innerHTML = '<p class="small muted">' + (res.success ? "Deleted " + esc(id) + "." : esc(res.error)) + "</p>";
    S.tests[key] = null;
    $(btn).disabled = true;
  }

  /** One confusable glyph swapped, the way a camera would misread the code. */
  function misread(uid) {
    const swaps = [["0", "O"], ["1", "I"], ["8", "B"], ["5", "S"], ["2", "Z"]];
    for (let k = uid.length - 1; k >= 0; k--) {
      const s = swaps.find((p) => p[0] === uid[k]);
      if (s) return uid.slice(0, k) + s[1] + uid.slice(k + 1);
    }
    return uid.slice(0, -2) + uid.slice(-1) + uid.slice(-2, -1);
  }

  async function probeFor(uid) {
    if (uid === "MED-ASALI-007") return { code: "MED-ASAL1-OO7", channel: "manual", vendor_id: "VND-005", price: 95, qty: 1, date: "2025-06-02 11:20" };
    const r = await api("reverse?uid=" + encodeURIComponent(uid));
    const rec = (r.records || []).find((x) => x.db_id === "db1" && x.exact);
    const c = (rec && rec.context) || {};
    return { code: misread(uid), channel: "manual", vendor_id: c.vendor_id || "", date: c.date || "",
      price: c.price_paid == null ? "" : c.price_paid, qty: c.quantity || 1 };
  }

  async function probeMatch(p) {
    const q = new URLSearchParams({ code: p.code, channel: p.channel, vendor_id: p.vendor_id || "", price: p.price || "",
      qty: p.qty || "", date: p.date || "", limit: "4" });
    return api("match?" + q.toString());
  }

  function beforeAfter(where, probe, before, after, what) {
    const line = (r) => '<span class="badge ' + ((DECISION[r.decision] || [])[1] || "") + '">' + esc(r.decision) + "</span> " +
      (r.best_uid ? '<span class="u-code">' + esc(r.best_uid) + "</span> p = " + num(r.best_posterior) : "p(no product) = " + num(r.p_none));
    $(where).innerHTML = '<div class="u-banner warn"><p class="small">' + esc(what) + ' Probe: <span class="u-code">' + esc(probe.code) + "</span>" +
      (probe.vendor_id ? " at " + esc(probe.vendor_id) : "") + (probe.price ? " for Rs " + esc(probe.price) : "") + "</p>" +
      '<div class="kv"><span class="kv-key">Before</span><span class="kv-val">' + line(before) + "</span></div>" +
      '<div class="kv"><span class="kv-key">After</span><span class="kv-val">' + line(after) + "</span></div></div>";
  }

  async function testMrp() {
    const uid = $("tMrpUid").value.trim();
    const view = await explorerOp("db3", "VIEW", "products", { product_uid: uid });
    if (!view.success || !view.records.length) { $("tMrpOut").innerHTML = '<p class="small">No product ' + esc(uid) + ".</p>"; return; }
    const old = view.records[0].msrp_kes;
    const probe = await probeFor(uid);
    const before = await probeMatch(probe);
    const res = await explorerOp("db3", "UPDATE", "products", { _key_column: "product_uid", _key_value: uid, msrp_kes: parseFloat($("tMrp").value) });
    if (!res.success) { $("tMrpOut").innerHTML = '<p class="small">' + esc(res.error) + "</p>"; return; }
    const after = await probeMatch(probe);
    S.tests.mrp = { uid: uid, old: old };
    $("btnMrpUndo").disabled = false;
    beforeAfter("tMrpOut", probe, before, after, "MRP of " + uid + " changed from Rs " + old + " to Rs " + $("tMrp").value + ".");
  }

  async function undoMrp() {
    const t = S.tests.mrp;
    if (!t) return;
    await explorerOp("db3", "UPDATE", "products", { _key_column: "product_uid", _key_value: t.uid, msrp_kes: t.old });
    $("tMrpOut").innerHTML = '<p class="small muted">Restored MRP of ' + esc(t.uid) + " to Rs " + esc(t.old) + ".</p>";
    S.tests.mrp = null;
    $("btnMrpUndo").disabled = true;
  }

  async function testDelete() {
    const uid = $("tDelUid").value.trim();
    const view = await explorerOp("db3", "VIEW", "products", { product_uid: uid });
    if (!view.success || !view.records.length) { $("tDelOut").innerHTML = '<p class="small">No product ' + esc(uid) + ".</p>"; return; }
    if (!confirm("Delete " + uid + " from the DB3 registry? You can restore it from this card.")) return;
    const row = view.records[0];
    const probe = await probeFor(uid);
    const before = await probeMatch(probe);
    const res = await explorerOp("db3", "DELETE", "products", { _key_column: "product_uid", _key_value: uid });
    if (!res.success) { $("tDelOut").innerHTML = '<p class="small">' + esc(res.error) + "</p>"; return; }
    const after = await probeMatch(probe);
    S.tests.del = row;
    $("btnDelUndo").disabled = false;
    beforeAfter("tDelOut", probe, before, after, uid + " deleted from DB3.");
  }

  async function undoDelete() {
    const row = S.tests.del;
    if (!row) return;
    const res = await explorerOp("db3", "INSERT", "products", row);
    $("tDelOut").innerHTML = '<p class="small muted">' + (res.success ? "Restored " + esc(row.product_uid) + "." : esc(res.error)) + "</p>";
    S.tests.del = null;
    $("btnDelUndo").disabled = true;
  }

  /* ------------------------------------------------------------------ wiring */

  function wire() {
    document.querySelectorAll("[data-demo]").forEach((b) => b.addEventListener("click", () => demo(b.dataset.demo)));
    $("btnMatch").addEventListener("click", runMatch);
    $("mCode").addEventListener("keydown", (e) => { if (e.key === "Enter") runMatch(); });
    $("btnOcr").addEventListener("click", runOcr);
    $("mSample").addEventListener("change", (e) => {
      const x = S.samples[+e.target.value];
      if (x) { fillMatch(sampleToQuery(x)); runMatch(); }
    });
    $("mUpload").addEventListener("change", (e) => {
      const f = e.target.files && e.target.files[0];
      if (!f) return;
      const img = $("mPreview");
      img.src = URL.createObjectURL(f);
      img.classList.remove("hidden");
      $("btnOcr").disabled = false;
      $("ocrStatus").textContent = "Image loaded. Read it with OCR, or type what it shows.";
    });
    $("btnReverse").addEventListener("click", () => runReverse());
    $("rUid").addEventListener("keydown", (e) => { if (e.key === "Enter") runReverse(); });
    $("btnRetrain").addEventListener("click", retrain);
    $("btnScan").addEventListener("click", runScan);
    $("btnApply").addEventListener("click", applyAuto);
    ["fDecision", "fCategory"].forEach((id) => $(id).addEventListener("change", () => { S.page = 0; renderScan(); }));
    $("fSearch").addEventListener("input", () => { S.page = 0; renderIssues(); });
    $("btnPrev").addEventListener("click", () => { S.page = Math.max(0, S.page - 1); renderIssues(); });
    $("btnNext").addEventListener("click", () => { S.page++; renderIssues(); });
    $("btnLineage").addEventListener("click", loadLineage);
    $("btnInsert").addEventListener("click", testInsert);
    $("btnInsertUndo").addEventListener("click", () => deleteEvent("insert", "btnInsertUndo", "tInsertOut"));
    $("btnFake").addEventListener("click", testFake);
    $("btnFakeUndo").addEventListener("click", () => deleteEvent("fake", "btnFakeUndo", "tFakeOut"));
    $("btnMrp").addEventListener("click", testMrp);
    $("btnMrpUndo").addEventListener("click", undoMrp);
    $("btnDel").addEventListener("click", testDelete);
    $("btnDelUndo").addEventListener("click", undoDelete);

    document.addEventListener("click", (e) => {
      const t = e.target;
      if (t.closest("[data-cat]")) {
        const k = t.closest("[data-cat]").dataset.cat;
        $("fCategory").value = $("fCategory").value === k ? "" : k;
        S.page = 0;
        renderScan();
      }
      if (t.dataset && t.dataset.accept) {
        const pick = document.querySelector('[data-pick="' + t.dataset.accept + '"]');
        decide(t.dataset.accept, "accept", pick ? pick.value : null);
      }
      if (t.dataset && t.dataset.reject) decide(t.dataset.reject, "reject");
      if (t.dataset && t.dataset.quarantine) decide(t.dataset.quarantine, "quarantine");
      if (t.dataset && t.dataset.undo) undo(t.dataset.undo);
      if (t.closest("[data-reverse]")) runReverse(t.closest("[data-reverse]").dataset.reverse);
    });
  }

  async function init() {
    wire();
    try {
      await loadCatalog();
      await loadSamples();
      const b = await api("benchmark").catch(() => null);
      if (b) { S.bench = b; renderBenchmark(b); $("statModel").textContent = b.missing ? "defaults" : "trained"; }
      demo("ciplox");
      runReverse("MED-ASALI-001");
      loadLineage();
    } catch (e) {
      errorCard($("matchResult"), e);
      errorCard($("benchResult"), e);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
