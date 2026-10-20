/**
 * explorer.js (v3 - Upgraded)
 * ----------------------------
 * Interactive Controller for Asali-Nakali Database Explorer & Code Bench.
 * 
 * Major Fixes & Upgrades:
 *   1. High-Contrast Code Terminal: Bright readable syntax highlighting (no black-on-black).
 *   2. Independent State Management: Schema (Section 1), Entries (Section 2), Bench (Section 3) don't conflict.
 *   3. Bulletproof Active Button Toggling: Every button (DB tabs, Table tabs, Limit pills, Ops) updates visibly.
 *   4. Multi-Silo Conflict & Anomaly Simulation Matrix (Component B).
 *   5. Cryptographic Blockchain Audit Ledger Validator (Component C).
 *   6. Multi-PC Cluster Topology & Live Latency Probing.
 *   7. Zero Component Borders Guarantee (tactile ceramic cards with soft shadows).
 */

// ==========================================
// 1. STATE MANAGEMENT
// ==========================================
const ExplorerState = {
  // Network Endpoints
  pc1Url: localStorage.getItem("asali_pc1_endpoint") || "http://127.0.0.1:8011",
  pc2Url: localStorage.getItem("asali_pc2_endpoint") || "http://127.0.0.1:8012",

  // Section 1: Schema Details
  schemaDb: "db1",
  schemaTable: "purchase_events",
  schemaCache: {},

  // Section 2: Live Entries Browser
  entriesDb: "db1",
  entriesTable: "purchase_events",
  entriesLimit: 20,
  entriesOffset: 0,
  entriesSearch: "",
  isLoadingEntries: false,

  // Section 3: Interactive Code Bench
  benchScope: "db1",
  benchOp: "VIEW",
  benchExamples: null,
  isExecutingBench: false,

  // Section 4: Conflict Matrix
  activeConflictScenario: null,
  conflictScenarios: [],

  // Section 5: Audit Ledger Validator
  isValidatingChain: false,
};

// Fallback in-memory metadata if nodes are offline
const DB_METADATA_FALLBACK = {
  db1: {
    id: "db1",
    name: "DB1: Retail Pharmacy POS",
    node: "PC1",
    port: 8011,
    paradigm: "Polyglot: NoSQL Document Store (JSON) & SQLite",
    primary_key: "scan_code (Point of Sale Scan)",
    role: "High-velocity retail dispensary checkout scans, UPI/Cash payments, device telemetry, and duplicate scan detection",
    tables: ["purchase_events", "vendors", "scan_anomaly_log", "nosql_documents"]
  },
  db2: {
    id: "db2",
    name: "DB2: Wholesale Distributor Logistics ERP",
    node: "PC1",
    port: 8011,
    paradigm: "Relational SQL (3NF Normalized SQLite)",
    primary_key: "batch_serial & batch_id",
    role: "Middle-mile freight transit, cold-chain temperature telemetry, source warehouse to destination vendor custody routes",
    tables: ["distribution_batches", "distributors", "distributor_vendor_contracts", "return_log"]
  },
  db3: {
    id: "db3",
    name: "DB3: CDSCO Master Drug Registry",
    node: "PC2",
    port: 8012,
    paradigm: "Central Master Data Management (MDM) Relational Catalog",
    primary_key: "product_uid (Statutory Golden Record)",
    role: "Government regulatory master catalog of licensed manufacturers, GMP certifications, batch release lab QC hashes, and statutory recalls",
    tables: ["products", "manufacturers", "authorized_distributors", "batch_release_certs", "item_lifecycle"]
  },
  db4: {
    id: "db4",
    name: "DB4: Ministry of Consumer Affairs Grievance Portal",
    node: "PC2",
    port: 8012,
    paradigm: "RESTful Web Microservice + SQLite Storage",
    primary_key: "complaint_item_ref & item_ref",
    role: "Public consumer grievance complaints (INGRAM), forensic chemical assay test results, gazetted counterfeit blacklists, and public alerts",
    tables: ["complaints", "ministry_blacklist", "lab_reports", "public_alerts", "ministry_officers"]
  },
  audit: {
    id: "audit",
    name: "Immutable Cryptographic Audit Ledger",
    node: "PC2",
    port: 8012,
    paradigm: "Cryptographic SHA-256 Hash-Chained Blockchain Ledger",
    primary_key: "seq & entry_hash",
    role: "Append-only tamper-proof audit trail of every verification query, trust score, participating database witnesses, and block hash",
    tables: ["audit_log", "chain_meta"]
  }
};

// ==========================================
// 2. NETWORK CALLS & PROBING
// ==========================================
function getTargetNodeUrl(dbId) {
  if (dbId === "db1" || dbId === "db2") {
    return ExplorerState.pc1Url;
  }
  return ExplorerState.pc2Url;
}

async function fetchFromCluster(endpoint, options = {}, dbHint = "db1") {
  const primaryUrl = getTargetNodeUrl(dbHint);
  const fallbackUrl = (primaryUrl === ExplorerState.pc1Url) ? ExplorerState.pc2Url : ExplorerState.pc1Url;

  try {
    const res = await fetch(primaryUrl + endpoint, { mode: "cors", ...options });
    if (res.ok) return await res.json();
    throw new Error(`HTTP ${res.status} from ${primaryUrl}`);
  } catch (err) {
    try {
      const resFallback = await fetch(fallbackUrl + endpoint, { mode: "cors", ...options });
      if (resFallback.ok) return await resFallback.json();
    } catch (err2) {
      try {
        const resLocal = await fetch(endpoint, { ...options });
        if (resLocal.ok) return await resLocal.json();
      } catch (err3) {
        throw new Error(`Failed cluster call: ${err.message}`);
      }
    }
    throw err;
  }
}

async function pingClusterNodes() {
  const pc1Badge = document.getElementById("pc1StatusBadge");
  const pc2Badge = document.getElementById("pc2StatusBadge");
  const pc1Latency = document.getElementById("pc1Latency");
  const pc2Latency = document.getElementById("pc2Latency");
  const topoPc1Badge = document.getElementById("topoPc1Badge");
  const topoPc2Badge = document.getElementById("topoPc2Badge");

  const setBadge = (el, text, bg, color) => {
    if (!el) return;
    el.textContent = text;
    el.className = `px-3 py-1 rounded-full text-[11px] font-medium ${bg} ${color}`;
  };

  setBadge(pc1Badge, "PROBING...", "bg-[#FEF3C7]", "text-[#92400E]");
  setBadge(pc2Badge, "PROBING...", "bg-[#FEF3C7]", "text-[#92400E]");
  setBadge(topoPc1Badge, "PROBING...", "bg-[#FEF3C7]", "text-[#92400E]");
  setBadge(topoPc2Badge, "PROBING...", "bg-[#FEF3C7]", "text-[#92400E]");

  // Probe PC 1
  const t0 = performance.now();
  try {
    const res1 = await fetch(ExplorerState.pc1Url + "/health", { mode: "cors" });
    const ms1 = Math.round(performance.now() - t0);
    if (res1.ok) {
      setBadge(pc1Badge, `ONLINE (${ms1}ms)`, "bg-[#DDEBE1]", "text-[#0A291A]");
      setBadge(topoPc1Badge, `ONLINE (${ms1}ms)`, "bg-[#DDEBE1]", "text-[#0A291A]");
      if (pc1Latency) pc1Latency.textContent = `${ms1}ms RTT`;
    } else {
      throw new Error("HTTP " + res1.status);
    }
  } catch (e) {
    setBadge(pc1Badge, "STANDALONE / LAN", "bg-[#E5E5EA]", "text-black/70");
    setBadge(topoPc1Badge, "STANDALONE", "bg-[#E5E5EA]", "text-black/70");
    if (pc1Latency) pc1Latency.textContent = "Local Fallback";
  }

  // Probe PC 2
  const t1 = performance.now();
  try {
    const res2 = await fetch(ExplorerState.pc2Url + "/health", { mode: "cors" });
    const ms2 = Math.round(performance.now() - t1);
    if (res2.ok) {
      const data2 = await res2.json();
      if (data2.simulated_partition) {
        setBadge(pc2Badge, "PARTITIONED", "bg-[#FEE2E2]", "text-[#7F1D1D]");
        setBadge(topoPc2Badge, "PARTITIONED", "bg-[#FEE2E2]", "text-[#7F1D1D]");
      } else {
        setBadge(pc2Badge, `ONLINE (${ms2}ms)`, "bg-[#DDEBE1]", "text-[#0A291A]");
        setBadge(topoPc2Badge, `ONLINE (${ms2}ms)`, "bg-[#DDEBE1]", "text-[#0A291A]");
      }
      if (pc2Latency) pc2Latency.textContent = `${ms2}ms RTT`;
    } else {
      throw new Error("HTTP " + res2.status);
    }
  } catch (e) {
    setBadge(pc2Badge, "STANDALONE / LAN", "bg-[#E5E5EA]", "text-black/70");
    setBadge(topoPc2Badge, "STANDALONE", "bg-[#E5E5EA]", "text-black/70");
    if (pc2Latency) pc2Latency.textContent = "Local Fallback";
  }
}

function saveClusterEndpoints() {
  const pc1Input = document.getElementById("inputPc1Endpoint");
  const pc2Input = document.getElementById("inputPc2Endpoint");
  if (pc1Input) {
    ExplorerState.pc1Url = pc1Input.value.trim() || "http://127.0.0.1:8011";
    localStorage.setItem("asali_pc1_endpoint", ExplorerState.pc1Url);
  }
  if (pc2Input) {
    ExplorerState.pc2Url = pc2Input.value.trim() || "http://127.0.0.1:8012";
    localStorage.setItem("asali_pc2_endpoint", ExplorerState.pc2Url);
  }
  pingClusterNodes();
  loadAllSchemas();
  loadDbEntries();
}

function toggleClusterGuide() {
  const drawer = document.getElementById("clusterGuideDrawer");
  if (drawer) drawer.classList.toggle("hidden");
}

// ==========================================
// 3. SECTION 1: DATABASE-WISE SCHEMA DETAILS
// ==========================================
async function loadAllSchemas() {
  try {
    const data = await fetchFromCluster("/api/v1/explorer/schema", {}, ExplorerState.schemaDb);
    if (data && typeof data === "object") {
      ExplorerState.schemaCache = data;
    }
  } catch (err) {
    console.warn("Could not fetch remote schema, using local metadata cache", err);
    ExplorerState.schemaCache = DB_METADATA_FALLBACK;
  }
  renderSchemaSection();
}

function selectSchemaDb(dbId) {
  ExplorerState.schemaDb = dbId;
  const meta = ExplorerState.schemaCache[dbId] || DB_METADATA_FALLBACK[dbId];
  if (meta && meta.tables && meta.tables.length > 0) {
    ExplorerState.schemaTable = meta.tables[0];
  }
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

  // 1. Update DB Switcher Pills (Active turns Black, inactive turns Gray)
  document.querySelectorAll(".schema-db-pill").forEach(btn => {
    const target = btn.getAttribute("data-db");
    if (target === dbId) {
      btn.className = "schema-db-pill px-4 py-2 rounded-full text-xs font-semibold bg-black text-white shadow-sm transition-all cursor-pointer";
    } else {
      btn.className = "schema-db-pill px-4 py-2 rounded-full text-xs font-medium bg-[#F3F3F6] text-black/70 hover:bg-[#EAEAEF] hover:text-black transition-all cursor-pointer";
    }
  });

  // 2. Render DB Architecture Metadata Card
  const nodeTarget = (dbId === "db1" || dbId === "db2") ? "Node PC 1 (Port 8011)" : "Node PC 2 (Port 8012)";
  const metaContainer = document.getElementById("schemaMetaContainer");
  if (metaContainer) {
    metaContainer.innerHTML = `
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div class="flex flex-wrap items-center gap-2 mb-2">
            <span class="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-black/5 text-black/80">${nodeTarget}</span>
            <span class="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-900">${meta.paradigm}</span>
            <span class="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium bg-neutral-100 text-neutral-800">PK: ${meta.primary_key}</span>
          </div>
          <h2 class="text-xl sm:text-2xl font-semibold text-black tracking-tight">${meta.name}</h2>
          <p class="text-xs sm:text-sm text-black/60 mt-1 leading-relaxed max-w-3xl">${meta.role}</p>
        </div>
      </div>
    `;
  }

  // 3. Render Table Switcher Pills
  renderSchemaTablePillsOnly();

  // 4. Render Table Columns
  renderSchemaColumnsOnly();
}

function renderSchemaTablePillsOnly() {
  const dbId = ExplorerState.schemaDb;
  const currentTable = ExplorerState.schemaTable;
  const meta = ExplorerState.schemaCache[dbId] || DB_METADATA_FALLBACK[dbId];
  const tablePillsContainer = document.getElementById("schemaTablePills");
  if (!tablePillsContainer || !meta) return;

  const tables = meta.tables || [];
  const schemaTables = meta.schema || {};

  tablePillsContainer.innerHTML = tables.map(tbl => {
    const isSelected = (tbl === currentTable);
    const rowCount = schemaTables[tbl]?.row_count !== undefined ? `${schemaTables[tbl].row_count} rows` : "active";
    const cls = isSelected 
      ? "schema-tbl-pill px-4 py-1.5 rounded-full text-xs font-semibold bg-black text-white shadow-sm cursor-pointer transition-all"
      : "schema-tbl-pill px-4 py-1.5 rounded-full text-xs font-medium bg-[#F3F3F6] text-black/70 hover:bg-[#EAEAEF] hover:text-black cursor-pointer transition-all";
    return `
      <button onclick="selectSchemaTable('${tbl}')" data-table="${tbl}" class="${cls}">
        <span>${tbl}</span>
        <span class="ml-1.5 text-[10px] opacity-75">(${rowCount})</span>
      </button>
    `;
  }).join("");
}

function renderSchemaColumnsOnly() {
  const dbId = ExplorerState.schemaDb;
  const tbl = ExplorerState.schemaTable;
  const meta = ExplorerState.schemaCache[dbId] || DB_METADATA_FALLBACK[dbId];
  const tableData = meta?.schema?.[tbl];
  const container = document.getElementById("schemaTableBody");
  const headerInfo = document.getElementById("schemaActiveTableTitle");

  if (headerInfo) {
    const rowCnt = tableData?.row_count !== undefined ? `${tableData.row_count} records` : "Live collection";
    headerInfo.innerHTML = `Table: <strong class="font-mono text-black">${tbl}</strong> <span class="text-black/40 font-normal">(${rowCnt})</span>`;
  }

  if (!container) return;

  if (!tableData || !tableData.columns) {
    container.innerHTML = `
      <tr>
        <td colspan="4" class="px-6 py-8 text-center text-xs text-black/40">
          Loading detailed column metadata for <strong>${tbl}</strong>...
        </td>
      </tr>
    `;
    return;
  }

  container.innerHTML = tableData.columns.map(col => {
    const pkBadge = col.pk ? `<span class="ml-2 px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 text-[10px] font-semibold">PRIMARY KEY</span>` : "";
    const notNullBadge = col.notnull ? `<span class="px-2 py-0.5 rounded-full bg-black/5 text-black/70 text-[10px] font-medium">NOT NULL</span>` : "";
    return `
      <tr class="hover:bg-[#FBFBFC] transition-colors">
        <td class="px-6 py-3.5 text-xs font-mono font-semibold text-black whitespace-nowrap">
          ${col.name} ${pkBadge}
        </td>
        <td class="px-6 py-3.5 text-xs font-mono text-black/70 whitespace-nowrap">
          <span class="px-2 py-0.5 rounded bg-black/[0.04]">${col.type}</span>
        </td>
        <td class="px-6 py-3.5 text-xs text-black/60 whitespace-nowrap">
          ${notNullBadge || "<span class='text-black/30'>—</span>"}
        </td>
        <td class="px-6 py-3.5 text-xs text-black/70 leading-relaxed">
          ${col.desc || "Field identifier in repository schema"}
        </td>
      </tr>
    `;
  }).join("");
}

// 1-Click jump from Schema to Live Entries
function jumpToLiveEntries(dbId, tableName) {
  selectEntriesDb(dbId);
  selectEntriesTable(tableName);
  const el = document.getElementById("sectionLiveEntries");
  if (el) el.scrollIntoView({ behavior: "smooth" });
}

// ==========================================
// 4. SECTION 2: LIVE ENTRIES BROWSER
// ==========================================
let searchDebounceTimer = null;

function handleEntriesSearch(term) {
  ExplorerState.entriesSearch = term;
  ExplorerState.entriesOffset = 0;
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => {
    loadDbEntries();
  }, 250);
}

function selectEntriesDb(dbId) {
  ExplorerState.entriesDb = dbId;
  ExplorerState.entriesOffset = 0;
  const meta = ExplorerState.schemaCache[dbId] || DB_METADATA_FALLBACK[dbId];
  if (meta && meta.tables && meta.tables.length > 0) {
    ExplorerState.entriesTable = meta.tables[0];
  }
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
  const dbId = ExplorerState.entriesDb;
  const currentTable = ExplorerState.entriesTable;
  const meta = ExplorerState.schemaCache[dbId] || DB_METADATA_FALLBACK[dbId];
  const container = document.getElementById("entriesTablePillsContainer");
  if (!container || !meta) return;

  const tables = meta.tables || [];
  container.innerHTML = tables.map(tbl => {
    const isSelected = (tbl === currentTable);
    const cls = isSelected
      ? "entries-tbl-pill px-4 py-1.5 rounded-full text-xs font-semibold bg-black text-white shadow-sm cursor-pointer transition-all"
      : "entries-tbl-pill px-4 py-1.5 rounded-full text-xs font-medium bg-[#F3F3F6] text-black/70 hover:bg-[#EAEAEF] hover:text-black cursor-pointer transition-all";
    return `
      <button onclick="selectEntriesTable('${tbl}')" data-table="${tbl}" class="${cls}">
        ${tbl}
      </button>
    `;
  }).join("");
}

function setEntriesLimit(limitVal) {
  ExplorerState.entriesLimit = limitVal;
  ExplorerState.entriesOffset = 0;

  // Update limit pill active state: active is black, others are gray
  document.querySelectorAll(".limit-pill").forEach(btn => {
    const val = btn.getAttribute("data-limit");
    if (String(val) === String(limitVal)) {
      btn.className = "limit-pill px-3 py-1 rounded-full text-xs font-semibold bg-black text-white shadow-sm transition-all cursor-pointer";
    } else {
      btn.className = "limit-pill px-3 py-1 rounded-full text-xs font-medium bg-[#F3F3F6] text-black/70 hover:bg-[#EAEAEF] hover:text-black transition-all cursor-pointer";
    }
  });

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

  const dbId = ExplorerState.entriesDb;
  const tbl = ExplorerState.entriesTable;
  const limit = ExplorerState.entriesLimit;
  const offset = ExplorerState.entriesOffset;
  const search = ExplorerState.entriesSearch;

  const metricsText = document.getElementById("entriesMetricsText");
  const spinner = document.getElementById("entriesRefreshSpinner");
  if (spinner) spinner.classList.remove("hidden");

  // Highlight active DB pill in entries section
  document.querySelectorAll(".entries-db-pill").forEach(btn => {
    const target = btn.getAttribute("data-db");
    if (target === dbId) {
      btn.className = "entries-db-pill px-4 py-2 rounded-full text-xs font-semibold bg-black text-white shadow-sm transition-all cursor-pointer";
    } else {
      btn.className = "entries-db-pill px-4 py-2 rounded-full text-xs font-medium bg-[#F3F3F6] text-black/70 hover:bg-[#EAEAEF] hover:text-black transition-all cursor-pointer";
    }
  });

  const queryParams = new URLSearchParams({
    db: dbId,
    table: tbl,
    limit: String(limit),
    offset: String(offset),
    search: search
  });

  try {
    const data = await fetchFromCluster(`/api/v1/explorer/entries?${queryParams.toString()}`, {}, dbId);
    renderEntriesGrid(data);
    if (metricsText) {
      const nodeLabel = (dbId === "db1" || dbId === "db2") ? "Node PC1 (8011)" : "Node PC2 (8012)";
      const isAll = (limit === "all");
      const startIdx = isAll ? 1 : offset + 1;
      const endIdx = isAll ? data.total_records : Math.min(offset + (data.records?.length || 0), data.filtered_records);
      metricsText.innerHTML = `
        <span>Showing <strong>${data.records?.length ? startIdx : 0}–${endIdx}</strong> of <strong>${data.filtered_records}</strong> records</span>
        <span class="mx-2 text-black/20">•</span>
        <span>Filtered from ${data.total_records} total</span>
        <span class="mx-2 text-black/20">•</span>
        <span class="font-mono font-semibold text-emerald-800">⚡ ${data.execution_ms}ms</span>
        <span class="mx-2 text-black/20">•</span>
        <span class="text-black/50">${nodeLabel}</span>
      `;
    }
  } catch (err) {
    console.error("Error loading entries:", err);
    renderEntriesError(err.message);
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

  if (columns.length === 0 || records.length === 0) {
    thead.innerHTML = `<tr><th class="px-6 py-3 text-xs font-medium text-black/40">Status</th></tr>`;
    tbody.innerHTML = `
      <tr>
        <td class="px-6 py-12 text-center text-xs text-black/40">
          No records found matching criteria in <strong>${ExplorerState.entriesTable}</strong>.
        </td>
      </tr>
    `;
    return;
  }

  // Build Table Header
  thead.innerHTML = `
    <tr>
      <th class="px-4 py-3 text-[11px] font-semibold text-black/40 uppercase tracking-wider text-left bg-[#F7F7F9]">#</th>
      ${columns.map(c => `
        <th class="px-4 py-3 text-[11px] font-semibold text-black/60 uppercase tracking-wider text-left bg-[#F7F7F9] whitespace-nowrap">
          ${c}
        </th>
      `).join("")}
    </tr>
  `;

  // Build Table Body
  tbody.innerHTML = records.map((row, idx) => {
    const rowNum = (ExplorerState.entriesLimit === "all" ? 0 : ExplorerState.entriesOffset) + idx + 1;
    return `
      <tr class="hover:bg-[#FBFBFC] transition-colors">
        <td class="px-4 py-3 text-[11px] font-mono text-black/40 whitespace-nowrap">
          ${rowNum}
        </td>
        ${columns.map(colName => {
          const val = row[colName];
          return `<td class="px-4 py-3 text-xs text-black/80 whitespace-nowrap">${formatCellValue(colName, val)}</td>`;
        }).join("")}
      </tr>
    `;
  }).join("");
}

function formatCellValue(colName, val) {
  if (val === null || val === undefined) {
    return `<span class="text-black/30">—</span>`;
  }

  if (typeof val === "object") {
    const str = JSON.stringify(val);
    const preview = str.length > 35 ? str.substring(0, 32) + "..." : str;
    return `
      <span title='${str.replace(/'/g, "&apos;")}' class="font-mono text-[11px] px-2 py-0.5 rounded bg-black/[0.04] text-black/75 cursor-help">
        ${preview}
      </span>
    `;
  }

  const strVal = String(val);

  // Status and Flag formatting
  if (colName === "status" || colName === "verdict") {
    const lower = strVal.toLowerCase();
    if (["delivered", "genuine", "success", "asali"].includes(lower)) {
      return `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-900 uppercase">${strVal}</span>`;
    }
    if (["counterfeit", "recalled", "failed", "confirmed_counterfeit", "nakali"].includes(lower)) {
      return `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-900 uppercase">${strVal}</span>`;
    }
    if (["in_transit", "under_investigation", "suspicious", "dispatched"].includes(lower)) {
      return `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-900 uppercase">${strVal}</span>`;
    }
  }

  if (["anomaly_flag", "is_recalled", "discrepancy_noted"].includes(colName)) {
    return val == 1 
      ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-900">FLAGGED (1)</span>`
      : `<span class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-black/5 text-black/60">0</span>`;
  }

  if (["cold_chain_maintained", "active_ingredient_match", "qc_passed", "active"].includes(colName)) {
    return val == 1 
      ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-900">YES (1)</span>`
      : `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-900">NO (0)</span>`;
  }

  if (colName.includes("hash") && strVal.length > 20) {
    return `
      <span title="${strVal}" class="font-mono text-[11px] text-neutral-600 bg-neutral-100 px-1.5 py-0.5 rounded cursor-pointer select-all" onclick="navigator.clipboard.writeText('${strVal}')">
        ${strVal.substring(0, 10)}...${strVal.substring(strVal.length - 6)}
      </span>
    `;
  }

  if (colName.endsWith("_id") || colName.endsWith("_uid") || colName.endsWith("_serial") || colName.endsWith("_code") || colName.endsWith("_ref")) {
    return `<span class="font-mono text-[11px] font-semibold text-black">${strVal}</span>`;
  }

  return strVal;
}

function renderEntriesError(errMsg) {
  const tbody = document.getElementById("entriesTbody");
  if (!tbody) return;
  tbody.innerHTML = `
    <tr>
      <td colspan="10" class="px-6 py-12 text-center text-xs text-rose-700">
        Failed to fetch records: ${errMsg}. Ensure local node servers are running.
      </td>
    </tr>
  `;
}

// ==========================================
// 5. SECTION 3: INTERACTIVE CODE BENCH
// ==========================================
async function loadCodeBenchExamples() {
  try {
    const examples = await fetchFromCluster("/api/v1/explorer/examples", {}, ExplorerState.benchScope);
    ExplorerState.benchExamples = examples;
  } catch (e) {
    console.warn("Using fallback bench examples", e);
  }
  syncBenchUI();
}

function selectBenchScope(scope) {
  ExplorerState.benchScope = scope;
  if (scope === "all") {
    ExplorerState.benchOp = "FEDERATED_VIEW";
  } else {
    ExplorerState.benchOp = "VIEW";
  }
  syncBenchUI();
}

function selectBenchOp(op) {
  ExplorerState.benchOp = op;
  syncBenchUI();
}

function syncBenchUI() {
  const scope = ExplorerState.benchScope;
  const op = ExplorerState.benchOp;

  // 1. Update Scope Pills
  document.querySelectorAll(".bench-scope-pill").forEach(btn => {
    const s = btn.getAttribute("data-scope");
    if (s === scope) {
      btn.className = "bench-scope-pill px-4 py-2 rounded-full text-xs font-semibold bg-black text-white shadow-sm transition-all cursor-pointer";
    } else {
      btn.className = "bench-scope-pill px-4 py-2 rounded-full text-xs font-medium bg-[#F3F3F6] text-black/70 hover:bg-[#EAEAEF] hover:text-black transition-all cursor-pointer";
    }
  });

  // 2. Render Operation Buttons depending on scope (Per-DB vs Federated)
  const opContainer = document.getElementById("benchOpButtons");
  if (opContainer) {
    if (scope === "all") {
      const fedOps = [
        { key: "FEDERATED_VIEW", label: "Federated View (4-Silo Verification)" },
        { key: "FEDERATED_INSERT", label: "Multi-Silo Registration (DB3→DB2→DB1)" },
        { key: "FEDERATED_DELETE", label: "Quarantine & Blacklist (DB4 Hard Veto)" }
      ];
      opContainer.innerHTML = fedOps.map(item => {
        const active = (item.key === op);
        const cls = active
          ? "bench-op-btn px-4 py-2 rounded-full text-xs font-semibold bg-black text-white shadow-sm transition-all cursor-pointer"
          : "bench-op-btn px-4 py-2 rounded-full text-xs font-medium bg-[#F3F3F6] text-black/70 hover:bg-[#EAEAEF] hover:text-black transition-all cursor-pointer";
        return `<button onclick="selectBenchOp('${item.key}')" class="${cls}">${item.label}</button>`;
      }).join("");
    } else {
      const normalOps = [
        { key: "VIEW", label: "VIEW (Query)" },
        { key: "INSERT", label: "INSERT (Create)" },
        { key: "UPDATE", label: "UPDATE (Modify)" },
        { key: "DELETE", label: "DELETE (Remove)" }
      ];
      opContainer.innerHTML = normalOps.map(item => {
        const active = (item.key === op);
        const cls = active
          ? "bench-op-btn px-4 py-2 rounded-full text-xs font-semibold bg-black text-white shadow-sm transition-all cursor-pointer"
          : "bench-op-btn px-4 py-2 rounded-full text-xs font-medium bg-[#F3F3F6] text-black/70 hover:bg-[#EAEAEF] hover:text-black transition-all cursor-pointer";
        return `<button onclick="selectBenchOp('${item.key}')" class="${cls}">${item.label}</button>`;
      }).join("");
    }
  }

  // 3. Load Example Payload into Code Editor
  const exampleObj = ExplorerState.benchExamples?.[scope]?.operations?.[op];
  const editor = document.getElementById("benchCodeEditor");
  const descEl = document.getElementById("benchOperationDesc");
  const nodeIndicator = document.getElementById("benchTargetNodeIndicator");

  if (exampleObj) {
    if (descEl) descEl.textContent = exampleObj.description || "";
    if (editor) {
      editor.value = JSON.stringify(exampleObj.payload, null, 2);
    }
  } else {
    if (descEl) descEl.textContent = `Custom operation on ${scope.toUpperCase()} - ${op}`;
  }

  if (nodeIndicator) {
    if (scope === "all") {
      nodeIndicator.textContent = "Multi-PC Federated Pipeline (PC1 & PC2)";
    } else if (scope === "db1" || scope === "db2") {
      nodeIndicator.textContent = "Target: Node PC1 (Port 8011)";
    } else {
      nodeIndicator.textContent = "Target: Node PC2 (Port 8012)";
    }
  }
}

function formatBenchPayload() {
  const editor = document.getElementById("benchCodeEditor");
  if (!editor) return;
  try {
    const obj = JSON.parse(editor.value);
    editor.value = JSON.stringify(obj, null, 2);
  } catch (e) {
    alert("Invalid JSON format: " + e.message);
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
    btn.innerHTML = `
      <svg class="animate-spin w-4 h-4 mr-2 inline" viewBox="0 0 24 24" fill="none">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
      </svg>
      Executing...
    `;
    btn.disabled = true;
  }

  let payloadData = {};
  try {
    payloadData = JSON.parse(editor.value);
  } catch (e) {
    alert("JSON Syntax Error: " + e.message);
    ExplorerState.isExecutingBench = false;
    if (btn) {
      btn.textContent = "Execute Operation";
      btn.disabled = false;
    }
    return;
  }

  const scope = ExplorerState.benchScope;
  const op = ExplorerState.benchOp;
  const exampleObj = ExplorerState.benchExamples?.[scope]?.operations?.[op];
  const targetTable = exampleObj?.table || "purchase_events";

  const requestBody = {
    db_id: scope,
    operation: op,
    table: targetTable,
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

    if (terminal) {
      terminal.innerHTML = syntaxHighlightJson(res);
    }
    if (metaBar) {
      const isSuccess = res.success !== false;
      const statusBadge = isSuccess 
        ? `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-900">HTTP 200 OK</span>`
        : `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-900">FAILED</span>`;
      
      metaBar.innerHTML = `
        <div class="flex flex-wrap items-center gap-2">
          ${statusBadge}
          <span class="text-xs text-black/60">Execution: <strong>${res.execution_ms || clientMs}ms</strong></span>
          ${res.rows_affected !== undefined ? `<span class="text-xs text-black/60">• Rows Affected: <strong>${res.rows_affected}</strong></span>` : ""}
          ${res.verdict ? `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold ${res.verdict === 'ASALI' || res.verdict === 'GENUINE' ? 'bg-emerald-600 text-white' : 'bg-rose-600 text-white'}">${res.verdict} (${res.trust_score}%)</span>` : ""}
        </div>
      `;
    }

    // Refresh live entries grid if write operation succeeded
    if (["INSERT", "UPDATE", "DELETE", "FEDERATED_INSERT", "FEDERATED_DELETE"].includes(op)) {
      setTimeout(() => {
        loadDbEntries();
      }, 300);
    }

  } catch (err) {
    if (terminal) {
      terminal.innerHTML = `<span class="text-rose-400 font-semibold">Error: ${err.message}</span>`;
    }
    if (metaBar) {
      metaBar.innerHTML = `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-900">EXECUTION ERROR</span>`;
    }
  } finally {
    ExplorerState.isExecutingBench = false;
    if (btn) {
      btn.textContent = "Execute Operation";
      btn.disabled = false;
    }
  }
}

// ==========================================
// HIGH-CONTRAST TERMINAL SYNTAX HIGHLIGHTER
// ==========================================
function syntaxHighlightJson(json) {
  if (typeof json !== "string") {
    json = JSON.stringify(json, undefined, 2);
  }
  json = json.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
    let cls = "text-[#6EE7B7]"; // String: soft mint green
    if (/^"/.test(match)) {
      if (/:$/.test(match)) {
        if (/error|exception|fail/i.test(match)) {
          cls = "text-[#F87171] font-semibold"; // Error key: vibrant light red
        } else {
          cls = "text-[#F1F5F9] font-semibold"; // Normal key: bright crisp white/slate
        }
      } else {
        if (/failed|error|constraint|invalid|denied|tamper/i.test(match)) {
          cls = "text-[#FCA5A5]"; // Error description text: soft coral/pink
        }
      }
    } else if (/true|false/.test(match)) {
      cls = (match === "true") ? "text-[#34D399] font-bold" : "text-[#F87171] font-bold";
    } else if (/null/.test(match)) {
      cls = "text-[#94A3B8] italic"; // Null: slate italic
    } else {
      cls = "text-[#FCD34D] font-mono"; // Number: vibrant gold
    }
    return `<span class="${cls}">${match}</span>`;
  });
}

// ==========================================
// 6. SECTION 4: MULTI-SILO CONFLICT MATRIX
// ==========================================
async function loadConflictScenarios() {
  try {
    const data = await fetchFromCluster("/api/v1/explorer/conflict_scenarios", {}, "db3");
    if (Array.isArray(data)) {
      ExplorerState.conflictScenarios = data;
      renderConflictMatrix();
    }
  } catch (e) {
    console.warn("Using local conflict scenarios", e);
  }
}

function renderConflictMatrix() {
  const container = document.getElementById("conflictScenariosContainer");
  if (!container || !ExplorerState.conflictScenarios.length) return;

  container.innerHTML = ExplorerState.conflictScenarios.map(sc => {
    const isSelected = (ExplorerState.activeConflictScenario === sc.id);
    const cardCls = isSelected
      ? "bg-white p-5 rounded-2xl ring-2 ring-black shadow-md cursor-pointer transition-all"
      : "bg-white p-5 rounded-2xl shadow-[0_2px_8px_-1px_rgba(0,0,0,0.07),0_1px_3px_rgba(0,0,0,0.04)] hover:shadow-md cursor-pointer transition-all";

    const scoreCls = sc.expected_verdict.includes("ASALI") 
      ? "bg-emerald-100 text-emerald-900" 
      : (sc.expected_verdict.includes("NAKALI") ? "bg-rose-100 text-rose-900" : "bg-amber-100 text-amber-900");

    return `
      <div onclick="simulateConflictScenario('${sc.id}')" class="${cardCls}">
        <div class="flex items-center justify-between gap-2 mb-2">
          <span class="text-xs font-semibold text-black">${sc.title}</span>
          <span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold ${scoreCls}">${sc.expected_verdict} (${sc.expected_score})</span>
        </div>
        <p class="text-xs text-black/60 leading-relaxed mb-3">${sc.description}</p>
        
        <div class="grid grid-cols-2 gap-2 text-[11px] pt-2 border-t border-black/[0.04]">
          <div><span class="text-black/40">DB3 Mfg:</span> <span class="text-black/80">${sc.silo_breakdown.db3_mfg}</span></div>
          <div><span class="text-black/40">DB2 Logistics:</span> <span class="text-black/80">${sc.silo_breakdown.db2_logistics}</span></div>
          <div><span class="text-black/40">DB1 POS:</span> <span class="text-black/80">${sc.silo_breakdown.db1_pos}</span></div>
          <div><span class="text-black/40">DB4 Ministry:</span> <span class="text-black/80">${sc.silo_breakdown.db4_ministry}</span></div>
        </div>

        <div class="mt-4 pt-2 flex items-center justify-between">
          <span class="text-[11px] font-mono text-black/40">Serial: ${sc.item_code}</span>
          <button class="px-3 py-1 rounded-full bg-black text-white text-[11px] font-medium hover:bg-neutral-800 transition-all">
            Run Simulation &rarr;
          </button>
        </div>
      </div>
    `;
  }).join("");
}

async function simulateConflictScenario(scenarioId) {
  ExplorerState.activeConflictScenario = scenarioId;
  renderConflictMatrix();

  const scenario = ExplorerState.conflictScenarios.find(s => s.id === scenarioId);
  if (!scenario) return;

  const resultBox = document.getElementById("conflictSimulationResult");
  if (resultBox) {
    resultBox.innerHTML = `
      <div class="flex items-center gap-3">
        <svg class="animate-spin w-4 h-4 text-black" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
        <span class="text-xs text-black/70">Executing cross-silo conflict resolution for <strong>${scenario.item_code}</strong>...</span>
      </div>
    `;
  }

  try {
    const res = await fetchFromCluster("/api/v1/explorer/operation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        db_id: "all",
        operation: "FEDERATED_VIEW",
        table: "",
        data: { item_code: scenario.item_code }
      })
    }, "all");

    if (resultBox) {
      const isGenuine = (res.verdict === "ASALI" || res.verdict === "GENUINE");
      const badgeCls = isGenuine ? "bg-emerald-600 text-white" : "bg-rose-600 text-white";
      const contradictionsHtml = (res.contradictions && res.contradictions.length > 0)
        ? `<div class="mt-2 text-xs text-rose-700 font-medium">Contradictions Detected: ${res.contradictions.join(", ")}</div>`
        : `<div class="mt-2 text-xs text-emerald-700 font-medium">Zero Contradictions: All witnesses fully concordant</div>`;
      
      const vetoHtml = (res.veto_codes && res.veto_codes.length > 0)
        ? `<div class="mt-1 text-xs text-rose-900 font-bold">Hard Veto Active: ${res.veto_codes.join(", ")} (Trust score forced to 0)</div>`
        : "";

      resultBox.innerHTML = `
        <div class="space-y-2">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <span class="px-3 py-1 rounded-full text-xs font-bold ${badgeCls}">${res.verdict || "RESOLVED"}</span>
              <span class="text-sm font-semibold text-black">Trust Index: ${res.trust_score}%</span>
            </div>
            <span class="text-xs text-black/50 font-mono">Latency: ${res.execution_ms}ms</span>
          </div>
          ${contradictionsHtml}
          ${vetoHtml}
          <div class="text-[11px] text-black/60 pt-2 font-mono bg-black/[0.03] p-3 rounded-xl">
            Ledger Hash: ${res.audit_entry?.entry_hash || "Calculated and signed to audit chain"}
          </div>
        </div>
      `;
    }
  } catch (err) {
    if (resultBox) {
      resultBox.innerHTML = `<span class="text-xs text-rose-600">Simulation error: ${err.message}</span>`;
    }
  }
}

// ==========================================
// 7. SECTION 5: AUDIT LEDGER VALIDATOR
// ==========================================
async function validateAuditLedger() {
  if (ExplorerState.isValidatingChain) return;
  ExplorerState.isValidatingChain = true;

  const btn = document.getElementById("btnValidateChain");
  const resultBox = document.getElementById("auditValidationResult");

  if (btn) {
    btn.innerHTML = `
      <svg class="animate-spin w-4 h-4 mr-1.5 inline" viewBox="0 0 24 24" fill="none">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
      </svg>
      Verifying Hashes...
    `;
    btn.disabled = true;
  }

  try {
    const data = await fetchFromCluster("/api/v1/explorer/validate_chain", {}, "audit");
    if (resultBox) {
      if (data.chain_intact) {
        resultBox.innerHTML = `
          <div class="bg-emerald-50 text-emerald-950 p-4 rounded-2xl space-y-2">
            <div class="flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-emerald-600"></span>
              <span class="text-xs font-bold uppercase tracking-wider">Blockchain Integrity 100% Intact</span>
            </div>
            <p class="text-xs leading-relaxed text-emerald-900">
              Cryptographically verified <strong>${data.total_blocks} sequential blocks</strong> in ${data.execution_ms}ms. Every SHA-256 hash pointer connects without discrepancy to Genesis (<code class="font-mono">${data.genesis_hash}</code>).
            </p>
            <div class="text-[11px] font-mono opacity-80 pt-1">
              Latest Block #${data.latest_block_seq}: ${data.latest_hash?.substring(0, 32)}...
            </div>
          </div>
        `;
      } else {
        resultBox.innerHTML = `
          <div class="bg-rose-50 text-rose-950 p-4 rounded-2xl space-y-2">
            <span class="text-xs font-bold uppercase tracking-wider">Blockchain Tampering Detected!</span>
            <p class="text-xs text-rose-900">Discrepancy in ${data.tampered_count} blocks.</p>
          </div>
        `;
      }
    }
  } catch (err) {
    if (resultBox) {
      resultBox.innerHTML = `<span class="text-xs text-rose-600">Validation error: ${err.message}</span>`;
    }
  } finally {
    ExplorerState.isValidatingChain = false;
    if (btn) {
      btn.innerHTML = `
        <svg class="w-3.5 h-3.5 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
        Validate Cryptographic Hashes
      `;
      btn.disabled = false;
    }
  }
}

// ==========================================
// 8. INITIALIZATION ON DOM READY
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
  // Sync endpoint inputs
  const pc1Input = document.getElementById("inputPc1Endpoint");
  const pc2Input = document.getElementById("inputPc2Endpoint");
  if (pc1Input) pc1Input.value = ExplorerState.pc1Url;
  if (pc2Input) pc2Input.value = ExplorerState.pc2Url;

  // Initialize cluster probe
  pingClusterNodes();

  // Load schemas
  loadAllSchemas();

  // Load database entries
  renderEntriesTablePills();
  loadDbEntries();

  // Load code bench examples
  loadCodeBenchExamples();

  // Load conflict scenarios
  loadConflictScenarios();
});

// Expose globals for HTML inline event handlers
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
