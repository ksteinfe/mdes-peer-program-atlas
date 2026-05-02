const $ = (sel) => document.querySelector(sel);

const LS_LAST_CORPUS_LABEL = "peer-atlas-last-corpus-label";
const LS_LAST_CORPUS_PATH = "peer-atlas-last-corpus-path";
const IDB_NAME = "peer-atlas-viewer";
const IDB_STORE = "fs-handles";
const IDB_CORPUS_KEY = "corpusFile";

/** @type {{ corpus_metadata?: object, programs: object[] } | null} */
let corpus = null;
/** @type {string | null} */
let selectedId = null;
/** @type {object[]} */
let patchQueue = [];

function setStatus(msg) {
  const el = $("#status");
  if (el) el.textContent = msg;
}

function normalizeCorpus(data) {
  if (!data || typeof data !== "object") throw new Error("Invalid JSON root");
  if (!Array.isArray(data.programs)) {
    throw new Error("Expected top-level 'programs' array");
  }
  return data;
}

function supportsFilePicker() {
  return typeof window.showOpenFilePicker === "function";
}

function rememberCorpusLabel(file) {
  const name = file?.name || "corpus.json";
  const path =
    typeof file?.path === "string" && file.path.length > 0 ? file.path : "";
  try {
    localStorage.setItem(LS_LAST_CORPUS_LABEL, name);
    if (path) localStorage.setItem(LS_LAST_CORPUS_PATH, path);
    else localStorage.removeItem(LS_LAST_CORPUS_PATH);
  } catch {
    /* quota or private mode */
  }
}

function openIdb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NAME, 1);
    req.onerror = () => reject(req.error);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(IDB_STORE)) {
        db.createObjectStore(IDB_STORE);
      }
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

/**
 * @param {string} key
 * @param {unknown} value
 */
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
  selectedId = null;
  patchQueue = [];
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
  renderDetail();
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
    selectedId = null;
    setStatus("Invalid or unexpected JSON.");
    console.error(err);
    renderTable();
    renderDetail();
  }
}

/**
 * Restore corpus from a persisted handle.
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
    setStatus(
      "Saved corpus could not be read. Use Load corpus… to pick a valid JSON file."
    );
    return false;
  }
  setStatus(
    "Saved corpus needs permission after refresh. Click Load corpus… and pick the same file once."
  );
  return false;
}

async function openCorpusPicker() {
  if (supportsFilePicker()) {
    try {
      /** @type {OpenFilePickerOptions} */
      const opts = {
        multiple: false,
        excludeAcceptAllOption: false,
        types: [
          {
            description: "JSON",
            accept: { "application/json": [".json"] },
          },
        ],
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

function pick(obj, path, fallback = "") {
  let cur = obj;
  for (const key of path) {
    if (cur == null || typeof cur !== "object") return fallback;
    cur = cur[key];
  }
  if (cur == null || cur === "") return fallback;
  return String(cur);
}

function rowCells(p) {
  const id = p.program_id ?? "";
  const ident = p.identity ?? {};
  const loc = ident.location ?? {};
  const pos = (p.positioning?.derived_features) ?? {};
  const dur = (p.duration?.derived_features) ?? {};
  const cost = (p.degree_cost?.derived_features) ?? {};
  const ver = p.verification ?? {};
  return {
    id,
    institution: pick(ident, ["institution_name"]),
    program: pick(ident, ["program_name"]),
    degree: pick(ident, ["degree_type"]),
    country: pick(loc, ["country"]),
    region: pick(loc, ["state_or_region"]),
    hostModel: pick(ident, ["host_academic_model"]),
    positioning: Array.isArray(pos.positioning_tags)
      ? pos.positioning_tags.filter((t) => t != null && String(t).trim()).join(", ")
      : "",
    durationCat: pick(dur, ["duration_category"]),
    berkSem: dur.length_in_berkeley_semesters ?? "",
    costUsd: cost.comparison_cost_usd ?? "",
    verification: pick(ver, ["status"]),
  };
}

function renderTable() {
  const tbody = $("#program-table tbody");
  if (!tbody || !corpus) return;
  const q = ($("#filter")?.value || "").trim().toLowerCase();
  tbody.replaceChildren();
  for (const p of corpus.programs) {
    const c = rowCells(p);
    const hay = [c.id, c.institution, c.program, c.degree].join(" ").toLowerCase();
    if (q && !hay.includes(q)) continue;
    const tr = document.createElement("tr");
    tr.tabIndex = 0;
    if (c.id === selectedId) tr.setAttribute("aria-selected", "true");
    tr.dataset.programId = c.id;
    const vals = [
      c.id,
      c.institution,
      c.program,
      c.degree,
      c.country,
      c.region,
      c.hostModel,
      c.positioning,
      c.durationCat,
      c.berkSem,
      c.costUsd,
      c.verification,
    ];
    for (const v of vals) {
      const td = document.createElement("td");
      td.textContent = v === null || v === undefined ? "" : String(v);
      tr.appendChild(td);
    }
    tr.addEventListener("click", () => selectProgram(c.id));
    tr.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        selectProgram(c.id);
      }
    });
    tbody.appendChild(tr);
  }
}

function esc(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderPrimitive(path, value) {
  const v =
    value === null || value === undefined
      ? ""
      : typeof value === "object"
        ? JSON.stringify(value)
        : String(value);
  return `<div class="kv"><div>${esc(path)}</div><div data-path="${esc(
    path
  )}">${esc(v)}</div></div>`;
}

function renderObjectSection(title, obj, prefix) {
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
    return `<div class="section"><h3>${esc(title)}</h3>${renderPrimitive(
      prefix,
      obj
    )}</div>`;
  }
  let inner = "";
  for (const [k, v] of Object.entries(obj)) {
    const p = prefix ? `${prefix}.${k}` : k;
    if (v != null && typeof v === "object" && !Array.isArray(v)) {
      inner += `<div class="nested"><strong>${esc(k)}</strong>${renderObjectBlock(
        p,
        v
      )}</div>`;
    } else if (Array.isArray(v)) {
      inner += `<div class="nested"><strong>${esc(k)}</strong>`;
      inner += `<pre data-path="${esc(p)}">${esc(JSON.stringify(v, null, 2))}</pre></div>`;
    } else {
      inner += renderPrimitive(p, v);
    }
  }
  return `<div class="section"><h3>${esc(title)}</h3>${inner}</div>`;
}

function renderObjectBlock(prefix, obj) {
  let inner = "";
  for (const [k, v] of Object.entries(obj)) {
    const p = `${prefix}.${k}`;
    if (v != null && typeof v === "object" && !Array.isArray(v)) {
      inner += `<div class="nested"><strong>${esc(k)}</strong>${renderObjectBlock(
        p,
        v
      )}</div>`;
    } else if (Array.isArray(v)) {
      inner += `<div class="nested"><strong>${esc(k)}</strong><pre data-path="${esc(
        p
      )}">${esc(JSON.stringify(v, null, 2))}</pre></div>`;
    } else {
      inner += renderPrimitive(p, v);
    }
  }
  return `<div class="kv-block">${inner}</div>`;
}

function renderDetail() {
  const root = $("#detail-root");
  const empty = $("#detail-empty");
  const patch = $("#patch-actions");
  if (!root || !empty || !patch) return;
  if (!selectedId || !corpus) {
    root.hidden = true;
    empty.hidden = false;
    patch.hidden = true;
    return;
  }
  const p = corpus.programs.find((x) => x.program_id === selectedId);
  if (!p) {
    root.hidden = true;
    empty.hidden = false;
    patch.hidden = true;
    return;
  }
  empty.hidden = true;
  root.hidden = false;
  patch.hidden = false;
  const blocks = [
    renderObjectSection("Identity", p.identity, "identity"),
    renderObjectSection("Positioning", p.positioning, "positioning"),
    renderObjectSection("Duration", p.duration, "duration"),
    renderObjectSection("Degree cost", p.degree_cost, "degree_cost"),
    renderObjectSection("Curriculum", p.curriculum, "curriculum"),
    renderObjectSection("Verification", p.verification, "verification"),
  ];
  root.innerHTML = blocks.join("");
  renderPatchQueue();
}

function selectProgram(id) {
  selectedId = id;
  renderTable();
  renderDetail();
}

function renderPatchQueue() {
  const ul = $("#patch-queue");
  if (!ul) return;
  ul.replaceChildren();
  for (const ch of patchQueue) {
    const li = document.createElement("li");
    li.textContent = `${ch.program_id}  ${ch.path}`;
    ul.appendChild(li);
  }
}

function queueVerificationHumanReviewed() {
  if (!corpus || !selectedId) {
    setStatus("Select a program first.");
    return;
  }
  const p = corpus.programs.find((x) => x.program_id === selectedId);
  if (!p) return;
  const cur = p.verification?.status ?? null;
  patchQueue.push({
    program_id: selectedId,
    path: "verification.status",
    old_value: cur,
    new_value: "human_reviewed",
    notes: "Queued from viewer",
  });
  setStatus("Change queued.");
  renderPatchQueue();
}

function isoDate() {
  return new Date().toISOString().slice(0, 10);
}

function exportPatch() {
  const createdBy = $("#meta-by")?.value?.trim() || "";
  const notes = $("#meta-notes")?.value?.trim() || "";
  const patch = {
    patch_metadata: {
      created_at: isoDate(),
      created_by: createdBy,
      source_corpus_name: "MDes Peer Program Comparator Corpus",
      notes,
    },
    changes: patchQueue.map(({ program_id, path, old_value, new_value, notes: n }) => ({
      program_id,
      path,
      old_value,
      new_value,
      ...(n ? { notes: n } : {}),
    })),
  };
  const blob = new Blob([JSON.stringify(patch, null, 2)], {
    type: "application/json",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `patch_${isoDate()}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
  setStatus("Patch downloaded.");
}

async function loadSample() {
  await clearPersistedCorpus();
  try {
    const r = await fetch("dev/sample-corpus.json");
    if (!r.ok) throw new Error(String(r.status));
    const data = await r.json();
    corpus = normalizeCorpus(data);
    selectedId = null;
    patchQueue = [];
    setStatus(`Loaded sample (${corpus.programs.length} programs).`);
    renderTable();
    renderDetail();
  } catch (e) {
    setStatus(
      "Could not load sample (serve viewer via static server, e.g. python -m http.server)."
    );
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
  await ingestCorpusFile(file, null, file.name);
  input.value = "";
});

$("#filter")?.addEventListener("input", () => renderTable());
$("#btn-sample")?.addEventListener("click", () => loadSample());
$("#btn-queue-reviewed")?.addEventListener("click", () =>
  queueVerificationHumanReviewed()
);
$("#btn-export-patch")?.addEventListener("click", () => exportPatch());

function bootEmbeddedCorpus() {
  const el = document.getElementById("corpus-data");
  if (!el || el.getAttribute("type") !== "application/json") return;
  try {
    const data = JSON.parse(el.textContent || "{}");
    corpus = normalizeCorpus(data);
    selectedId = null;
    patchQueue = [];
    setStatus(`Loaded embedded corpus (${corpus.programs.length} programs).`);
    renderTable();
    renderDetail();
  } catch (e) {
    console.error(e);
  }
}

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
