/**
 * explorer.js — Asali / Nakali database explorer & code bench.
 *
 * Talks to the same node endpoints as before:
 *   GET  /health
 *   GET  /api/v1/explorer/schema
 *   GET  /api/v1/explorer/entries?db&table&limit&offset&search
 *   GET  /api/v1/explorer/examples
 *   POST /api/v1/explorer/operation
 *   GET  /api/v1/explorer/conflict_scenarios
 *   GET  /api/v1/explorer/validate_chain
 *
 * Requests go to whichever node owns the silo (DB1/DB2 → PC1, DB3/DB4/audit → PC2),
 * falling back to the sibling node and then to a same-origin path.
 */

/* ==========================================================================
   1. STATE
   ========================================================================== */
const ExplorerState = {
  // Endpoints are owned by assets/cluster.js so the verification page uses the
  // same pair; these mirror it for convenience.
  get pc1Url() { return window.Cluster.get().pc1; },
  get pc2Url() { return window.Cluster.get().pc2; },

  schemaDb: "db1",
  schemaTable: "purchase_events",
  schemaCache: {},

  entriesDb: "db1",
  entriesTable: "purchase_events",
  entriesLimit: 20,
  entriesOffset: 0,
  entriesSearch: "",
  isLoadingEntries: false,

  benchScope: "db1",
  benchOp: "VIEW",
  benchExamples: null,
  isExecutingBench: false,

  activeConflictScenario: null,
  conflictScenarios: [],

  isValidatingChain: false,

  activityDb: "all",
  isLoadingActivity: false
};

/* Used when the nodes are unreachable, so the page still explains the architecture. */
const DB_METADATA_FALLBACK = {
  db1: {
    id: "db1", name: "Retail pharmacy checkouts", node: "PC1", port: 8011,
    paradigm: "JSON documents with a SQLite mirror",
    primary_key: "scan_code",
    role: "Every checkout scan made at a pharmacy counter, with the payment method, the scanner that read it, and any duplicate scans the till flagged at the time.",
    tables: ["purchase_events", "vendors", "scan_anomaly_log", "nosql_documents"]
  },
  db2: {
    id: "db2", name: "Distributor logistics ledger", node: "PC1", port: 8011,
    paradigm: "Relational SQLite, third normal form",
    primary_key: "batch_serial / batch_id",
    role: "Shipments between warehouses and pharmacies, including the route taken, the vehicle, and the temperature readings logged along the way.",
    tables: ["distribution_batches", "distributors", "distributor_vendor_contracts", "return_log"]
  },
  db3: {
    id: "db3", name: "National drug registry", node: "PC2", port: 8012,
    paradigm: "Master catalogue",
    primary_key: "product_uid",
    role: "The authoritative record of what was legally manufactured: licensed makers, quality certificates, batch releases, and any recalls that have been gazetted.",
    tables: ["products", "manufacturers", "authorized_distributors", "batch_release_certs", "item_lifecycle"]
  },
  db4: {
    id: "db4", name: "Consumer grievance service", node: "PC2", port: 8012,
    paradigm: "REST service over SQLite",
    primary_key: "complaint_item_ref / item_ref",
    role: "Complaints filed by the public, adverse reactions reported by doctors, laboratory test results, and the statutory blacklist.",
    tables: ["complaints", "ministry_blacklist", "lab_reports", "public_alerts", "ministry_officers"]
  },
  audit: {
    id: "audit", name: "Audit ledger", node: "PC2", port: 8012,
    paradigm: "Hash-chained ledger",
    primary_key: "seq / entry_hash",
    role: "One appended block per verification, holding the verdict, the score, which silos answered, and the hash of the block before it.",
    tables: ["audit_log", "chain_meta"]
  }
};

/* ==========================================================================
   2. HELPERS
   ========================================================================== */
function esc(s) {
  return String(s === undefined || s === null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function setBadge(id, cls, text) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = cls;
  el.textContent = text;
}

/** Shared pill toggling — active pills are lime, the rest recede. */
function togglePills(selector, attr, activeValue) {
  document.querySelectorAll(selector).forEach((btn) => {
    btn.classList.toggle("is-active", String(btn.getAttribute(attr)) === String(activeValue));
  });
}

function spinnerSvg(size) {
  const s = size || 15;
  return '<svg class="spin" width="' + s + '" height="' + s + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.2-8.6" stroke-linecap="round"/></svg>';
}

/* ==========================================================================
   3. NETWORK
   ========================================================================== */
function getTargetNodeUrl(dbId) {
  if (dbId === "db1" || dbId === "db2") return ExplorerState.pc1Url;
  return ExplorerState.pc2Url;
}

/* Same routing as every other page; writes also reach the other PC's copy. */
function fetchFromCluster(endpoint, options = {}, dbHint = "db1") {
  return window.Cluster.call(endpoint, options, dbHint);
}

async function pingClusterNodes() {
  setBadge("pc1StatusBadge", "badge badge-amber", "Checking…");
  setBadge("pc2StatusBadge", "badge badge-amber", "Checking…");

  let pc1Ok = false, pc2Ok = false;

  const t0 = performance.now();
  try {
    const res1 = await fetch(ExplorerState.pc1Url + "/health", { mode: "cors" });
    if (!res1.ok) throw new Error("HTTP " + res1.status);
    const ms = Math.round(performance.now() - t0);
    pc1Ok = true;
    setBadge("pc1StatusBadge", "badge badge-green", "Online");
    setBadge("pc1Latency", "mono xsmall faint", "answered in " + ms + " ms");
  } catch (e) {
    setBadge("pc1StatusBadge", "badge", "Not reachable");
    setBadge("pc1Latency", "mono xsmall faint", "no response");
  }

  const t1 = performance.now();
  try {
    const res2 = await fetch(ExplorerState.pc2Url + "/health", { mode: "cors" });
    if (!res2.ok) throw new Error("HTTP " + res2.status);
    const ms = Math.round(performance.now() - t1);
    const body = await res2.json();
    if (body.simulated_partition) {
      setBadge("pc2StatusBadge", "badge badge-red", "Cut off (test)");
      setBadge("pc2Latency", "mono xsmall faint", "cut off by the test in Tools");
    } else {
      pc2Ok = true;
      setBadge("pc2StatusBadge", "badge badge-green", "Online");
      setBadge("pc2Latency", "mono xsmall faint", "answered in " + ms + " ms");
    }
  } catch (e) {
    setBadge("pc2StatusBadge", "badge", "Not reachable");
    setBadge("pc2Latency", "mono xsmall faint", "no response");
  }

  const nav = document.getElementById("navClusterBadge");
  if (nav) {
    if (pc1Ok && pc2Ok) {
      nav.className = "badge badge-green";
      nav.innerHTML = '<span class="dot dot-green"></span> Both PCs online';
    } else if (pc1Ok || pc2Ok) {
      nav.className = "badge badge-amber";
      nav.innerHTML = '<span class="dot dot-amber"></span> ' + (pc1Ok ? "Only PC1 online" : "Only PC2 online");
    } else {
      nav.className = "badge badge-red";
      nav.innerHTML = '<span class="dot dot-red"></span> PCs not reachable';
    }
  }
}

function saveClusterEndpoints() {
  const pc1Input = document.getElementById("inputPc1Endpoint");
  const pc2Input = document.getElementById("inputPc2Endpoint");
  window.Cluster.set(
    pc1Input ? pc1Input.value : undefined,
    pc2Input ? pc2Input.value : undefined
  );
}

/* Re-read everything whenever the connection changes, wherever it was changed
   from — this panel, or the status chip in the nav. */
function reloadForCluster() {
  const pc1Input = document.getElementById("inputPc1Endpoint");
  const pc2Input = document.getElementById("inputPc2Endpoint");
  if (pc1Input) pc1Input.value = ExplorerState.pc1Url;
  if (pc2Input) pc2Input.value = ExplorerState.pc2Url;

  pingClusterNodes();
  loadAllSchemas();
  loadDbEntries();
  loadCodeBenchExamples();
  loadConflictScenarios();
  loadActivity();
}
window.addEventListener("cluster:changed", reloadForCluster);

/**
 * Cuts the regulatory node out of the mesh so the circuit breaker can be seen
 * working. The node is told to start refusing, and if it is already unreachable
 * the UI still demonstrates the fallback path.
 */
let isSimulatingPartition = false;

async function togglePartitionSimulation() {
  isSimulatingPartition = !isSimulatingPartition;

  try {
    await fetch(ExplorerState.pc2Url + "/api/v1/partition/toggle", { method: "POST", mode: "cors" });
  } catch (e) {
    // Node already unreachable; the simulation still stands.
  }

  const btn = document.getElementById("btnTogglePartition");
  const desc = document.getElementById("partitionDescText");
  const impact = document.getElementById("partitionAuditImpact");

  if (isSimulatingPartition) {
    if (btn) { btn.textContent = "Reconnect PC2"; btn.className = "btn btn-ghost btn-sm"; }
    setBadge("circuitBreakerStateBadge", "badge badge-red", "PC2 cut off");
    setBadge("pc2StatusBadge", "badge badge-red", "Cut off (test)");
    if (desc) desc.textContent = "PC2 is cut off, so the drug registry and the ministry records cannot be " +
      "reached. Instead of failing, the system answers from the sales and shipment records it can still " +
      "see on PC1.";
    if (impact) impact.textContent = "Any result given now is marked as not confirmed by the regulator, " +
      "and its confidence is capped at 50%.";
  } else {
    if (btn) { btn.textContent = "Cut PC2 off (test)"; btn.className = "btn btn-danger btn-sm"; }
    setBadge("circuitBreakerStateBadge", "badge badge-green", "PC2 connected");
    if (desc) desc.textContent = "Both PCs are reachable, so every result uses all the databases.";
    if (impact) impact.textContent = "No confidence penalty is applied.";
    pingClusterNodes();
  }
}

function toggleClusterGuide() {
  const drawer = document.getElementById("clusterGuideDrawer");
  const chev = document.getElementById("clusterGuideChevron");
  if (!drawer) return;
  const willOpen = drawer.classList.contains("hidden");
  drawer.classList.toggle("hidden", !willOpen);
  if (chev) chev.classList.toggle("is-open", willOpen);
}

/* ==========================================================================
   4. SECTION 1 — SCHEMA
   ========================================================================== */
async function loadAllSchemas() {
  try {
    const data = await fetchFromCluster("/api/v1/explorer/schema", {}, ExplorerState.schemaDb);
    if (data && typeof data === "object") ExplorerState.schemaCache = data;
  } catch (err) {
    console.warn("Schema unavailable from nodes, using local metadata", err);
    ExplorerState.schemaCache = DB_METADATA_FALLBACK;
  }
  renderSchemaSection();
}

function selectSchemaDb(dbId) {
  ExplorerState.schemaDb = dbId;
  const meta = ExplorerState.schemaCache[dbId] || DB_METADATA_FALLBACK[dbId];
  if (meta && meta.tables && meta.tables.length) ExplorerState.schemaTable = meta.tables[0];
  renderSchemaSection();
}

function selectSchemaTable(tableName) {
  ExplorerState.schemaTable = tableName;
  renderSchemaTablePillsOnly();
  renderSchemaColumnsOnly();
}

function renderSchemaSection() {
  const dbId = ExplorerState.schemaDb;
  const meta = ExplorerState.schemaCache[dbId] || DB_METADATA_FALLBACK[dbId];
  if (!meta) return;

  togglePills(".schema-db-pill", "data-db", dbId);

  const onPc1 = (dbId === "db1" || dbId === "db2");
  const container = document.getElementById("schemaMetaContainer");
  if (container) {
    container.innerHTML =
      '<div class="row-wrap gap-2" style="margin-bottom:12px;">' +
        '<span class="badge ' + (onPc1 ? "badge-lime" : "badge-blue") + '">' + (onPc1 ? "Stored on PC1" : "Stored on PC2") + '</span>' +
        '<span class="badge">' + esc(meta.paradigm) + '</span>' +
        '<span class="badge">Key column: ' + esc(meta.primary_key) + '</span>' +
      '</div>' +
      '<h3 class="display display-sm">' + esc(meta.name) + '</h3>' +
      '<p class="small muted" style="margin-top:10px; max-width:76ch;">' + esc(meta.role) + '</p>';
  }

  renderSchemaTablePillsOnly();
  renderSchemaColumnsOnly();
}

function renderSchemaTablePillsOnly() {
  const dbId = ExplorerState.schemaDb;
  const meta = ExplorerState.schemaCache[dbId] || DB_METADATA_FALLBACK[dbId];
  const host = document.getElementById("schemaTablePills");
  if (!host || !meta) return;

  const schemaTables = meta.schema || {};
  host.innerHTML = (meta.tables || []).map((tbl) => {
    const active = (tbl === ExplorerState.schemaTable) ? " is-active" : "";
    const rows = schemaTables[tbl] && schemaTables[tbl].row_count !== undefined
      ? schemaTables[tbl].row_count + " rows" : "live";
    return '<button class="pill-btn schema-tbl-pill' + active + '" data-table="' + esc(tbl) + '" ' +
           'onclick="selectSchemaTable(\'' + esc(tbl) + '\')">' +
           '<span class="mono">' + esc(tbl) + '</span> ' +
           '<span class="xsmall" style="opacity:0.6;">' + esc(rows) + '</span></button>';
  }).join("");
}

function renderSchemaColumnsOnly() {
  const dbId = ExplorerState.schemaDb;
  const tbl = ExplorerState.schemaTable;
  const meta = ExplorerState.schemaCache[dbId] || DB_METADATA_FALLBACK[dbId];
  const tableData = meta && meta.schema ? meta.schema[tbl] : null;
  const body = document.getElementById("schemaTableBody");
  const title = document.getElementById("schemaActiveTableTitle");

  if (title) {
    const rows = tableData && tableData.row_count !== undefined ? tableData.row_count + " records" : "live collection";
    title.innerHTML = '<span class="mono">' + esc(tbl) + '</span> <span class="faint">· ' + esc(rows) + '</span>';
  }

  const jumpBtn = document.getElementById("schemaJumpBtn");
  if (jumpBtn) jumpBtn.setAttribute("onclick", "jumpToLiveEntries('" + esc(dbId) + "','" + esc(tbl) + "')");

  if (!body) return;

  if (!tableData || !tableData.columns) {
    body.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:26px;" class="faint">' +
      'The columns of <span class="mono">' + esc(tbl) + '</span> are read from a running PC. Start the PCs to see them.</td></tr>';
    return;
  }

  body.innerHTML = tableData.columns.map((col) => {
    const pk = col.pk ? ' <span class="badge badge-amber">PK</span>' : "";
    const nn = col.notnull ? '<span class="badge">not null</span>' : '<span class="faint">—</span>';
    return '<tr>' +
      '<td class="nowrap"><span class="mono em">' + esc(col.name) + '</span>' + pk + '</td>' +
      '<td class="nowrap mono xsmall">' + esc(col.type) + '</td>' +
      '<td class="nowrap">' + nn + '</td>' +
      '<td>' + esc(col.desc || "Field identifier in the repository schema") + '</td>' +
      '</tr>';
  }).join("");
}

function jumpToLiveEntries(dbId, tableName) {
  selectEntriesDb(dbId);
  selectEntriesTable(tableName);
  const el = document.getElementById("sectionLiveEntries");
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ==========================================================================
   5. SECTION 2 — LIVE ENTRIES
   ========================================================================== */
let searchDebounceTimer = null;

function handleEntriesSearch(term) {
  ExplorerState.entriesSearch = term;
  ExplorerState.entriesOffset = 0;
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(loadDbEntries, 250);
}

function selectEntriesDb(dbId) {
  ExplorerState.entriesDb = dbId;
  ExplorerState.entriesOffset = 0;
  const meta = ExplorerState.schemaCache[dbId] || DB_METADATA_FALLBACK[dbId];
  if (meta && meta.tables && meta.tables.length) ExplorerState.entriesTable = meta.tables[0];
  renderEntriesTablePills();
  loadDbEntries();
}

function selectEntriesTable(tbl) {
  ExplorerState.entriesTable = tbl;
  ExplorerState.entriesOffset = 0;
  renderEntriesTablePills();
  loadDbEntries();
}

function renderEntriesTablePills() {
  const meta = ExplorerState.schemaCache[ExplorerState.entriesDb] || DB_METADATA_FALLBACK[ExplorerState.entriesDb];
  const host = document.getElementById("entriesTablePillsContainer");
  if (!host || !meta) return;

  host.innerHTML = (meta.tables || []).map((tbl) => {
    const active = (tbl === ExplorerState.entriesTable) ? " is-active" : "";
    return '<button class="pill-btn entries-tbl-pill' + active + '" data-table="' + esc(tbl) + '" ' +
           'onclick="selectEntriesTable(\'' + esc(tbl) + '\')"><span class="mono">' + esc(tbl) + '</span></button>';
  }).join("");
}

function setEntriesLimit(limitVal) {
  ExplorerState.entriesLimit = limitVal;
  ExplorerState.entriesOffset = 0;
  togglePills(".limit-pill", "data-limit", limitVal);
  loadDbEntries();
}

function paginateEntries(delta) {
  if (ExplorerState.entriesLimit === "all") return;
  const limit = parseInt(ExplorerState.entriesLimit, 10);
  ExplorerState.entriesOffset = Math.max(0, ExplorerState.entriesOffset + (delta * limit));
  loadDbEntries();
}

async function loadDbEntries() {
  if (ExplorerState.isLoadingEntries) return;
  ExplorerState.isLoadingEntries = true;

  const { entriesDb: dbId, entriesTable: tbl, entriesLimit: limit, entriesOffset: offset, entriesSearch: search } = ExplorerState;

  const metricsText = document.getElementById("entriesMetricsText");
  const spinner = document.getElementById("entriesRefreshSpinner");
  if (spinner) spinner.classList.remove("hidden");

  togglePills(".entries-db-pill", "data-db", dbId);

  const queryParams = new URLSearchParams({
    db: dbId, table: tbl, limit: String(limit), offset: String(offset), search: search
  });

  try {
    const data = await fetchFromCluster("/api/v1/explorer/entries?" + queryParams.toString(), {}, dbId);
    renderEntriesGrid(data);
    if (metricsText) {
      const nodeLabel = (dbId === "db1" || dbId === "db2") ? "read from PC1" : "read from PC2";
      const isAll = (limit === "all");
      const count = (data.records && data.records.length) || 0;
      const startIdx = isAll ? 1 : offset + 1;
      const endIdx = isAll ? data.total_records : Math.min(offset + count, data.filtered_records);
      metricsText.innerHTML =
        '<span class="em">' + (count ? startIdx : 0) + '–' + endIdx + '</span> of ' +
        '<span class="em">' + data.filtered_records + '</span> records' +
        '<span class="faint"> · out of ' + data.total_records + ' in the table</span>' +
        '<span class="faint"> · </span><span class="mono" style="color:var(--lime);">' + data.execution_ms + ' ms</span>' +
        '<span class="faint"> · ' + nodeLabel + '</span>';
    }
  } catch (err) {
    console.error("Error loading entries:", err);
    renderEntriesError(err.message);
    if (metricsText) metricsText.innerHTML = '<span class="faint">No PC reachable</span>';
  } finally {
    ExplorerState.isLoadingEntries = false;
    if (spinner) spinner.classList.add("hidden");
  }
}

function renderEntriesGrid(data) {
  const thead = document.getElementById("entriesThead");
  const tbody = document.getElementById("entriesTbody");
  if (!thead || !tbody) return;

  const columns = data.columns || [];
  const records = data.records || [];

  if (!columns.length || !records.length) {
    thead.innerHTML = "<tr><th>Result</th></tr>";
    tbody.innerHTML = '<tr><td style="text-align:center; padding:36px;" class="faint">' +
      'No rows in <span class="mono">' + esc(ExplorerState.entriesTable) + '</span> match the search.</td></tr>';
    return;
  }

  thead.innerHTML = "<tr><th>#</th>" + columns.map(c => "<th>" + esc(c) + "</th>").join("") + "</tr>";

  tbody.innerHTML = records.map((row, idx) => {
    const rowNum = (ExplorerState.entriesLimit === "all" ? 0 : ExplorerState.entriesOffset) + idx + 1;
    return '<tr><td class="nowrap mono xsmall faint">' + rowNum + "</td>" +
      columns.map(col => '<td class="nowrap">' + formatCellValue(col, row[col]) + "</td>").join("") +
      "</tr>";
  }).join("");
}

function formatCellValue(colName, val) {
  if (val === null || val === undefined) return '<span class="faint">—</span>';

  if (typeof val === "object") {
    const str = JSON.stringify(val);
    const preview = str.length > 38 ? str.substring(0, 35) + "…" : str;
    return '<span title="' + esc(str) + '" class="mono xsmall" style="cursor:help; padding:2px 6px; border-radius:6px; background:rgba(255,255,255,0.05);">' + esc(preview) + '</span>';
  }

  const strVal = String(val);

  if (colName === "status" || colName === "verdict") {
    const lower = strVal.toLowerCase();
    if (["delivered", "genuine", "success", "asali"].includes(lower)) return '<span class="badge badge-green">' + esc(strVal) + "</span>";
    if (["counterfeit", "recalled", "failed", "confirmed_counterfeit", "nakali"].includes(lower)) return '<span class="badge badge-red">' + esc(strVal) + "</span>";
    if (["in_transit", "under_investigation", "suspicious", "dispatched"].includes(lower)) return '<span class="badge badge-amber">' + esc(strVal) + "</span>";
  }

  if (["anomaly_flag", "is_recalled", "discrepancy_noted"].includes(colName)) {
    return val == 1 ? '<span class="badge badge-red">flagged</span>' : '<span class="badge">0</span>';
  }

  if (["cold_chain_maintained", "active_ingredient_match", "qc_passed", "active"].includes(colName)) {
    return val == 1 ? '<span class="badge badge-green">yes</span>' : '<span class="badge badge-red">no</span>';
  }

  if (colName.includes("hash") && strVal.length > 20) {
    return '<span class="hash-chip" title="' + esc(strVal) + '" onclick="copyText(this, \'' + esc(strVal) + '\')">' +
           esc(strVal.substring(0, 10)) + "…" + esc(strVal.slice(-6)) + "</span>";
  }

  if (/_(id|uid|serial|code|ref)$/.test(colName)) {
    return '<span class="mono em xsmall">' + esc(strVal) + "</span>";
  }

  return esc(strVal);
}

function renderEntriesError(errMsg) {
  const tbody = document.getElementById("entriesTbody");
  const thead = document.getElementById("entriesThead");
  if (thead) thead.innerHTML = "<tr><th>Connection</th></tr>";
  if (!tbody) return;
  tbody.innerHTML = '<tr><td style="padding:34px; text-align:center;">' +
    '<p class="small" style="color:var(--red-ink);">Could not reach a PC: ' + esc(errMsg) + '</p>' +
    '<p class="xsmall faint" style="margin-top:8px;">Start the PCs with <span class="mono">python scripts/run_cluster.py --mode all</span>, ' +
    'or set their addresses in part 1 (Connection).</p></td></tr>';
}

function copyText(el, text) {
  if (!navigator.clipboard) return;
  navigator.clipboard.writeText(text).then(() => {
    const original = el.textContent;
    el.textContent = "copied ✓";
    setTimeout(() => { el.textContent = original; }, 1100);
  }).catch(() => {});
}

/* ==========================================================================
   6. SECTION 3 — CODE BENCH
   ========================================================================== */
async function loadCodeBenchExamples() {
  try {
    ExplorerState.benchExamples = await fetchFromCluster("/api/v1/explorer/examples", {}, ExplorerState.benchScope);
  } catch (e) {
    console.warn("Bench examples unavailable, using inline defaults", e);
  }
  syncBenchUI();
}

function selectBenchScope(scope) {
  ExplorerState.benchScope = scope;
  ExplorerState.benchOp = (scope === "all") ? "FEDERATED_VIEW" : "VIEW";
  syncBenchUI();
}

function selectBenchOp(op) {
  ExplorerState.benchOp = op;
  syncBenchUI();
}

function syncBenchUI() {
  const { benchScope: scope, benchOp: op } = ExplorerState;

  togglePills(".bench-scope-pill", "data-scope", scope);

  const opContainer = document.getElementById("benchOpButtons");
  if (opContainer) {
    const ops = (scope === "all")
      ? [
          { key: "FEDERATED_VIEW",   label: "Check a medicine in all 4 databases" },
          { key: "FEDERATED_INSERT", label: "Register a new medicine (DB3, DB2 and DB1)" },
          { key: "FEDERATED_DELETE", label: "Blacklist a medicine (DB4)" }
        ]
      : [
          { key: "VIEW",   label: "View rows" },
          { key: "INSERT", label: "Add a row" },
          { key: "UPDATE", label: "Change a row" },
          { key: "DELETE", label: "Delete a row" }
        ];
    opContainer.innerHTML = ops.map(item =>
      '<button class="pill-btn bench-op-btn' + (item.key === op ? " is-active" : "") + '" ' +
      'data-op="' + item.key + '" onclick="selectBenchOp(\'' + item.key + '\')">' + item.label + "</button>"
    ).join("");
  }

  const examples = ExplorerState.benchExamples;
  const exampleObj = examples && examples[scope] && examples[scope].operations
    ? examples[scope].operations[op] : null;

  const editor = document.getElementById("benchCodeEditor");
  const descEl = document.getElementById("benchOperationDesc");
  const nodeIndicator = document.getElementById("benchTargetNodeIndicator");

  if (exampleObj) {
    if (descEl) descEl.textContent = exampleObj.description || "";
    if (editor) editor.value = JSON.stringify(exampleObj.payload, null, 2);
  } else {
    if (descEl) descEl.textContent = op + " on " + scope.toUpperCase() +
      ". Start the PCs to load a ready-made example.";
    if (editor && !editor.value.trim()) editor.value = "{\n  \n}";
  }

  if (nodeIndicator) {
    nodeIndicator.textContent = (scope === "all") ? "Runs across PC1 and PC2"
      : (scope === "db1" || scope === "db2") ? "Runs on PC1"
      : "Runs on PC2";
  }
}

function formatBenchPayload() {
  const editor = document.getElementById("benchCodeEditor");
  if (!editor) return;
  try {
    editor.value = JSON.stringify(JSON.parse(editor.value), null, 2);
  } catch (e) {
    alert("Invalid JSON: " + e.message);
  }
}

function resetBenchPayload() {
  syncBenchUI();
}

async function executeCodeBench() {
  if (ExplorerState.isExecutingBench) return;
  ExplorerState.isExecutingBench = true;

  const btn = document.getElementById("btnExecuteBench");
  const terminal = document.getElementById("benchResultTerminal");
  const metaBar = document.getElementById("benchResultMeta");
  const editor = document.getElementById("benchCodeEditor");

  if (btn) {
    btn.innerHTML = spinnerSvg(15) + " Running…";
    btn.disabled = true;
  }

  let payloadData;
  try {
    payloadData = JSON.parse(editor.value);
  } catch (e) {
    alert("The record is not valid JSON: " + e.message);
    ExplorerState.isExecutingBench = false;
    if (btn) { btn.textContent = "Run it"; btn.disabled = false; }
    return;
  }

  const { benchScope: scope, benchOp: op } = ExplorerState;
  const examples = ExplorerState.benchExamples;
  const exampleObj = examples && examples[scope] && examples[scope].operations
    ? examples[scope].operations[op] : null;

  const requestBody = {
    db_id: scope,
    operation: op,
    table: (exampleObj && exampleObj.table) || "purchase_events",
    data: payloadData
  };

  const t0 = performance.now();
  try {
    const res = await fetchFromCluster("/api/v1/explorer/operation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody)
    }, scope);

    const clientMs = Math.round(performance.now() - t0);

    if (terminal) terminal.innerHTML = syntaxHighlightJson(res);

    if (metaBar) {
      const ok = res.success !== false;
      let html = '<span class="badge ' + (ok ? "badge-green" : "badge-red") + '">' + (ok ? "Done" : "Failed") + "</span>" +
                 '<span class="xsmall muted">' + (res.execution_ms || clientMs) + " ms</span>";
      if (res.rows_affected !== undefined) html += '<span class="xsmall muted">' + res.rows_affected + " row(s) changed</span>";
      const copy = res.replication;
      if (copy && copy.status !== "same_storage") {
        const tone = copy.status === "copied" ? "badge-green" : copy.status === "pending" ? "" : "badge-red";
        html += '<span class="badge ' + tone + '" title="' + esc(copy.message) + '">' +
          esc(copy.status === "copied" ? "Also saved on the other PC" : copy.status === "pending" ? "Copying to the other PC…" : "Not copied to the other PC") + "</span>";
      }
      if (res.verdict) {
        const good = (res.verdict === "ASALI" || res.verdict === "GENUINE");
        html += '<span class="badge ' + (good ? "badge-green" : "badge-red") + '">' + esc(res.verdict) + " · " + res.trust_score + "%</span>";
      }
      metaBar.innerHTML = html;
    }

    // A write may have changed what the grid is showing.
    if (["INSERT", "UPDATE", "DELETE", "FEDERATED_INSERT", "FEDERATED_DELETE"].includes(op)) {
      setTimeout(loadDbEntries, 300);
    }
    // Every operation lands in the feed, reads included.
    setTimeout(loadActivity, 320);
  } catch (err) {
    if (terminal) terminal.innerHTML = '<span class="tok-str-err">Error: ' + esc(err.message) + "</span>";
    if (metaBar) metaBar.innerHTML = '<span class="badge badge-red">Failed</span>';
  } finally {
    ExplorerState.isExecutingBench = false;
    if (btn) { btn.textContent = "Run it"; btn.disabled = false; }
  }
}

/** JSON syntax highlighting — bright keys on the dark terminal, never dark-on-dark. */
function syntaxHighlightJson(json) {
  if (typeof json !== "string") json = JSON.stringify(json, undefined, 2);
  json = json.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  return json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    (match) => {
      let cls = "tok-str";
      if (/^"/.test(match)) {
        if (/:$/.test(match)) {
          cls = /error|exception|fail/i.test(match) ? "tok-key-err" : "tok-key";
        } else if (/failed|error|constraint|invalid|denied|tamper/i.test(match)) {
          cls = "tok-str-err";
        }
      } else if (/^(true|false)$/.test(match)) {
        cls = (match === "true") ? "tok-true" : "tok-false";
      } else if (match === "null") {
        cls = "tok-null";
      } else {
        cls = "tok-num";
      }
      return '<span class="' + cls + '">' + match + "</span>";
    }
  );
}

/* ==========================================================================
   7. SECTION 4 — CONFLICT MATRIX
   ========================================================================== */
async function loadConflictScenarios() {
  try {
    const data = await fetchFromCluster("/api/v1/explorer/conflict_scenarios", {}, "db3");
    if (Array.isArray(data)) {
      ExplorerState.conflictScenarios = data;
      renderConflictMatrix();
      return;
    }
  } catch (e) {
    console.warn("Conflict scenarios unavailable from nodes", e);
  }
  const host = document.getElementById("conflictScenariosContainer");
  if (host && !ExplorerState.conflictScenarios.length) {
    host.innerHTML = '<div class="card card-inset card-pad-sm col-12"><p class="small muted">' +
      'These cases are served by PC2. Start the PCs to load and run them.</p></div>';
  }
}

function renderConflictMatrix() {
  const container = document.getElementById("conflictScenariosContainer");
  if (!container || !ExplorerState.conflictScenarios.length) return;

  container.innerHTML = ExplorerState.conflictScenarios.map((sc) => {
    const selected = (ExplorerState.activeConflictScenario === sc.id);
    const verdict = String(sc.expected_verdict || "");
    const tone = /genuine|asali/i.test(verdict) ? "green"
      : (/counterfeit|nakali/i.test(verdict) ? "red" : "amber");
    const tint = tone === "green" ? "" : (tone === "amber" ? " tint-suspicious" : " tint-nakali");
    const score = String(sc.expected_score || "").replace(/%$/, "") + "%";

    return '<div class="col-6"><div class="card' + tint + '" style="height:100%; cursor:pointer;' +
      (selected ? " box-shadow: 0 0 0 1px var(--lime), var(--shadow-card);" : "") + '" ' +
      'onclick="simulateConflictScenario(\'' + esc(sc.id) + '\')">' +
      '<div class="card-head" style="margin-bottom:10px;">' +
        '<h4 class="h-sm">' + esc(sc.title) + "</h4>" +
        '<span class="badge badge-' + tone + '">' + esc(verdict) + ", " + esc(score) + "</span>" +
      "</div>" +
      '<p class="small muted">' + esc(sc.description) + "</p>" +
      '<hr class="divider-dashed" style="margin-block:12px;">' +
      '<div class="bento" style="gap:6px;">' +
        '<div class="col-6"><p class="xsmall faint">DB3 drug registry says</p><p class="xsmall">' + esc(sc.silo_breakdown.db3_mfg) + "</p></div>" +
        '<div class="col-6"><p class="xsmall faint">DB2 shipments say</p><p class="xsmall">' + esc(sc.silo_breakdown.db2_logistics) + "</p></div>" +
        '<div class="col-6"><p class="xsmall faint">DB1 pharmacy sales say</p><p class="xsmall">' + esc(sc.silo_breakdown.db1_pos) + "</p></div>" +
        '<div class="col-6"><p class="xsmall faint">DB4 complaints say</p><p class="xsmall">' + esc(sc.silo_breakdown.db4_ministry) + "</p></div>" +
      "</div>" +
      '<div class="row-wrap gap-2 between" style="margin-top:14px;">' +
        '<span class="mono xsmall faint">' + esc(sc.item_code) + "</span>" +
        '<span class="btn btn-ghost btn-sm">Run this case →</span>' +
      "</div></div></div>";
  }).join("");
}

async function simulateConflictScenario(scenarioId) {
  ExplorerState.activeConflictScenario = scenarioId;
  renderConflictMatrix();

  const scenario = ExplorerState.conflictScenarios.find(s => s.id === scenarioId);
  if (!scenario) return;

  const resultBox = document.getElementById("conflictSimulationResult");
  if (resultBox) {
    resultBox.innerHTML = '<div class="row gap-3">' + spinnerSvg(16) +
      '<span class="small muted">Checking <span class="mono">' + esc(scenario.item_code) + "</span> in all four databases…</span></div>";
  }

  try {
    const res = await fetchFromCluster("/api/v1/explorer/operation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        db_id: "all", operation: "FEDERATED_VIEW", table: "",
        data: { item_code: scenario.item_code }
      })
    }, "all");

    if (resultBox) {
      const good = (res.verdict === "ASALI" || res.verdict === "GENUINE");
      const contradictions = (res.contradictions && res.contradictions.length)
        ? '<p class="small" style="color:var(--red-ink); margin-top:10px;">The databases disagreed on: ' + esc(res.contradictions.join(", ")) + "</p>"
        : '<p class="small" style="color:var(--green-ink); margin-top:10px;">Nothing to settle: all four databases agree.</p>';
      const veto = (res.veto_codes && res.veto_codes.length)
        ? '<p class="small" style="color:var(--red-ink); margin-top:6px; font-weight:600;">Hard stop: ' + esc(res.veto_codes.join(", ")) + " (trust score forced to 0).</p>"
        : "";

      resultBox.innerHTML =
        '<div class="row-wrap gap-3 between">' +
          '<div class="row gap-3">' +
            '<span class="badge badge-' + (good ? "green" : "red") + '">' + esc(res.verdict || "resolved") + "</span>" +
            '<span class="h-md">Trust score ' + esc(res.trust_score) + "%</span>" +
          "</div>" +
          '<span class="mono xsmall faint">' + esc(res.execution_ms) + " ms</span>" +
        "</div>" + contradictions + veto +
        '<p class="mono xsmall faint" style="margin-top:12px; word-break:break-all;">Saved in the audit ledger: ' +
          esc((res.audit_entry && res.audit_entry.entry_hash) || "yes") + "</p>";
    }
  } catch (err) {
    if (resultBox) resultBox.innerHTML = '<p class="small" style="color:var(--red-ink);">Could not run this case: ' + esc(err.message) + "</p>";
  }
}

/* ==========================================================================
   8. SECTION 5 — AUDIT LEDGER
   ========================================================================== */
async function validateAuditLedger() {
  if (ExplorerState.isValidatingChain) return;
  ExplorerState.isValidatingChain = true;

  const btn = document.getElementById("btnValidateChain");
  const resultBox = document.getElementById("auditValidationResult");

  if (btn) {
    btn.innerHTML = spinnerSvg(15) + " Checking…";
    btn.disabled = true;
  }

  try {
    const data = await fetchFromCluster("/api/v1/explorer/validate_chain", {}, "audit");
    if (resultBox) {
      if (data.chain_intact) {
        resultBox.innerHTML =
          '<div class="card card-inset card-pad-sm">' +
            '<div class="row gap-3" style="margin-bottom:10px;">' +
              '<span class="dot dot-green"></span>' +
              '<span class="eyebrow" style="color:var(--green-ink);">No tampering found</span>' +
            "</div>" +
            '<p class="small muted">Checked <span class="em">' + esc(data.total_blocks) + " blocks</span> in " +
              esc(data.execution_ms) + " ms. Every block's SHA-256 fingerprint matches, all the way back to the first block " +
              '<span class="mono xsmall">' + esc(data.genesis_hash) + "</span>.</p>" +
            '<p class="mono xsmall faint" style="margin-top:10px; word-break:break-all;">Latest block #' +
              esc(data.latest_block_seq) + " · " + esc((data.latest_hash || "").substring(0, 40)) + "…</p>" +
          "</div>";
      } else {
        resultBox.innerHTML =
          '<div class="card card-inset card-pad-sm tint-nakali">' +
            '<div class="row gap-3" style="margin-bottom:10px;">' +
              '<span class="dot dot-red"></span>' +
              '<span class="eyebrow" style="color:var(--red-ink);">Tampering detected</span>' +
            "</div>" +
            '<p class="small muted">The fingerprints do not match in <span class="em">' + esc(data.tampered_count) +
              " block(s)</span>: something was edited, so the ledger can no longer be trusted as evidence.</p>" +
          "</div>";
      }
    }
  } catch (err) {
    if (resultBox) {
      resultBox.innerHTML = '<div class="card card-inset card-pad-sm"><p class="small" style="color:var(--red-ink);">' +
        "Could not check the ledger: " + esc(err.message) + '</p><p class="xsmall faint" style="margin-top:6px;">' +
        "The audit ledger is stored on PC2. Start the PCs to check it.</p></div>";
    }
  } finally {
    ExplorerState.isValidatingChain = false;
    if (btn) {
      btn.innerHTML = "Check every hash";
      btn.disabled = false;
    }
  }
}


/* ==========================================================================
   8. ACTIVITY LOG
   --------------------------------------------------------------------------
   Each node keeps its own record of what was done to the silos it serves, so
   the feed asks both and merges by timestamp. Asking only the owning node would
   miss work the fallback path routed elsewhere.
   ========================================================================== */
function selectActivityDb(dbId) {
  ExplorerState.activityDb = dbId;
  togglePills(".activity-db-pill", "data-db", dbId);
  loadActivity();
}

const ACTION_TONE = {
  SELECT: "", SEARCH: "", SCHEMA: "",
  VIEW: "", FEDERATED_VIEW: "blue",
  INSERT: "green", FEDERATED_INSERT: "green",
  UPDATE: "amber",
  DELETE: "red", FEDERATED_DELETE: "red",
  VALIDATE: "blue", CLEAR: "amber"
};

const ACTION_LABEL = {
  SELECT: "Browsed rows", SEARCH: "Searched", SCHEMA: "Read schema",
  VIEW: "Queried", INSERT: "Inserted", UPDATE: "Updated", DELETE: "Deleted",
  FEDERATED_VIEW: "Checked in all databases",
  FEDERATED_INSERT: "Registered in all databases",
  FEDERATED_DELETE: "Blacklisted",
  VALIDATE: "Checked the chain", CLEAR: "Cleared the log"
};

const SILO_LABEL = {
  db1: "DB1 · Pharmacy sales", db2: "DB2 · Shipments", db3: "DB3 · Drug registry",
  db4: "DB4 · Complaints", audit: "Audit ledger", all: "All databases"
};

function whenText(iso) {
  if (!iso) return "—";
  const then = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  if (isNaN(then)) return iso;
  const secs = Math.floor((Date.now() - then.getTime()) / 1000);
  if (secs < 5) return "just now";
  if (secs < 60) return secs + "s ago";
  if (secs < 3600) return Math.floor(secs / 60) + "m ago";
  if (secs < 86400) return Math.floor(secs / 3600) + "h ago";
  return then.toLocaleDateString();
}

async function loadActivity() {
  if (ExplorerState.isLoadingActivity) return;
  ExplorerState.isLoadingActivity = true;

  const db = ExplorerState.activityDb;
  const query = "/api/v1/explorer/activity?db=" + encodeURIComponent(db) + "&limit=80";
  const urls = window.Cluster.get();

  async function fromNode(base) {
    try {
      const res = await fetch(base + query, { mode: "cors" });
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  try {
    const [a, b] = await Promise.all([fromNode(urls.pc1), fromNode(urls.pc2)]);
    const reachable = [a, b].filter(Boolean);

    let entries = [];
    let total = 0;
    const counts = {};
    reachable.forEach((r) => {
      entries = entries.concat(r.entries || []);
      total += r.total_entries || 0;
      Object.keys(r.counts_by_db || {}).forEach((k) => {
        counts[k] = (counts[k] || 0) + r.counts_by_db[k];
      });
    });

    entries.sort((x, y) => String(y.ts).localeCompare(String(x.ts)));
    renderActivity(entries.slice(0, 80), counts, total, reachable.length);
  } finally {
    ExplorerState.isLoadingActivity = false;
  }
}

function renderActivity(entries, counts, total, nodesAnswering) {
  const tbody = document.getElementById("activityTbody");
  const metrics = document.getElementById("activityMetrics");
  const countHost = document.getElementById("activityCounts");

  if (countHost) {
    const order = ["db1", "db2", "db3", "db4", "audit"];
    countHost.innerHTML = order.map((k) =>
      '<div class="col-3"><div class="card card-inset card-pad-sm">' +
        '<p class="eyebrow">' + SILO_LABEL[k] + "</p>" +
        '<p class="stat-num" style="margin-top:4px;">' + (counts[k] || 0) + "</p>" +
      "</div></div>"
    ).join("");
  }

  if (!tbody) return;

  if (!nodesAnswering) {
    tbody.innerHTML = '<tr><td colspan="8" style="padding:30px; text-align:center;">' +
      '<p class="small" style="color:var(--red-ink);">No PC answered.</p>' +
      '<p class="xsmall faint" style="margin-top:6px;">Start the PCs, or change their addresses by clicking the status badge at the top.</p></td></tr>';
    if (metrics) metrics.textContent = "—";
    return;
  }

  if (!entries.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="padding:30px; text-align:center;" class="faint">' +
      "Nothing recorded yet for this database. Browse a table or run an operation and it will appear here.</td></tr>";
    if (metrics) metrics.textContent = "0 entries";
    return;
  }

  tbody.innerHTML = entries.map((e) => {
    const tone = ACTION_TONE[e.action] || "";
    const failed = e.ok === 0 || e.ok === false;
    const label = ACTION_LABEL[e.action] || e.action;
    const badgeCls = "badge " + (failed ? "badge-red" : (tone ? "badge-" + tone : ""));

    return "<tr>" +
      '<td class="nowrap xsmall faint" title="' + esc(e.ts) + '">' + esc(whenText(e.ts)) + "</td>" +
      '<td class="nowrap"><span class="xsmall">' + esc(SILO_LABEL[e.db_id] || e.db_id) + "</span></td>" +
      '<td class="nowrap"><span class="' + badgeCls + '">' + esc(label) + "</span></td>" +
      '<td class="nowrap mono xsmall">' + (e.target ? esc(e.target) : '<span class="faint">—</span>') + "</td>" +
      "<td>" + esc(e.summary || "") + "</td>" +
      '<td class="nowrap mono xsmall">' + (e.rows || 0) + "</td>" +
      '<td class="nowrap mono xsmall faint">' + (e.ms || 0) + " ms</td>" +
      '<td class="nowrap xsmall faint">' + esc(String(e.node || "").replace(/_.*$/, "")) + "</td>" +
    "</tr>";
  }).join("");

  if (metrics) {
    metrics.innerHTML = "Showing <span class=\"em\">" + entries.length + "</span> of " +
      "<span class=\"em\">" + total + "</span> recorded operations" +
      (nodesAnswering < 2 ? ' <span class="faint">· only one PC answered</span>' : "");
  }
}


/**
 * Wipes the feed on both nodes. This cannot be undone, so it asks first, and
 * the clear itself is recorded — an empty table with one "history cleared"
 * entry is honest in a way a silently empty table is not.
 */
async function clearActivity() {
  const ok = window.confirm(
    "Clear the activity log?\n\n" +
    "This erases the record of every operation on both PCs and cannot be undone. " +
    "The databases themselves are not touched."
  );
  if (!ok) return;

  const btn = document.getElementById("btnClearActivity");
  if (btn) { btn.disabled = true; btn.textContent = "Clearing…"; }

  const urls = window.Cluster.get();
  const wipe = (base) =>
    fetch(base + "/api/v1/explorer/activity/clear", { method: "POST", mode: "cors" })
      .then((r) => r.ok)
      .catch(() => false);

  try {
    // Both nodes share the file on one machine and keep separate files on two,
    // so ask each of them.
    await Promise.all([wipe(urls.pc1), wipe(urls.pc2)]);
    await loadActivity();
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Clear log"; }
  }
}

/* ==========================================================================
   9. INIT
   ========================================================================== */
document.addEventListener("DOMContentLoaded", () => {
  const pc1Input = document.getElementById("inputPc1Endpoint");
  const pc2Input = document.getElementById("inputPc2Endpoint");
  if (pc1Input) pc1Input.value = ExplorerState.pc1Url;
  if (pc2Input) pc2Input.value = ExplorerState.pc2Url;

  const searchInput = document.getElementById("entriesSearchInput");
  if (searchInput) searchInput.addEventListener("input", (e) => handleEntriesSearch(e.target.value));

  pingClusterNodes();
  loadAllSchemas();
  renderEntriesTablePills();
  loadDbEntries();
  loadCodeBenchExamples();
  loadConflictScenarios();
  loadActivity();
});

/* Exports for inline handlers */
window.pingClusterNodes = pingClusterNodes;
window.saveClusterEndpoints = saveClusterEndpoints;
window.toggleClusterGuide = toggleClusterGuide;
window.selectSchemaDb = selectSchemaDb;
window.selectSchemaTable = selectSchemaTable;
window.jumpToLiveEntries = jumpToLiveEntries;
window.selectEntriesDb = selectEntriesDb;
window.selectEntriesTable = selectEntriesTable;
window.setEntriesLimit = setEntriesLimit;
window.handleEntriesSearch = handleEntriesSearch;
window.paginateEntries = paginateEntries;
window.loadDbEntries = loadDbEntries;
window.selectBenchScope = selectBenchScope;
window.selectBenchOp = selectBenchOp;
window.formatBenchPayload = formatBenchPayload;
window.resetBenchPayload = resetBenchPayload;
window.executeCodeBench = executeCodeBench;
window.simulateConflictScenario = simulateConflictScenario;
window.validateAuditLedger = validateAuditLedger;
window.selectActivityDb = selectActivityDb;
window.loadActivity = loadActivity;
window.clearActivity = clearActivity;
window.togglePartitionSimulation = togglePartitionSimulation;
window.copyText = copyText;
