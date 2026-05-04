/**
 * Write peer-atlas-viewer/dev/viewer-categories.json from repo categories_and_rules.
 * Run from repo root: node peer-atlas-viewer/tools/write-dev-catalog.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadViewerCategories } from "./slim-corpus-for-viewer.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const viewerRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(viewerRoot, "..");
const outPath = path.join(viewerRoot, "dev", "viewer-categories.json");

const data = loadViewerCategories(repoRoot);
fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, JSON.stringify(data, null, 2), "utf8");
console.log(`Wrote ${outPath}`);
