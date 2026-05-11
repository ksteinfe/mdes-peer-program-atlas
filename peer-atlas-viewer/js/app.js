const $ = (sel) => document.querySelector(sel);

const LS_LAST_CORPUS_LABEL = "peer-atlas-last-corpus-label";
const LS_LAST_CORPUS_PATH = "peer-atlas-last-corpus-path";
const IDB_NAME = "peer-atlas-viewer";
const IDB_STORE = "fs-handles";
const IDB_CORPUS_KEY = "corpusFile";

/** @type {{ corpus_metadata?: object, programs: object[] } | null} */
let corpus = null;
/** @type {Record<string, unknown>} */
let categories = {};
/** @type {string | null} */
let detailProgramId = null;
/** @type {object | null} */
let editBaseline = null;
let editMode = false;

/** @type {{ key: string, dir: 'asc' | 'desc' }} */
let sortState = { key: "institution", dir: "asc" };

/**
 * @typedef {{
 *   degrees: Set<string>,
 *   hostModels: Set<string>,
 *   tags: Set<string>,
 *   semMin: number | null,
 *   semMax: number | null,
 * }} FilterState
 */

/** @type {FilterState} */
const filters = {
  degrees: new Set(),
  hostModels: new Set(),
  tags: new Set(),
  semMin: null,
  semMax: null,
};

/** When true, filter checkboxes show "(n/total)" counts for each option. */
let filterPanelShowCounts = false;

const SORT_KEYS = ["institution", "program", "degree", "berkeleySem", "hostModel", "tags"];

/** Max characters for course title in sample list (ellipsis if longer). */
const COURSE_TITLE_LIST_MAX = 52;

/** Max characters for course dialog heading `course_id - course_title` (ellipsis if longer). */
const COURSE_POPOVER_TITLE_MAX = 78;

/** Dot-paths merge-patch uses (popover fields only). */
const EDITABLE_PATHS = [
  "identity.institution_name",
  "identity.program_name",
  "identity.credential_name",
  "identity.degree_type",
  "identity.host_academic_units",
  "identity.host_academic_model",
  "identity.location_label",
  "identity.first_degree_granted_year",
  "identity.cip_code",
  "identity.ipeds_unitid",
  "positioning.positioning_summary",
  "positioning.positioning_tags",
  "duration.length_in_berkeley_semesters",
  "duration.duration_category",
  "duration.duration_summary",
  "degree_cost.base_currency",
  "degree_cost.exchange_rate_to_usd",
  "degree_cost.comparison_cost_usd",
  "degree_cost.cost_base_currency",
  "degree_cost.cost_basis",
  "degree_cost.comparison_cost_method",
  "curriculum.unit_system",
  "curriculum.sequencedness",
  "curriculum.curriculum_summary",
  "curriculum.offers_specialization",
  "curriculum.electives.summary",
  "historical",
];

function setStatus(msg) {
  const el = $("#status");
  if (el) el.textContent = msg;
}

function setCountLine(visible, total) {
  const el = $("#count-line");
  if (el) el.textContent = `Showing ${visible} of ${total} programs`;
}

function deepClone(o) {
  return JSON.parse(JSON.stringify(o));
}

function deepEqual(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

/**
 * @param {unknown} data
 */
function normalizeCorpus(data) {
  if (!data || typeof data !== "object") throw new Error("Invalid JSON root");
  const root = /** @type {Record<string, unknown>} */ (data);
  if (!Array.isArray(root.programs)) throw new Error("Expected top-level 'programs' array");
  for (const p of root.programs) {
    if (p && typeof p === "object" && !Array.isArray(p)) {
      const pr = /** @type {Record<string, unknown>} */ (p);
      delete pr.llm_rationales;
      delete pr.sources;
    }
  }
  return /** @type {{ corpus_metadata?: object, programs: object[] }} */ (data);
}

function supportsFilePicker() {
  return typeof window.showOpenFilePicker === "function";
}

function rememberCorpusLabel(file) {
  const name = file?.name || "corpus.json";
  const path = typeof file?.path === "string" && file.path.length > 0 ? file.path : "";
  try {
    localStorage.setItem(LS_LAST_CORPUS_LABEL, name);
    if (path) localStorage.setItem(LS_LAST_CORPUS_PATH, path);
    else localStorage.removeItem(LS_LAST_CORPUS_PATH);
  } catch {
    /* ignore */
  }
}

function openIdb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NAME, 1);
    req.onerror = () => reject(req.error);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(IDB_STORE)) db.createObjectStore(IDB_STORE);
    };
    req.onsuccess = () => resolve(req.result);
  });
}

/** @param {IDBDatabase} db */
function idbClose(db) {
  try {
    db.close();
  } catch {
    /* ignore */
  }
}

/** @param {string} key @param {unknown} value */
async function idbPut(key, value) {
  const db = await openIdb();
  try {
    await new Promise((resolve, reject) => {
      const tx = db.transaction(IDB_STORE, "readwrite");
      tx.oncomplete = () => resolve(undefined);
      tx.onerror = () => reject(tx.error);
      tx.objectStore(IDB_STORE).put(value, key);
    });
  } finally {
    idbClose(db);
  }
}

/** @param {string} key */
async function idbGet(key) {
  const db = await openIdb();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(IDB_STORE, "readonly");
      tx.onerror = () => reject(tx.error);
      const r = tx.objectStore(IDB_STORE).get(key);
      r.onsuccess = () => resolve(r.result);
    });
  } finally {
    idbClose(db);
  }
}

/** @param {string} key */
async function idbDelete(key) {
  const db = await openIdb();
  try {
    await new Promise((resolve, reject) => {
      const tx = db.transaction(IDB_STORE, "readwrite");
      tx.oncomplete = () => resolve(undefined);
      tx.onerror = () => reject(tx.error);
      tx.objectStore(IDB_STORE).delete(key);
    });
  } finally {
    idbClose(db);
  }
}

async function clearPersistedCorpus() {
  try {
    localStorage.removeItem(LS_LAST_CORPUS_LABEL);
    localStorage.removeItem(LS_LAST_CORPUS_PATH);
  } catch {
    /* ignore */
  }
  try {
    await idbDelete(IDB_CORPUS_KEY);
  } catch {
    /* ignore */
  }
}

/**
 * @param {File} file
 * @param {FileSystemFileHandle | null} handle
 * @param {{ reload?: boolean }} [opts]
 */
async function applyLoadedCorpus(file, handle, opts = {}) {
  const text = await file.text();
  const data = JSON.parse(text);
  corpus = normalizeCorpus(data);
  detailProgramId = null;
  editBaseline = null;
  editMode = false;
  clearFilterSets();
  rememberCorpusLabel(file);
  if (handle && supportsFilePicker()) {
    try {
      await idbPut(IDB_CORPUS_KEY, handle);
    } catch (e) {
      console.warn("Could not persist file handle:", e);
    }
  }
  let savedPath = "";
  try {
    savedPath = localStorage.getItem(LS_LAST_CORPUS_PATH) || "";
  } catch {
    savedPath = "";
  }
  const pathFromFile =
    typeof file.path === "string" && file.path.length > 0 && !file.path.includes("fakepath")
      ? file.path
      : "";
  const label =
    opts.reload && savedPath ? savedPath : pathFromFile || file.name || "corpus";
  const verb = opts.reload ? "Reloaded" : "Loaded";
  setStatus(`${verb} ${label} (${corpus.programs.length} programs).`);
  renderTable();
}

/**
 * @param {File} file
 * @param {FileSystemFileHandle | null} handle
 */
async function ingestCorpusFile(file, handle) {
  try {
    await applyLoadedCorpus(file, handle, { reload: false });
  } catch (err) {
    corpus = null;
    detailProgramId = null;
    setStatus("Invalid or unexpected JSON.");
    console.error(err);
    renderTable();
  }
}

/**
 * @param {FileSystemFileHandle} handle
 * @returns {Promise<'ok' | 'denied' | 'error'>}
 */
async function restoreFromHandle(handle) {
  if (!handle || typeof handle.getFile !== "function") return "error";
  if (handle.queryPermission) {
    const perm = await handle.queryPermission({ mode: "read" });
    if (perm !== "granted") return "denied";
  }
  const file = await handle.getFile();
  try {
    await applyLoadedCorpus(file, handle, { reload: true });
    return "ok";
  } catch (e) {
    console.error(e);
    return "error";
  }
}

async function tryRestorePersistedCorpus() {
  if (corpus) return true;
  let handle = null;
  try {
    handle = await idbGet(IDB_CORPUS_KEY);
  } catch (e) {
    console.warn(e);
    return false;
  }
  if (!handle) return false;
  const result = await restoreFromHandle(handle);
  if (result === "ok") return true;
  if (result === "error") {
    try {
      await idbDelete(IDB_CORPUS_KEY);
    } catch {
      /* ignore */
    }
    setStatus("Saved corpus could not be read. Use Load corpus… to pick a valid JSON file.");
    return false;
  }
  setStatus("Saved corpus needs permission after refresh. Click Load corpus… and pick the same file once.");
  return false;
}

async function openCorpusPicker() {
  if (supportsFilePicker()) {
    try {
      /** @type {OpenFilePickerOptions} */
      const opts = {
        multiple: false,
        excludeAcceptAllOption: false,
        types: [{ description: "JSON", accept: { "application/json": [".json"] } }],
      };
      const handles = await window.showOpenFilePicker(opts);
      const handle = handles[0];
      const file = await handle.getFile();
      await ingestCorpusFile(file, handle);
      return;
    } catch (e) {
      if (e && typeof e === "object" && e.name === "AbortError") return;
      console.warn("showOpenFilePicker failed, falling back to file input:", e);
    }
  }
  const input = $("#file-corpus");
  if (input instanceof HTMLInputElement) input.click();
}

function clearFilterSets() {
  filters.degrees.clear();
  filters.hostModels.clear();
  filters.tags.clear();
  filters.semMin = null;
  filters.semMax = null;
}

/**
 * Add this positioning tag to the active tag filters (does not clear degree, host, or semester filters).
 * Multiple tag filters combine with AND (program must include every selected tag).
 * @param {string} tagId
 */
function applyTagFilter(tagId) {
  if (!tagId) return;
  filters.tags.add(tagId);
  renderTable();
  const lab = labelForId("positioning_tags", tagId) || tagId;
  const n = filters.tags.size;
  setStatus(
    n > 1
      ? `Added tag filter: ${lab} (${n} tags required; programs must match all). Use Filter programs to adjust or clear.`
      : `Added tag filter: ${lab}. Use Filter programs to adjust or clear.`
  );
}

/**
 * @param {string} catKey e.g. 'host_academic_models'
 * @param {string} id
 */
function labelForId(catKey, id) {
  const block = categories[catKey];
  const items = block && typeof block === "object" && Array.isArray(block.items) ? block.items : [];
  const row = items.find((x) => x && typeof x === "object" && x.id === id);
  return row && typeof row.label === "string" ? row.label : id;
}

/** Main program table + footer summaries only; use {@link labelForId} for filters, detail, etc. */
function hostModelShortLabel(id) {
  if (!id) return "";
  const block = categories.host_academic_models;
  const items = block && typeof block === "object" && Array.isArray(block.items) ? block.items : [];
  const row = items.find((x) => x && typeof x === "object" && x.id === id);
  if (!row) return id;
  if (typeof row.short_label === "string" && row.short_label.trim()) return row.short_label.trim();
  return typeof row.label === "string" ? row.label : id;
}

/**
 * @param {object} p
 */
function rowView(p) {
  const ident = p.identity ?? {};
  const pos = p.positioning ?? {};
  const dur = p.duration ?? {};
  const tags = Array.isArray(pos.positioning_tags)
    ? pos.positioning_tags.filter((t) => t != null && String(t).trim())
    : [];
  const hostId = typeof ident.host_academic_model === "string" ? ident.host_academic_model : "";
  const berk = dur.length_in_berkeley_semesters;
  return {
    program: p,
    institution: String(ident.institution_name ?? ""),
    programName: String(ident.program_name ?? ""),
    degree: String(ident.degree_type ?? ""),
    berkeleySem: berk === null || berk === undefined || berk === "" ? null : Number(berk),
    hostModel: hostId,
    hostModelLabel: hostModelShortLabel(hostId) || hostId,
    tags,
    tagsSortKey: tags.slice().sort().join(", "),
  };
}

/**
 * @param {object} p
 */
function passesFilters(p) {
  const v = rowView(p);
  if (filters.degrees.size && !filters.degrees.has(v.degree)) return false;
  if (filters.hostModels.size && !filters.hostModels.has(v.hostModel)) return false;
  if (filters.tags.size) {
    for (const t of filters.tags) {
      if (!v.tags.includes(t)) return false;
    }
  }
  if (filters.semMin != null && Number.isFinite(filters.semMin)) {
    if (v.berkeleySem == null || !Number.isFinite(v.berkeleySem) || v.berkeleySem < filters.semMin)
      return false;
  }
  if (filters.semMax != null && Number.isFinite(filters.semMax)) {
    if (v.berkeleySem == null || !Number.isFinite(v.berkeleySem) || v.berkeleySem > filters.semMax)
      return false;
  }
  return true;
}

/**
 * @param {ReturnType<typeof rowView>} a
 * @param {ReturnType<typeof rowView>} b
 */
/**
 * @param {ReturnType<typeof rowView>} v
 * @param {string} k
 */
function sortValueFor(v, k) {
  if (k === "program") return v.programName;
  return /** @type {string | number | null} */ (v[k]);
}

function compareRows(a, b) {
  const dir = sortState.dir === "desc" ? -1 : 1;
  const k = sortState.key;
  let cmp = 0;
  if (k === "berkeleySem") {
    const na = a.berkeleySem;
    const nb = b.berkeleySem;
    if (na == null && nb == null) cmp = 0;
    else if (na == null) cmp = 1;
    else if (nb == null) cmp = -1;
    else cmp = na - nb;
  } else if (k === "tags") {
    cmp = a.tagsSortKey.localeCompare(b.tagsSortKey, undefined, { sensitivity: "base" });
  } else {
    const sa = String(sortValueFor(a, k) ?? "");
    const sb = String(sortValueFor(b, k) ?? "");
    cmp = sa.localeCompare(sb, undefined, { sensitivity: "base" });
  }
  if (cmp !== 0) return cmp * dir;
  return a.institution.localeCompare(b.institution, undefined, { sensitivity: "base" });
}

function getFilteredPrograms() {
  if (!corpus) return [];
  return corpus.programs.filter(passesFilters);
}

/**
 * Buckets entries with count &lt; 5% of row count into one "Other" row; sorts by count descending.
 * @param {{ label: string, count: number }[]} entries
 */
function summarizeWithOtherBucket(entries, rowCount) {
  const threshold = rowCount * 0.05;
  const main = [];
  let otherTotal = 0;
  /** @type {{ label: string, count: number }[]} */
  const small = [];
  for (const e of entries) {
    if (e.count < threshold) {
      otherTotal += e.count;
      small.push(e);
    } else main.push({ label: e.label, count: e.count });
  }
  const out = [...main];
  if (otherTotal > 0) {
    small.sort((a, b) => b.count - a.count);
    const detail = small.map((s) => `${s.label} (${s.count})`).join("; ");
    out.push({ label: "Other", count: otherTotal, detail });
  }
  out.sort((a, b) => b.count - a.count);
  return out;
}

const SUMMARY_TABLE_COL_CLASSES = ["col-inst", "col-program", "col-degree", "col-sem", "col-host", "col-tags"];

/**
 * @param {{ label: string, count: number, detail?: string }[]} rows
 * @param {{ tags?: boolean }} [opts]
 */
function buildSummaryList(rows, opts = {}) {
  const wrap = document.createElement("div");
  wrap.className = opts.tags ? "column-summary-block column-summary-block--tags" : "column-summary-block";
  const ul = document.createElement("ul");
  ul.className = "column-summary-list";
  if (!rows.length) {
    const li = document.createElement("li");
    li.textContent = "—";
    ul.appendChild(li);
  } else {
    for (const r of rows) {
      const li = document.createElement("li");
      li.textContent = `${r.label} (${r.count})`;
      if (r.detail) li.title = r.detail;
      ul.appendChild(li);
    }
  }
  wrap.appendChild(ul);
  return wrap;
}

function buildSummaryTableRow(cells) {
  const table = document.createElement("table");
  table.className = "program-table column-summaries-table";
  const cg = document.createElement("colgroup");
  for (const cls of SUMMARY_TABLE_COL_CLASSES) {
    const col = document.createElement("col");
    col.className = cls;
    cg.appendChild(col);
  }
  table.appendChild(cg);
  const tbody = document.createElement("tbody");
  const tr = document.createElement("tr");
  tr.className = "column-summary-row";
  for (const cell of cells) {
    const td = document.createElement("td");
    td.className = "column-summary-td";
    if (cell) td.appendChild(cell);
    tr.appendChild(td);
  }
  tbody.appendChild(tr);
  table.appendChild(tbody);
  return table;
}

/**
 * @param {ReturnType<typeof rowView>[]} list
 */
function renderColumnSummaries(list) {
  const root = $("#column-summaries");
  if (!root) return;
  root.replaceChildren();
  root.className = "column-summaries";

  if (!list.length) {
    const p = document.createElement("p");
    p.className = "column-summaries-empty";
    p.textContent = "No programs match the current filters.";
    root.appendChild(p);
    return;
  }

  const n = list.length;

  const degMap = new Map();
  for (const v of list) {
    const d = v.degree || "";
    degMap.set(d, (degMap.get(d) ?? 0) + 1);
  }
  const degEntries = [...degMap.entries()].map(([key, count]) => ({
    label: key || "—",
    count,
  }));
  degEntries.sort((a, b) => b.count - a.count);

  const semMap = new Map();
  for (const v of list) {
    const raw = v.berkeleySem;
    const key = raw == null || !Number.isFinite(raw) ? "—" : String(raw);
    semMap.set(key, (semMap.get(key) ?? 0) + 1);
  }
  const semEntries = [...semMap.entries()].map(([key, count]) => ({
    label: key === "—" ? "—" : `${key} sem`,
    count,
  }));
  semEntries.sort((a, b) => b.count - a.count);

  const hostMap = new Map();
  for (const v of list) {
    const id = v.hostModel && String(v.hostModel).trim() ? v.hostModel : "__none__";
    hostMap.set(id, (hostMap.get(id) ?? 0) + 1);
  }
  const hostEntries = [...hostMap.entries()].map(([id, count]) => ({
    label: id === "__none__" ? "—" : hostModelShortLabel(id) || id,
    count,
  }));
  hostEntries.sort((a, b) => b.count - a.count);

  const tagItems = (categories.positioning_tags?.items ?? []).filter((x) => x && x.id && x.id !== "INVALID");
  const tagCounts = new Map();
  for (const it of tagItems) tagCounts.set(it.id, 0);
  for (const v of list) {
    for (const t of v.tags) {
      tagCounts.set(t, (tagCounts.get(t) ?? 0) + 1);
    }
  }
  const tagRows = [...tagCounts.entries()]
    .map(([id, count]) => ({
      id,
      count,
      label: labelForId("positioning_tags", id) || id,
    }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, undefined, { sensitivity: "base" }));

  const degList = buildSummaryList(summarizeWithOtherBucket(degEntries, n));
  const semList = buildSummaryList(summarizeWithOtherBucket(semEntries, n));
  const hostList = buildSummaryList(summarizeWithOtherBucket(hostEntries, n));
  const tagList = buildSummaryList(
    tagRows.map((r) => ({ label: r.label, count: r.count })),
    { tags: true },
  );

  root.appendChild(
    buildSummaryTableRow([
      null,
      null,
      degList,
      semList,
      hostList,
      tagList,
    ]),
  );
}

function renderTable() {
  const tbody = $("#program-table tbody");
  if (!tbody || !corpus) {
    if (tbody) tbody.replaceChildren();
    setCountLine(0, 0);
    $("#column-summaries")?.replaceChildren();
    return;
  }
  const list = getFilteredPrograms().map(rowView).sort(compareRows);
  setCountLine(list.length, corpus.programs.length);
  tbody.replaceChildren();
  for (const v of list) {
    const tr = document.createElement("tr");
    tr.dataset.programId = v.program.program_id;
    tr.tabIndex = 0;
    tr.innerHTML = "";
    const cells = [
      v.institution,
      v.programName,
      v.degree,
      v.berkeleySem == null || !Number.isFinite(v.berkeleySem) ? "—" : String(v.berkeleySem),
      v.hostModelLabel,
    ];
    for (let i = 0; i < cells.length; i++) {
      const td = document.createElement("td");
      td.textContent = cells[i];
      if (i === 3) td.className = "sem-cell";
      tr.appendChild(td);
    }
    const tdTags = document.createElement("td");
    tdTags.className = "tag-cell";
    const ul = document.createElement("ul");
    ul.className = "tag-list";
    for (const t of v.tags) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tag-pill";
      btn.textContent = labelForId("positioning_tags", t) || t;
      btn.title = `Add tag to filters (must match all selected tags): ${labelForId("positioning_tags", t) || t}`;
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        e.preventDefault();
        applyTagFilter(String(t));
      });
      li.appendChild(btn);
      ul.appendChild(li);
    }
    tdTags.appendChild(ul);
    tr.appendChild(tdTags);
    tr.addEventListener("click", (e) => {
      if (e.target instanceof HTMLElement && e.target.closest("button.tag-pill")) return;
      openDetail(v.program.program_id);
    });
    tr.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openDetail(v.program.program_id);
      }
    });
    tbody.appendChild(tr);
  }
  renderColumnSummaries(list);
}

function toggleSort(key) {
  if (!SORT_KEYS.includes(key)) return;
  if (sortState.key === key) sortState.dir = sortState.dir === "asc" ? "desc" : "asc";
  else {
    sortState.key = key;
    sortState.dir = "asc";
  }
  renderTable();
}

function esc(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escAttr(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

/** Lazily parsed `#course-type-icons` JSON map (base64 data URLs from bundle) or empty. */
/** @type {Record<string, string> | null} */
let courseTypeIconSrcMapCache = null;

function getCourseTypeIconSrcMap() {
  if (courseTypeIconSrcMapCache !== null) return courseTypeIconSrcMapCache;
  const el = document.getElementById("course-type-icons");
  if (el?.textContent?.trim()) {
    try {
      courseTypeIconSrcMapCache = JSON.parse(el.textContent);
      return courseTypeIconSrcMapCache;
    } catch {
      courseTypeIconSrcMapCache = {};
      return courseTypeIconSrcMapCache;
    }
  }
  courseTypeIconSrcMapCache = {};
  return courseTypeIconSrcMapCache;
}

/**
 * Icon URL for a course_types id: embedded bundle map first, else `icons/course-types/{id}.svg` next to the module.
 * @param {unknown} typeId
 * @returns {string | null}
 */
function courseTypeIconSrc(typeId) {
  const id = String(typeId ?? "").trim();
  if (!id || id === "INVALID") return null;
  const embedded = getCourseTypeIconSrcMap()[id];
  if (embedded) return embedded;
  try {
    return new URL(`../icons/course-types/${encodeURIComponent(id)}.svg`, import.meta.url).href;
  } catch {
    return null;
  }
}

/**
 * @param {unknown} typeId
 * @param {{ size?: number, className?: string, alt?: string }} [opts]
 */
function courseTypeIconImgHtml(typeId, opts = {}) {
  const id = String(typeId ?? "").trim();
  const size = opts.size ?? 20;
  const cls = opts.className ?? "course-type-icon";
  const altText = opts.alt !== undefined ? String(opts.alt) : "";
  const url = courseTypeIconSrc(id);
  if (!url) return "";
  const altAttr = ` alt="${escAttr(altText)}"`;
  return `<img src="${escAttr(url)}"${altAttr} width="${size}" height="${size}" class="${esc(cls)}" loading="lazy" decoding="async" />`;
}

/**
 * Label cell content: optional icon + human-readable type label.
 * @param {unknown} typeId
 */
function courseTypeLabelWithIconHtml(typeId) {
  const id = String(typeId ?? "").trim();
  const lbl = labelCourseType(id) || id || "—";
  const icon = courseTypeIconImgHtml(id, {
    size: 20,
    className: "course-type-icon course-type-icon--inline",
    alt: "",
  });
  if (!icon) return esc(lbl);
  return `<span class="course-type-label-with-icon">${icon}<span class="course-type-label-text">${esc(lbl)}</span></span>`;
}

/**
 * Two-letter code for course primary_type (from underscore segments or first two chars).
 * @param {unknown} typeId
 */
function primaryTypeTwoChar(typeId) {
  const id = String(typeId ?? "").trim();
  if (!id) return "—";
  const parts = id.split("_").filter(Boolean);
  if (parts.length >= 2) {
    const a = parts[0][0] || "";
    const b = parts[1][0] || "";
    return (a + b).toUpperCase();
  }
  return id.slice(0, 2).toUpperCase().padEnd(2, "·");
}

/**
 * @param {unknown} typeId
 */
function labelCourseType(typeId) {
  return labelForId("course_types", String(typeId ?? ""));
}

/**
 * @param {object} curriculumObj
 */
function buildSampleCoursesSectionHtml(curriculumObj) {
  const cur = curriculumObj && typeof curriculumObj === "object" ? curriculumObj : {};
  const courses = Array.isArray(cur.core_courses) ? cur.core_courses : [];
  if (!courses.length) {
    return `<section class="detail-section detail-section--courses"><h3>Sample courses</h3><p class="sample-courses-empty">No core courses in this record.</p></section>`;
  }
  let rows = "";
  for (let i = 0; i < courses.length; i++) {
    const c = courses[i];
    if (!c || typeof c !== "object") continue;
    const cid = String(c.course_id ?? "");
    const tit = String(c.course_title ?? "");
    const abbr = primaryTypeTwoChar(c.primary_type);
    const typeLabel = labelCourseType(c.primary_type) || abbr;
    const icon = courseTypeIconImgHtml(c.primary_type, {
      size: 18,
      className: "course-type-icon course-type-icon--sample",
      alt: typeLabel,
    });
    let shown = tit;
    let ell = "";
    if (tit.length > COURSE_TITLE_LIST_MAX) {
      shown = tit.slice(0, COURSE_TITLE_LIST_MAX);
      ell = "…";
    }
    const rightTd = icon
      ? `<td class="sample-course-type">${icon}</td>`
      : `<td class="sample-course-abbr">${esc(abbr)}</td>`;
    rows += `<tr class="course-sample-row" data-course-index="${i}" tabindex="0" role="button"><td class="sample-course-main">${esc(
      cid
    )} - ${esc(shown)}${ell}</td>${rightTd}</tr>`;
  }
  return `<section class="detail-section detail-section--courses"><h3>Sample courses</h3><table class="sample-courses" aria-label="Core courses"><tbody>${rows}</tbody></table></section>`;
}

/**
 * @param {object} p
 */
function _fmt_currency(v) {
  if (v === null || v === undefined) return "—";
  return "$" + Number(v).toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function _fmt_num(v) {
  if (v === null || v === undefined) return "—";
  return Number(v).toLocaleString("en-US", { maximumFractionDigits: 1 });
}

function buildFreoppSectionHtml(p) {
  const f = p.freopp_roi && typeof p.freopp_roi === "object" ? p.freopp_roi : null;
  let html = `<section class="detail-section"><h3>FREOPP ROI Study 2022</h3>`;
  if (!f) {
    const ident = p.identity ?? {};
    let reason = "No matching record found in the FREOPP Graduate ROI Dataset 2022.";
    if (!ident.ipeds_unitid) {
      reason = "No IPEDS UnitID recorded for this institution — run lookup-ipeds-unitids.py to enable FREOPP matching.";
    } else if (!ident.cip_code || ident.cip_code === "unknown" || ident.cip_code === "INVALID") {
      reason = "No valid CIP code recorded for this program — run classify-cip to enable FREOPP matching.";
    }
    html += `<table class="def-table"><tr><th>Status</th><td>${esc(reason)}</td></tr></table>`;
    html += `</section>`;
    return html;
  }

  if (f.match_confidence === "low") {
    html += `<p style="color:#b45309;background:#fef3c7;padding:0.4rem 0.6rem;border-radius:4px;margin-bottom:0.5rem;font-size:0.85em">⚠ Low-confidence match — CIP code did not align; matched on degree field, length, and academic context.</p>`;
  }

  html += `<table class="def-table">`;

  // Program info
  html += `<tr><th>Degree Field</th><td>${esc(f.degree_field ?? "—")}</td></tr>`;
  html += `<tr><th>Field Category</th><td>${esc(f.degree_field_category ?? "—")}</td></tr>`;
  html += `<tr><th>Control</th><td>${esc(f.control ?? "—")}</td></tr>`;
  html += `<tr><th>Cohort Count</th><td>${f.college_scorecard_cohort_count != null ? f.college_scorecard_cohort_count.toLocaleString() : "—"}</td></tr>`;

  // Cost
  html += `<tr><th colspan="2" class="def-table-subheader">Cost</th></tr>`;
  html += `<tr><th>Annual Tuition</th><td>${_fmt_currency(f.annual_tuition)}</td></tr>`;
  html += `<tr><th>Annual Ed. Spending</th><td>${_fmt_currency(f.annual_education_spending)}</td></tr>`;
  html += `<tr><th>Completion Rate</th><td>${esc(f.estimated_completion_rate ?? "—")}</td></tr>`;

  // ROI
  html += `<tr><th colspan="2" class="def-table-subheader">Return on Investment</th></tr>`;
  html += `<tr><th>% ↑ Lifetime Earnings</th><td>${esc(f.percentage_increase_lifetime_earnings ?? "—")}</td></tr>`;
  html += `<tr><th>ROI Rank (Master's)</th><td>${f.rank_by_roi_masters != null ? "#" + f.rank_by_roi_masters.toLocaleString() : "—"}</td></tr>`;

  html += `</table>`;
  html += `<p class="detail-empty" style="font-size:0.8em;margin-top:0.5rem">Source: FREOPP Graduate ROI Dataset 2022 · Credential Level 5 (Master's)</p>`;
  html += `</section>`;
  return html;
}

function buildHistoricalSectionHtml(p) {
  const hist = Array.isArray(p.historical) ? p.historical : [];
  const sorted = [...hist].sort((a, b) =>
    String(b.academic_year ?? "").localeCompare(String(a.academic_year ?? ""))
  );
  let html = `<section class="detail-section"><h3>Historical degrees granted</h3>`;
  if (editMode) {
    if (hist.length === 0) {
      html += `<p class="detail-empty">No data yet. Add a row below.</p>`;
    } else {
      html += `<table class="def-table"><thead><tr><th>Academic Year</th><th>Degrees Granted</th><th></th></tr></thead><tbody>`;
      for (let i = 0; i < hist.length; i++) {
        const e = hist[i] && typeof hist[i] === "object" ? hist[i] : {};
        const ay = String(e.academic_year ?? "");
        const dg = e.degrees_granted === null || e.degrees_granted === undefined ? "" : String(e.degrees_granted);
        html += `<tr>`;
        html += `<td><input type="text" data-hist-idx="${i}" data-hist-field="academic_year" value="${esc(ay)}" placeholder="e.g. 2022-23" /></td>`;
        html += `<td><input type="number" data-hist-idx="${i}" data-hist-field="degrees_granted" value="${esc(dg)}" step="1" min="0" /></td>`;
        html += `<td><button type="button" class="hist-row-remove" data-hist-idx="${i}">Remove</button></td>`;
        html += `</tr>`;
      }
      html += `</tbody></table>`;
    }
    html += `<button type="button" id="hist-add-row" style="margin-top:0.5rem">+ Add year</button>`;
  } else {
    if (sorted.length === 0) {
      html += `<p class="detail-empty">No historical degree data collected.</p>`;
    } else {
      html += `<table class="def-table"><tr><th>Academic Year</th><th>Degrees Granted</th></tr>`;
      for (const e of sorted) {
        const ay = String(e.academic_year ?? "");
        const dg = e.degrees_granted === null || e.degrees_granted === undefined ? "—" : String(e.degrees_granted);
        html += `<tr><td>${esc(ay)}</td><td>${esc(dg)}</td></tr>`;
      }
      html += `</table>`;
    }
  }
  html += `</section>`;
  return html;
}

function onHistInput(e) {
  const t = e.target;
  if (!(t instanceof HTMLInputElement)) return;
  const idx = parseInt(/** @type {HTMLElement} */ (t).dataset.histIdx ?? "", 10);
  const field = /** @type {HTMLElement} */ (t).dataset.histField;
  if (isNaN(idx) || !field || !detailProgramId) return;
  const p = findProgram(detailProgramId);
  if (!p) return;
  if (!Array.isArray(p.historical)) p.historical = [];
  const entry = p.historical[idx];
  if (!entry || typeof entry !== "object") return;
  if (field === "degrees_granted") {
    const s = t.value.trim();
    entry.degrees_granted = s === "" ? null : Number(s);
  } else {
    entry[field] = t.value;
  }
  syncEditChrome();
}

function onHistRemove(e) {
  const t = /** @type {HTMLElement} */ (e.currentTarget);
  const idx = parseInt(t.dataset.histIdx ?? "", 10);
  if (isNaN(idx) || !detailProgramId) return;
  const p = findProgram(detailProgramId);
  if (!p || !Array.isArray(p.historical)) return;
  p.historical.splice(idx, 1);
  renderDetailBody();
  syncEditChrome();
}

function onHistAddRow() {
  if (!detailProgramId) return;
  const p = findProgram(detailProgramId);
  if (!p) return;
  if (!Array.isArray(p.historical)) p.historical = [];
  p.historical.push({ academic_year: "", degrees_granted: null });
  renderDetailBody();
  syncEditChrome();
}

/**
 * @param {object} p
 */
function setProgramDialogTitle(p) {
  const titleEl = $("#dlg-detail-title");
  if (!titleEl || !p) return;
  const inst = p.identity?.institution_name ?? "";
  const pn = p.identity?.program_name ?? "";
  const text = [inst, pn].filter(Boolean).join(" — ") || "Program";
  titleEl.replaceChildren();
  const u = typeof p.base_url === "string" ? p.base_url.trim() : "";
  if (u) {
    const a = document.createElement("a");
    a.href = u;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = text;
    titleEl.appendChild(a);
  } else {
    titleEl.textContent = text;
  }
}

function closeCourseDialog() {
  const dlg = /** @type {HTMLDialogElement} */ ($("#dlg-course"));
  if (dlg?.open) dlg.close();
}

/**
 * @param {object} course
 */
function openCourseDialog(course) {
  if (!course || typeof course !== "object") return;
  closeCourseDialog();
  const dlg = /** @type {HTMLDialogElement} */ ($("#dlg-course"));
  const scroll = $("#course-scroll");
  if (!dlg || !scroll) return;
  setCourseDialogTitle(course);
  scroll.innerHTML = buildCourseDetailHtml(course);
  dlg.showModal();
}

/**
 * Full and display-safe heading for the course dialog (`course_id - course_title`).
 * @param {object} course
 * @returns {{ full: string, short: string }}
 */
function coursePopoverTitleParts(course) {
  const cid = String(course.course_id ?? "").trim();
  const tit = String(course.course_title ?? "").trim();
  const full = cid && tit ? `${cid} - ${tit}` : cid || tit || "Course";
  let short = full;
  if (full.length > COURSE_POPOVER_TITLE_MAX) {
    short = full.slice(0, Math.max(1, COURSE_POPOVER_TITLE_MAX - 1)) + "…";
  }
  return { full, short };
}

/**
 * @param {object} course
 */
function setCourseDialogTitle(course) {
  const titleEl = $("#dlg-course-title");
  if (!titleEl) return;
  const { full, short } = coursePopoverTitleParts(course);
  titleEl.removeAttribute("title");
  titleEl.replaceChildren();
  const url = course.source_url && String(course.source_url).trim();
  if (url) {
    const a = document.createElement("a");
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = short;
    if (short !== full) a.title = full;
    titleEl.appendChild(a);
  } else {
    titleEl.textContent = short;
    if (short !== full) titleEl.title = full;
  }
}

/**
 * @param {object} c
 */
function buildCourseDetailHtml(c) {
  /** @type {string[]} */
  const rows = [];
  const push = (label, innerTd) => {
    rows.push(`<tr><th>${esc(label)}</th><td>${innerTd}</td></tr>`);
  };
  const fullTit = String(c.course_title ?? "").trim();
  push("Course title", fullTit ? esc(fullTit) : "—");
  push(
    "Units / credits",
    c.units_or_credits != null && c.units_or_credits !== "" ? esc(String(c.units_or_credits)) : "—"
  );
  const pt = String(c.primary_type ?? "").trim();
  push("Primary type", courseTypeLabelWithIconHtml(pt));
  const st = c.secondary_type;
  const stStr = st == null || st === "" ? null : String(st).trim();
  push("Secondary type", stStr == null ? "—" : courseTypeLabelWithIconHtml(stStr));
  const nw = c.normalized_unit_weight;
  push(
    "Normalized unit weight",
    nw != null && Number.isFinite(Number(nw)) ? esc(Number(nw).toFixed(2)) : "—"
  );
  const sum = String(c.course_summary ?? "").trim();
  push("Summary", esc(sum || "—"));
  const lo = Array.isArray(c.learning_outcomes)
    ? c.learning_outcomes.filter((x) => typeof x === "string" && x.trim())
    : [];
  const loHtml =
    lo.length === 0 ? "—" : `<ul class="course-lo">${lo.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`;
  push("Learning outcomes", loHtml);
  return `<table class="def-table course-detail-table"><tbody>${rows.join("")}</tbody></table>`;
}

function formatCostK(usd) {
  if (usd == null || usd === "" || !Number.isFinite(Number(usd))) return "—";
  const n = Math.round(Number(usd) / 1000);
  return `$${n}k`;
}

/**
 * @param {object} obj
 * @param {string} path
 */
function getPath(obj, path) {
  const parts = path.split(".");
  let cur = obj;
  for (const p of parts) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = /** @type {Record<string, unknown>} */ (cur)[p];
  }
  return cur;
}

/**
 * @param {object} obj
 * @param {string} path
 * @param {unknown} value
 */
function setPath(obj, path, value) {
  const parts = path.split(".");
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    const k = parts[i];
    if (cur[k] == null || typeof cur[k] !== "object") cur[k] = {};
    cur = /** @type {Record<string, unknown>} */ (cur)[k];
  }
  cur[parts[parts.length - 1]] = value;
}

function findProgram(id) {
  return corpus?.programs.find((x) => x.program_id === id) ?? null;
}

function closeDetail() {
  closeCourseDialog();
  if (editMode && editBaseline && detailProgramId) {
    const idx = corpus?.programs.findIndex((x) => x.program_id === detailProgramId) ?? -1;
    if (corpus && idx >= 0) corpus.programs[idx] = deepClone(editBaseline);
  }
  const dlg = /** @type {HTMLDialogElement} */ ($("#dlg-detail"));
  if (dlg?.open) dlg.close();
  detailProgramId = null;
  editBaseline = null;
  editMode = false;
  syncEditChrome();
  renderTable();
}

function openDetail(programId) {
  if (!findProgram(programId)) return;
  detailProgramId = programId;
  editBaseline = null;
  editMode = false;
  const dlg = /** @type {HTMLDialogElement} */ ($("#dlg-detail"));
  renderDetailBody();
  syncEditChrome();
  dlg?.showModal();
}

function enterEditMode() {
  const p = detailProgramId ? findProgram(detailProgramId) : null;
  if (!p) return;
  editBaseline = deepClone(p);
  editMode = true;
  renderDetailBody();
  syncEditChrome();
}

function cancelEditMode() {
  const p = detailProgramId ? findProgram(detailProgramId) : null;
  if (!p || !editBaseline) {
    editMode = false;
    editBaseline = null;
    syncEditChrome();
    renderDetailBody();
    return;
  }
  const idx = corpus?.programs.findIndex((x) => x.program_id === detailProgramId) ?? -1;
  if (corpus && idx >= 0) corpus.programs[idx] = deepClone(editBaseline);
  editBaseline = null;
  editMode = false;
  renderDetailBody();
  syncEditChrome();
}

function syncEditChrome() {
  const hint = $("#edit-hint");
  const btnEdit = $("#btn-edit-toggle");
  const btnCancel = $("#btn-edit-cancel");
  const btnExport = $("#btn-export-patch");
  const meta = $("#patch-meta-row");
  if (hint) hint.hidden = !editMode;
  if (btnCancel) btnCancel.hidden = !editMode;
  if (btnExport) {
    btnExport.hidden = !editMode;
    btnExport.disabled = !editMode || !isDirty();
  }
  if (meta) meta.hidden = !editMode;
  if (btnEdit) btnEdit.textContent = editMode ? "Editing" : "Edit";
  if (btnEdit) btnEdit.disabled = !detailProgramId || editMode;
}

function isDirty() {
  const p = detailProgramId ? findProgram(detailProgramId) : null;
  if (!editMode || !p || !editBaseline) return false;
  for (const path of EDITABLE_PATHS) {
    if (!deepEqual(getPath(p, path), getPath(editBaseline, path))) return true;
  }
  return false;
}

function collectChangesForExport() {
  const p = detailProgramId ? findProgram(detailProgramId) : null;
  if (!p || !editBaseline) return [];
  /** @type {object[]} */
  const changes = [];
  for (const path of EDITABLE_PATHS) {
    const oldV = getPath(editBaseline, path);
    const newV = getPath(p, path);
    if (!deepEqual(oldV, newV)) {
      changes.push({
        program_id: detailProgramId,
        path,
        old_value: oldV === undefined ? null : oldV,
        new_value: newV === undefined ? null : newV,
      });
    }
  }
  return changes;
}

function isoDate() {
  return new Date().toISOString().slice(0, 10);
}

function exportPatch() {
  const p = detailProgramId ? findProgram(detailProgramId) : null;
  if (!p || !editBaseline) return;
  const changes = collectChangesForExport();
  if (!changes.length) return;
  const createdBy = $("#meta-by")?.value?.trim() || "";
  const notes = $("#meta-notes")?.value?.trim() || "";
  const patch = {
    patch_metadata: {
      created_at: isoDate(),
      created_by: createdBy,
      source_corpus_name: "MDes Peer Program Comparator Corpus",
      notes,
    },
    changes,
  };
  const blob = new Blob([JSON.stringify(patch, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  const safeId = String(detailProgramId).replace(/[^a-z0-9_-]+/gi, "_");
  a.href = URL.createObjectURL(blob);
  a.download = `patch_${safeId}_${isoDate()}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
  setStatus("Patch downloaded.");
  editBaseline = deepClone(p);
  syncEditChrome();
  renderDetailBody();
}

/**
 * @param {string} path
 */
function resetField(path) {
  const p = detailProgramId ? findProgram(detailProgramId) : null;
  if (!p || !editBaseline || !editMode) return;
  const v = getPath(editBaseline, path);
  setPath(p, path, deepClone(v));
  renderDetailBody();
  syncEditChrome();
}

function renderDetailBody() {
  const root = $("#detail-scroll");
  if (!root || !detailProgramId) return;
  const p = findProgram(detailProgramId);
  if (!p) {
    root.innerHTML = "";
    return;
  }
  const ident = p.identity ?? {};
  const pos = p.positioning ?? {};
  const dur = p.duration ?? {};
  const deg = p.degree_cost ?? {};
  const cur = p.curriculum ?? {};
  const elec = cur.electives ?? {};

  const hostIdVal = String(ident.host_academic_model ?? "");
  const hostItems = (categories.host_academic_models?.items ?? []).filter((x) => x && x.id);
  const hostIds = new Set(hostItems.map((x) => x.id));
  let hostOptions = hostItems
    .map((x) => `<option value="${esc(x.id)}">${esc(x.label || x.id)}</option>`)
    .join("");
  if (hostIdVal && !hostIds.has(hostIdVal)) {
    hostOptions = `<option value="${esc(hostIdVal)}">${esc(hostIdVal)}</option>` + hostOptions;
  }

  const durIdVal = String(dur.duration_category ?? "");
  const durItems = (categories.duration_categories?.items ?? []).filter((x) => x && x.id);
  const durIds = new Set(durItems.map((x) => x.id));
  let durOptions = durItems
    .map((x) => `<option value="${esc(x.id)}">${esc(x.label || x.id)}</option>`)
    .join("");
  if (durIdVal && !durIds.has(durIdVal)) {
    durOptions = `<option value="${esc(durIdVal)}">${esc(durIdVal)}</option>` + durOptions;
  }

  const unitIdVal = String(cur.unit_system ?? "");
  const unitItems = (categories.unit_systems?.items ?? []).filter((x) => x && x.id);
  const unitIds = new Set(unitItems.map((x) => x.id));
  let unitOptions = unitItems
    .map((x) => `<option value="${esc(x.id)}">${esc(x.label || x.id)}</option>`)
    .join("");
  if (unitIdVal && !unitIds.has(unitIdVal)) {
    unitOptions = `<option value="${esc(unitIdVal)}">${esc(unitIdVal)}</option>` + unitOptions;
  }

  const seqIdVal = String(cur.sequencedness ?? "");
  const seqItems = (categories.sequencedness?.items ?? []).filter((x) => x && x.id);
  const seqIds = new Set(seqItems.map((x) => x.id));
  let seqOptions = seqItems
    .map((x) => `<option value="${esc(x.id)}">${esc(x.label || x.id)}</option>`)
    .join("");
  if (seqIdVal && !seqIds.has(seqIdVal)) {
    seqOptions = `<option value="${esc(seqIdVal)}">${esc(seqIdVal)}</option>` + seqOptions;
  }

  const tagItems = categories.positioning_tags?.items ?? [];
  const tagList = Array.isArray(pos.positioning_tags) ? pos.positioning_tags : [];
  const tagChecks = tagItems
    .filter((x) => x && x.id)
    .map((x) => {
      const on = tagList.includes(x.id);
      return `<label><input type="checkbox" data-path="positioning.positioning_tags" data-tag="${esc(
        x.id
      )}" ${editMode ? "" : "disabled"} ${on ? "checked" : ""}/> ${esc(x.label || x.id)}</label>`;
    })
    .join("");

  const cipIdVal = String(ident.cip_code ?? "");
  const cipItems = (categories.cip_codes?.items ?? []).filter((x) => x && x.id);
  const cipIds = new Set(cipItems.map((x) => x.id));
  let cipOptions = cipItems
    .map((x) => `<option value="${esc(x.id)}">${esc(x.id)}${x.label && x.label !== x.id ? " — " + esc(x.label) : ""}</option>`)
    .join("");
  if (cipIdVal && !cipIds.has(cipIdVal)) {
    cipOptions = `<option value="${esc(cipIdVal)}">${esc(cipIdVal)}</option>` + cipOptions;
  }

  const unitsStr = (ident.host_academic_units ?? []).join(", ");

  /** @param {string} path @param {string} label @param {string} inner @returns {string} */
  const fieldRow = (path, label, inner) => {
    const dirty =
      editMode && editBaseline && !deepEqual(getPath(p, path), getPath(editBaseline, path));
    const reset =
      editMode && dirty
        ? `<button type="button" class="reset-field" data-reset="${esc(path)}">Reset field</button>`
        : "";
    return `<tr data-field-path="${esc(path)}" class="${dirty ? "field-dirty" : ""}"><th>${esc(
      label
    )}</th><td>${inner}${reset}</td></tr>`;
  };

  let html = "";

  html += `<section class="detail-section"><h3>Identity</h3><table class="def-table">`;
  if (editMode) {
    html += fieldRow(
      "identity.institution_name",
      "Institution",
      `<input type="text" data-path="identity.institution_name" value="${esc(ident.institution_name ?? "")}" />`
    );
    html += fieldRow(
      "identity.program_name",
      "Program",
      `<input type="text" data-path="identity.program_name" value="${esc(ident.program_name ?? "")}" />`
    );
    html += fieldRow(
      "identity.credential_name",
      "Credential name",
      `<input type="text" data-path="identity.credential_name" value="${esc(ident.credential_name ?? "")}" />`
    );
    html += fieldRow(
      "identity.degree_type",
      "Degree type",
      `<input type="text" data-path="identity.degree_type" value="${esc(ident.degree_type ?? "")}" />`
    );
    html += fieldRow(
      "identity.host_academic_units",
      "Host academic units",
      `<input type="text" data-path="identity.host_academic_units" value="${esc(unitsStr)}" placeholder="Comma-separated" />`
    );
    html += fieldRow(
      "identity.host_academic_model",
      "Host academic model",
      `<select data-path="identity.host_academic_model">${hostOptions}</select>`
    );
    html += fieldRow(
      "identity.location_label",
      "Location",
      `<input type="text" data-path="identity.location_label" value="${esc(ident.location_label ?? "")}" />`
    );
    html += fieldRow(
      "identity.first_degree_granted_year",
      "First degree year",
      `<input type="text" data-path="identity.first_degree_granted_year" value="${esc(String(ident.first_degree_granted_year ?? ""))}" placeholder="e.g. 1998 or unknown" />`
    );
    html += fieldRow(
      "identity.cip_code",
      "CIP code",
      `<select data-path="identity.cip_code">${cipOptions}</select>`
    );
    html += fieldRow(
      "identity.ipeds_unitid",
      "IPEDS UnitID",
      `<input type="text" data-path="identity.ipeds_unitid" value="${esc(String(ident.ipeds_unitid ?? ""))}" placeholder="e.g. 110635" />`
    );
  } else {
    html += `<tr><th>Institution</th><td>${esc(ident.institution_name ?? "")}</td></tr>`;
    html += `<tr><th>Program</th><td>${esc(ident.program_name ?? "")}</td></tr>`;
    html += `<tr><th>Credential name</th><td>${esc(ident.credential_name ?? "")}</td></tr>`;
    html += `<tr><th>Degree type</th><td>${esc(ident.degree_type ?? "")}</td></tr>`;
    html += `<tr><th>Host academic units</th><td>${esc(unitsStr)}</td></tr>`;
    html += `<tr><th>Host academic model</th><td>${esc(labelForId("host_academic_models", String(ident.host_academic_model ?? "")))}</td></tr>`;
    html += `<tr><th>Location</th><td>${esc(ident.location_label ?? "")}</td></tr>`;
    html += `<tr><th>First degree year</th><td>${esc(String(ident.first_degree_granted_year ?? ""))}</td></tr>`;
    const cipLabel = labelForId("cip_codes", cipIdVal);
    html += `<tr><th>CIP code</th><td>${esc(cipIdVal)}${cipLabel && cipLabel !== cipIdVal ? " — " + esc(cipLabel) : ""}</td></tr>`;
    if (ident.ipeds_unitid) {
      html += `<tr><th>IPEDS UnitID</th><td>${esc(String(ident.ipeds_unitid))}</td></tr>`;
    }
  }
  html += `</table></section>`;

  html += `<section class="detail-section"><h3>Positioning</h3><table class="def-table">`;
  if (editMode) {
    html += fieldRow(
      "positioning.positioning_summary",
      "Positioning summary",
      `<textarea data-path="positioning.positioning_summary">${esc(pos.positioning_summary ?? "")}</textarea>`
    );
    const pathTags = "positioning.positioning_tags";
    const tagsDirty =
      editMode && editBaseline && !deepEqual(getPath(p, pathTags), getPath(editBaseline, pathTags));
    const tagsReset =
      editMode && tagsDirty
        ? `<button type="button" class="reset-field" data-reset="${esc(pathTags)}">Reset field</button>`
        : "";
    html += `<tr data-field-path="${esc(pathTags)}" class="${tagsDirty ? "field-dirty" : ""}"><th>Positioning tags</th><td><div class="tag-editor">${tagChecks}</div>${tagsReset}</td></tr>`;
  } else {
    html += `<tr><th>Positioning summary</th><td>${esc(pos.positioning_summary ?? "")}</td></tr>`;
    html += `<tr><th>Positioning tags</th><td><div class="tag-list">${tagList
      .map(
        (t) =>
          `<span class="tag-pill">${esc(labelForId("positioning_tags", String(t)))}</span>`
      )
      .join(" ")}</div></td></tr>`;
  }
  html += `</table></section>`;

  html += `<section class="detail-section"><h3>Duration</h3><table class="def-table">`;
  const durSummary = dur.duration_summary != null ? String(dur.duration_summary) : "";
  if (editMode) {
    html += fieldRow(
      "duration.length_in_berkeley_semesters",
      "Length (Berkeley semesters)",
      `<input type="number" data-path="duration.length_in_berkeley_semesters" value="${
        dur.length_in_berkeley_semesters == null ? "" : esc(String(dur.length_in_berkeley_semesters))
      }" step="1" min="0" />`
    );
    html += fieldRow(
      "duration.duration_category",
      "Duration category",
      `<select data-path="duration.duration_category">${durOptions}</select>`
    );
    html += fieldRow(
      "duration.duration_summary",
      "Duration summary",
      `<textarea data-path="duration.duration_summary">${esc(durSummary)}</textarea>`
    );
  } else {
    html += `<tr><th>Length (Berkeley semesters)</th><td>${
      dur.length_in_berkeley_semesters == null ? "—" : esc(String(dur.length_in_berkeley_semesters))
    }</td></tr>`;
    html += `<tr><th>Duration category</th><td>${esc(labelForId("duration_categories", String(dur.duration_category ?? "")))}</td></tr>`;
    if (durSummary) html += `<tr><th>Duration summary</th><td>${esc(durSummary)}</td></tr>`;
  }
  html += `</table></section>`;

  html += `<section class="detail-section"><h3>Degree cost</h3><table class="def-table">`;
  if (editMode) {
    html += fieldRow(
      "degree_cost.comparison_cost_usd",
      "Comparison cost (USD)",
      `<input type="number" data-path="degree_cost.comparison_cost_usd" value="${
        deg.comparison_cost_usd == null ? "" : esc(String(deg.comparison_cost_usd))
      }" step="1" min="0" />`
    );
    html += fieldRow(
      "degree_cost.base_currency",
      "Base currency",
      `<input type="text" data-path="degree_cost.base_currency" value="${esc(deg.base_currency ?? "")}" />`
    );
    html += fieldRow(
      "degree_cost.cost_base_currency",
      "Cost (base currency)",
      `<input type="number" data-path="degree_cost.cost_base_currency" value="${
        deg.cost_base_currency == null ? "" : esc(String(deg.cost_base_currency))
      }" step="0.01" />`
    );
    html += fieldRow(
      "degree_cost.exchange_rate_to_usd",
      "Exchange rate to USD",
      `<input type="number" data-path="degree_cost.exchange_rate_to_usd" value="${
        deg.exchange_rate_to_usd == null ? "" : esc(String(deg.exchange_rate_to_usd))
      }" step="0.000001" />`
    );
    html += fieldRow(
      "degree_cost.cost_basis",
      "Cost basis",
      `<input type="text" data-path="degree_cost.cost_basis" value="${esc(
        deg.cost_basis != null ? String(deg.cost_basis) : ""
      )}" />`
    );
    html += fieldRow(
      "degree_cost.comparison_cost_method",
      "Comparison cost method",
      `<input type="text" data-path="degree_cost.comparison_cost_method" value="${esc(
        deg.comparison_cost_method != null ? String(deg.comparison_cost_method) : ""
      )}" />`
    );
  } else {
    html += `<tr><th>Comparison (rounded)</th><td>${esc(formatCostK(deg.comparison_cost_usd))}</td></tr>`;
    html += `<tr><th>Base currency</th><td>${esc(deg.base_currency ?? "")}</td></tr>`;
    html += `<tr><th>Cost (base currency)</th><td>${
      deg.cost_base_currency == null ? "—" : esc(String(deg.cost_base_currency))
    }</td></tr>`;
    if (deg.cost_basis) html += `<tr><th>Cost basis</th><td>${esc(String(deg.cost_basis))}</td></tr>`;
    if (deg.comparison_cost_method)
      html += `<tr><th>Comparison cost method</th><td>${esc(String(deg.comparison_cost_method))}</td></tr>`;
  }
  html += `</table></section>`;

  html += `<section class="detail-section"><h3>Curriculum summary</h3><table class="def-table">`;
  if (editMode) {
    html += fieldRow(
      "curriculum.curriculum_summary",
      "Curriculum summary",
      `<textarea data-path="curriculum.curriculum_summary">${esc(cur.curriculum_summary ?? "")}</textarea>`
    );
    html += fieldRow(
      "curriculum.unit_system",
      "Unit system",
      `<select data-path="curriculum.unit_system">${unitOptions}</select>`
    );
    html += fieldRow(
      "curriculum.sequencedness",
      "Sequencedness",
      `<select data-path="curriculum.sequencedness">${seqOptions}</select>`
    );
    html += fieldRow(
      "curriculum.offers_specialization",
      "Offers specialization",
      `<select data-path="curriculum.offers_specialization"><option value="true" ${
        cur.offers_specialization === true ? "selected" : ""
      }>Yes</option><option value="false" ${
        !cur.offers_specialization ? "selected" : ""
      }>No</option></select>`
    );
    html += fieldRow(
      "curriculum.electives.summary",
      "Electives summary",
      `<textarea data-path="curriculum.electives.summary">${esc(elec.summary ?? "")}</textarea>`
    );
  } else {
    html += `<tr><th>Curriculum summary</th><td>${esc(cur.curriculum_summary ?? "")}</td></tr>`;
    html += `<tr><th>Unit system</th><td>${esc(labelForId("unit_systems", String(cur.unit_system ?? "")))}</td></tr>`;
    html += `<tr><th>Sequencedness</th><td>${esc(labelForId("sequencedness", String(cur.sequencedness ?? "")))}</td></tr>`;
    html += `<tr><th>Offers specialization</th><td>${cur.offers_specialization ? "Yes" : "No"}</td></tr>`;
    html += `<tr><th>Electives summary</th><td>${esc(elec.summary ?? "")}</td></tr>`;
  }
  html += `</table></section>`;

  html += buildHistoricalSectionHtml(p);

  html += buildSampleCoursesSectionHtml(cur);

  html += buildFreoppSectionHtml(p);

  root.innerHTML = html;

  setProgramDialogTitle(p);

  if (editMode) {
    const selHost = root.querySelector('[data-path="identity.host_academic_model"]');
    if (selHost instanceof HTMLSelectElement) selHost.value = String(ident.host_academic_model ?? "");
    const selCip = root.querySelector('[data-path="identity.cip_code"]');
    if (selCip instanceof HTMLSelectElement) selCip.value = String(ident.cip_code ?? "");
    const selDur = root.querySelector('[data-path="duration.duration_category"]');
    if (selDur instanceof HTMLSelectElement) selDur.value = String(dur.duration_category ?? "");
    const selUnit = root.querySelector('[data-path="curriculum.unit_system"]');
    if (selUnit instanceof HTMLSelectElement) selUnit.value = String(cur.unit_system ?? "");
    const selSeq = root.querySelector('[data-path="curriculum.sequencedness"]');
    if (selSeq instanceof HTMLSelectElement) selSeq.value = String(cur.sequencedness ?? "");

    root.querySelectorAll("input[data-path]:not([type=checkbox])").forEach((el) => {
      el.addEventListener("input", onFieldInput);
    });
    root.querySelectorAll("textarea[data-path]").forEach((el) => {
      el.addEventListener("input", onFieldInput);
    });
    root.querySelectorAll("select[data-path]").forEach((el) => {
      el.addEventListener("change", onFieldInput);
    });
    root.querySelectorAll('input[type="checkbox"][data-path="positioning.positioning_tags"]').forEach((el) => {
      el.addEventListener("change", onTagCheckbox);
    });
    root.querySelectorAll(".reset-field").forEach((btn) => {
      btn.addEventListener("click", () => {
        const path = btn.getAttribute("data-reset");
        if (path) resetField(path);
      });
    });
    root.querySelectorAll("input[data-hist-idx]").forEach((el) => {
      el.addEventListener("input", onHistInput);
    });
    root.querySelectorAll(".hist-row-remove").forEach((btn) => {
      btn.addEventListener("click", onHistRemove);
    });
    const histAddBtn = root.querySelector("#hist-add-row");
    if (histAddBtn) histAddBtn.addEventListener("click", onHistAddRow);
  }
}

/**
 * After inline edits, update dirty row styling and reset buttons without re-rendering the whole form
 * (re-rendering on every keystroke destroys inputs and interrupts typing).
 */
function updateDetailDirtyStyling() {
  const root = $("#detail-scroll");
  const p = detailProgramId ? findProgram(detailProgramId) : null;
  if (!root || !p || !editMode || !editBaseline) return;
  for (const path of EDITABLE_PATHS) {
    const tr = root.querySelector(`tr[data-field-path="${path}"]`);
    if (!(tr instanceof HTMLTableRowElement)) continue;
    const dirty = !deepEqual(getPath(p, path), getPath(editBaseline, path));
    tr.classList.toggle("field-dirty", dirty);
    const td = tr.cells[1];
    if (!td) continue;
    const resetBtn = td.querySelector("button.reset-field");
    if (dirty && !resetBtn) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "reset-field";
      btn.dataset.reset = path;
      btn.textContent = "Reset field";
      btn.addEventListener("click", () => resetField(path));
      td.appendChild(btn);
    } else if (!dirty && resetBtn) {
      resetBtn.remove();
    }
  }
}

function onFieldInput(e) {
  const t = e.target;
  if (!(t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement || t instanceof HTMLSelectElement))
    return;
  const path = t.getAttribute("data-path");
  if (!path || !detailProgramId) return;
  const p = findProgram(detailProgramId);
  if (!p) return;
  let val;
  if (t instanceof HTMLSelectElement && path === "curriculum.offers_specialization") {
    val = t.value === "true";
  } else if (t instanceof HTMLInputElement && t.type === "number") {
    const s = t.value.trim();
    val = s === "" ? null : Number(s);
    if (Number.isNaN(val)) val = null;
  } else if (path === "identity.host_academic_units") {
    val = t.value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  } else {
    val = t.value;
  }
  if (path === "duration.duration_summary" && val === "") {
    if (p.duration && typeof p.duration === "object") delete p.duration.duration_summary;
    updateDetailDirtyStyling();
    syncEditChrome();
    return;
  }
  setPath(p, path, val);
  updateDetailDirtyStyling();
  syncEditChrome();
}

function onTagCheckbox() {
  const p = detailProgramId ? findProgram(detailProgramId) : null;
  if (!p) return;
  const root = $("#detail-scroll");
  if (!root) return;
  const checked = [...root.querySelectorAll('input[type="checkbox"][data-path="positioning.positioning_tags"]:checked')].map(
    (x) => /** @type {HTMLInputElement} */ (x).dataset.tag
  ).filter(Boolean);
  if (!p.positioning || typeof p.positioning !== "object") p.positioning = {};
  p.positioning.positioning_tags = checked;
  updateDetailDirtyStyling();
  syncEditChrome();
}

function buildFilterPanel() {
  const body = $("#filter-body");
  if (!body || !corpus) return;
  const rows = corpus.programs.map(rowView);
  const totalPrograms = rows.length;
  const degs = [...new Set(rows.map((r) => r.degree))].sort((a, b) => a.localeCompare(b));
  const hosts = [...new Set(rows.map((r) => r.hostModel).filter(Boolean))].sort();
  const allTags = new Set();
  for (const r of rows) {
    r.tags.forEach((x) => allTags.add(x));
  }
  const tags = [...allTags].sort();
  const tagDisplayLabel = (v) => labelForId("positioning_tags", v) || v;
  const tagCount = (v) => rows.filter((r) => r.tags.includes(v)).length;
  /**
   * @param {string} v tag id
   */
  const renderTagCheckbox = (v) => {
    const id = `f-tags-${encodeURIComponent(v)}`.replace(/%/g, "_");
    const on = filters.tags.has(v);
    const base = tagDisplayLabel(v);
    const label = filterPanelShowCounts ? `${base} (${tagCount(v)}/${totalPrograms})` : base;
    return `<label><input type="checkbox" data-filter-set="tags" value="${esc(v)}" id="${id}" ${
      on ? "checked" : ""
    }/> ${esc(label)}</label>`;
  };
  const tagsAdjacentLabel = tags.filter((v) => tagDisplayLabel(v).toLowerCase().includes("adjacent"));
  const tagsOther = tags.filter((v) => !tagDisplayLabel(v).toLowerCase().includes("adjacent"));
  const byTagLabel = (a, b) => tagDisplayLabel(a).localeCompare(tagDisplayLabel(b), undefined, { sensitivity: "base" });
  tagsAdjacentLabel.sort(byTagLabel);
  tagsOther.sort(byTagLabel);

  /**
   * @param {string} title
   * @param {keyof typeof filters} setKey
   * @param {string[]} values
   * @param {(v: string) => string} labelFn
   * @param {(v: string) => number} countFn programs in corpus matching this option alone
   * @param {string} [hint]
   */
  const cbGroup = (title, setKey, values, labelFn, countFn, hint) => {
    const set = filters[setKey];
    let inner = `<div class="filter-group"><h3>${esc(title)}</h3>`;
    if (hint) inner += `<p class="filter-hint">${esc(hint)}</p>`;
    inner += `<div class="filter-checkboxes">`;
    for (const v of values) {
      const id = `f-${setKey}-${encodeURIComponent(v)}`.replace(/%/g, "_");
      const on = set.has(v);
      const base = labelFn(v);
      const label = filterPanelShowCounts ? `${base} (${countFn(v)}/${totalPrograms})` : base;
      inner += `<label><input type="checkbox" data-filter-set="${esc(setKey)}" value="${esc(v)}" id="${id}" ${
        on ? "checked" : ""
      }/> ${esc(label)}</label>`;
    }
    inner += `</div></div>`;
    return inner;
  };

  let html = "";
  html += cbGroup("Degree type", "degrees", degs, (v) => v, (v) => rows.filter((r) => r.degree === v).length);
  html += cbGroup(
    "Host academic model",
    "hostModels",
    hosts,
    (v) => labelForId("host_academic_models", v) || v,
    (v) => rows.filter((r) => r.hostModel === v).length
  );
  const tagHint =
    "A program is shown only if it has every tag you check (AND). Leave all unchecked to ignore this filter.";
  let tagBlock = `<div class="filter-group"><h3>${esc("Positioning tags")}</h3>`;
  tagBlock += `<p class="filter-hint">${esc(tagHint)}</p>`;
  tagBlock += `<div class="filter-tags-groups">`;
  if (tagsOther.length) {
    tagBlock += `<div class="filter-tag-subgroup">`;
    tagBlock += `<div class="filter-tag-subgroup-title">${esc("Themes & focus")}</div>`;
    tagBlock += `<div class="filter-checkboxes filter-checkboxes--nested">`;
    tagBlock += tagsOther.map(renderTagCheckbox).join("");
    tagBlock += `</div></div>`;
  }
  if (tagsAdjacentLabel.length) {
    tagBlock += `<div class="filter-tag-subgroup">`;
    tagBlock += `<div class="filter-tag-subgroup-title">${esc("Adjacent disciplines")}</div>`;
    tagBlock += `<div class="filter-checkboxes filter-checkboxes--nested">`;
    tagBlock += tagsAdjacentLabel.map(renderTagCheckbox).join("");
    tagBlock += `</div></div>`;
  }
  tagBlock += `</div></div>`;
  html += tagBlock;
  html += `<div class="filter-group"><h3>Berkeley semesters</h3><div class="filter-range">`;
  html += `<label>Min <input type="number" id="f-sem-min" step="1" min="0" value="${
    filters.semMin ?? ""
  }" placeholder="—"/></label>`;
  html += `<label>Max <input type="number" id="f-sem-max" step="1" min="0" value="${
    filters.semMax ?? ""
  }" placeholder="—"/></label>`;
  html += `</div></div>`;

  const active = [];
  if (filters.degrees.size) active.push(`Degree: ${[...filters.degrees].join(", ")}`);
  if (filters.hostModels.size)
    active.push(
      `Host model: ${[...filters.hostModels].map((hid) => labelForId("host_academic_models", hid) || hid).join(", ")}`,
    );
  if (filters.tags.size)
    active.push(`Positioning tags (all of): ${[...filters.tags].map((id) => labelForId("positioning_tags", id) || id).join(", ")}`);
  if (filters.semMin != null) active.push(`Min semesters ≥ ${filters.semMin}`);
  if (filters.semMax != null) active.push(`Max semesters ≤ ${filters.semMax}`);
  html += `<div class="active-filters"><strong>Active filters</strong>`;
  if (!active.length) html += `<p>None (all programs shown).</p>`;
  else html += `<ul>${active.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>`;
  html += `</div>`;
  html += `<div class="filter-show-counts"><label><input type="checkbox" id="f-filter-show-counts" ${
    filterPanelShowCounts ? "checked" : ""
  }/> Show counts</label></div>`;

  body.innerHTML = html;
  body.querySelectorAll('input[type="checkbox"][data-filter-set]').forEach((el) => {
    el.addEventListener("change", () => {
      const setKey = el.getAttribute("data-filter-set");
      const val = el.getAttribute("value");
      if (!setKey || val == null || !(filters[setKey] instanceof Set)) return;
      const s = /** @type {Set<string>} */ (filters[setKey]);
      if (el.checked) s.add(val);
      else s.delete(val);
    });
  });
  $("#f-filter-show-counts")?.addEventListener("change", (e) => {
    const t = e.target;
    if (!(t instanceof HTMLInputElement)) return;
    readSemInputsFromFilterPanel();
    filterPanelShowCounts = t.checked;
    buildFilterPanel();
  });
}

function readSemInputsFromFilterPanel() {
  const minEl = /** @type {HTMLInputElement | null} */ (document.querySelector("#f-sem-min"));
  const maxEl = /** @type {HTMLInputElement | null} */ (document.querySelector("#f-sem-max"));
  const minV = minEl?.value?.trim() ?? "";
  const maxV = maxEl?.value?.trim() ?? "";
  filters.semMin = minV === "" ? null : Number(minV);
  filters.semMax = maxV === "" ? null : Number(maxV);
  if (filters.semMin != null && Number.isNaN(filters.semMin)) filters.semMin = null;
  if (filters.semMax != null && Number.isNaN(filters.semMax)) filters.semMax = null;
}

function openFilterDialog() {
  buildFilterPanel();
  /** @type {HTMLDialogElement} */ ($("#dlg-filter"))?.showModal();
}

function wireDialogs() {
  const dlgF = /** @type {HTMLDialogElement} */ ($("#dlg-filter"));
  const dlgD = /** @type {HTMLDialogElement} */ ($("#dlg-detail"));
  dlgF?.addEventListener("click", (e) => {
    if (e.target === dlgF) dlgF.close();
  });
  dlgD?.addEventListener("click", (e) => {
    if (e.target === dlgD) closeDetail();
  });
  dlgD?.addEventListener("click", (e) => {
    const row = e.target instanceof Element ? e.target.closest(".course-sample-row") : null;
    if (!row || !detailProgramId) return;
    e.stopPropagation();
    const idx = Number(row.getAttribute("data-course-index"));
    if (!Number.isFinite(idx) || idx < 0) return;
    const prog = findProgram(detailProgramId);
    const courses = prog?.curriculum?.core_courses;
    if (!Array.isArray(courses) || !courses[idx]) return;
    openCourseDialog(courses[idx]);
  });
  dlgD?.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const t = e.target;
    if (!(t instanceof Element)) return;
    const row = t.closest(".course-sample-row");
    if (!row || !detailProgramId) return;
    e.preventDefault();
    const idx = Number(row.getAttribute("data-course-index"));
    if (!Number.isFinite(idx) || idx < 0) return;
    const prog = findProgram(detailProgramId);
    const courses = prog?.curriculum?.core_courses;
    if (!Array.isArray(courses) || !courses[idx]) return;
    openCourseDialog(courses[idx]);
  });

  const dlgC = /** @type {HTMLDialogElement} */ ($("#dlg-course"));
  dlgC?.addEventListener("click", (e) => {
    if (e.target === dlgC) closeCourseDialog();
  });
  $("#btn-course-close")?.addEventListener("click", () => closeCourseDialog());

  $("#btn-filter-close")?.addEventListener("click", () => dlgF?.close());
  $("#btn-filter-done")?.addEventListener("click", () => {
    readSemInputsFromFilterPanel();
    dlgF?.close();
    renderTable();
  });
  $("#btn-filter-clear")?.addEventListener("click", () => {
    clearFilterSets();
    buildFilterPanel();
    renderTable();
  });
  $("#btn-detail-close")?.addEventListener("click", () => closeDetail());
  $("#btn-filter")?.addEventListener("click", () => openFilterDialog());
}

async function loadViewerCategories() {
  const el = document.getElementById("viewer-categories");
  const txt = el?.textContent?.trim();
  if (txt) {
    try {
      categories = JSON.parse(txt);
      return;
    } catch (e) {
      console.warn(e);
    }
  }
  try {
    const r = await fetch("dev/viewer-categories.json");
    if (r.ok) {
      categories = await r.json();
      return;
    }
  } catch {
    /* ignore */
  }
  categories = {};
}

async function loadSample() {
  await clearPersistedCorpus();
  try {
    const r = await fetch("dev/sample-corpus.json");
    if (!r.ok) throw new Error(String(r.status));
    const data = await r.json();
    corpus = normalizeCorpus(data);
    detailProgramId = null;
    editBaseline = null;
    editMode = false;
    clearFilterSets();
    setStatus(`Loaded sample (${corpus.programs.length} programs).`);
    renderTable();
  } catch (e) {
    setStatus("Could not load sample (serve viewer via static server, e.g. python -m http.server).");
    console.error(e);
  }
}

$("#btn-load-corpus")?.addEventListener("click", () => {
  void openCorpusPicker();
});

$("#file-corpus")?.addEventListener("change", async (e) => {
  const input = e.target;
  if (!(input instanceof HTMLInputElement) || !input.files?.length) return;
  const file = input.files[0];
  await ingestCorpusFile(file, null);
  input.value = "";
});

$("#btn-sample")?.addEventListener("click", () => loadSample());

document.querySelectorAll(".th-sort").forEach((btn) => {
  btn.addEventListener("click", () => {
    const k = btn.getAttribute("data-sort");
    if (k) toggleSort(k);
  });
});

$("#btn-edit-toggle")?.addEventListener("click", () => enterEditMode());
$("#btn-edit-cancel")?.addEventListener("click", () => cancelEditMode());
$("#btn-export-patch")?.addEventListener("click", () => exportPatch());

function bootEmbeddedCorpus() {
  const el = document.getElementById("corpus-data");
  if (!el || el.getAttribute("type") !== "application/json") return;
  try {
    const data = JSON.parse(el.textContent || "{}");
    corpus = normalizeCorpus(data);
    detailProgramId = null;
    editBaseline = null;
    editMode = false;
    clearFilterSets();
    setStatus(`Loaded embedded corpus (${corpus.programs.length} programs).`);
    renderTable();
  } catch (e) {
    console.error(e);
  }
}

async function boot() {
  await loadViewerCategories();
  wireDialogs();
  bootEmbeddedCorpus();
  if (!corpus) {
    void tryRestorePersistedCorpus().then((ok) => {
      if (!ok && !corpus) {
        const hint = supportsFilePicker()
          ? "Load a corpus JSON file (Chrome/Edge remembers it across refreshes) or the dev sample."
          : "Load a corpus JSON file or the dev sample.";
        setStatus(hint);
      }
    });
  }
}

void boot();
