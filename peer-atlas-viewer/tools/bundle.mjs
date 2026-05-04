/**
 * Bundle peer-atlas-viewer into a single HTML file for sharing.
 * Usage: node peer-atlas-viewer/tools/bundle.mjs [optional/path/to/corpus.json]
 *
 * Output is **minified** (inter-tag whitespace removed; CSS comments/whitespace reduced;
 * module script gets conservative blank-line / trailing-space trimming). Dev-only controls
 * between `<!-- peer-atlas:bundle-remove:start/end -->` in index.html are omitted from dist.
 *
 * When a corpus path is passed, embeds a **slim** corpus (table + drilldown fields only)
 * and inlined **viewer_categories** (enums from categories_and_rules). **Course-type**
 * icons under `icons/course-types/*.svg` are embedded as base64 data URLs for offline use.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { slimCorpus, loadViewerCategories } from "./slim-corpus-for-viewer.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const viewerRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(viewerRoot, "..");
const indexPath = path.join(viewerRoot, "index.html");
const distDir = path.join(viewerRoot, "dist");
const outPath = path.join(distDir, "atlas-viewer.html");

const BUNDLE_REMOVE_START = "<!-- peer-atlas:bundle-remove:start -->";
const BUNDLE_REMOVE_END = "<!-- peer-atlas:bundle-remove:end -->";

function readText(p) {
  return fs.readFileSync(p, "utf8");
}

/**
 * Remove dev toolbar region (Load corpus / file input / Load sample) from the template.
 * @param {string} html
 */
function stripBundleRemoveRegion(html) {
  const i = html.indexOf(BUNDLE_REMOVE_START);
  const j = html.indexOf(BUNDLE_REMOVE_END);
  if (i === -1 || j === -1 || j < i) {
    throw new Error(
      `Missing bundle-remove markers in index.html (expected ${BUNDLE_REMOVE_START} … ${BUNDLE_REMOVE_END}).`,
    );
  }
  return html.slice(0, i) + html.slice(j + BUNDLE_REMOVE_END.length);
}

function inlineAssets(html) {
  let out = html;
  const linkRe = /<link\s+[^>]*rel=["']stylesheet["'][^>]*href=["']([^"']+)["'][^>]*>/i;
  const m = out.match(linkRe);
  if (!m) throw new Error("No stylesheet link found in index.html");
  const cssPath = path.resolve(viewerRoot, m[1]);
  const css = readText(cssPath);
  out = out.replace(m[0], `<style>\n${css}\n</style>`);

  const scriptRe =
    /<script\s+[^>]*type=["']module["'][^>]*src=["']([^"']+)["'][^>]*>\s*<\/script>/i;
  const sm = out.match(scriptRe);
  if (!sm) throw new Error("No module script tag found in index.html");
  const jsPath = path.resolve(viewerRoot, sm[1]);
  const js = readText(jsPath);
  out = out.replace(sm[0], `<script type="module">\n${js}\n</script>`);
  return out;
}

/**
 * @param {string} html
 * @param {string} [corpusPath]
 */
function embedCorpusAndCategories(html, corpusPath) {
  if (!corpusPath) return html;
  const raw = JSON.parse(readText(corpusPath));
  const slim = slimCorpus(raw);
  const corpusJson = JSON.stringify(slim);
  const categories = loadViewerCategories(repoRoot);
  const catJson = JSON.stringify(categories);
  const embed = `<script id="corpus-data" type="application/json">${corpusJson}</script><script id="viewer-categories" type="application/json">${catJson}</script>`;
  return html.replace("</body>", `${embed}</body>`);
}

/**
 * Embed course_type SVGs as base64 data URLs in JSON (stable single-file viewer; avoids `</script>` issues).
 * @param {string} html
 */
function embedCourseTypeIcons(html) {
  const dir = path.join(viewerRoot, "icons", "course-types");
  if (!fs.existsSync(dir)) return html;
  /** @type {Record<string, string>} */
  const map = {};
  for (const name of fs.readdirSync(dir)) {
    if (!name.toLowerCase().endsWith(".svg")) continue;
    const id = name.replace(/\.svg$/i, "");
    const buf = fs.readFileSync(path.join(dir, name));
    map[id] = `data:image/svg+xml;base64,${buf.toString("base64")}`;
  }
  if (Object.keys(map).length === 0) return html;
  const json = JSON.stringify(map);
  const tag = `<script id="course-type-icons" type="application/json">${json}</script>`;
  return html.replace("</body>", `${tag}</body>`);
}

/** Minify HTML segments (not inside script/style). */
function minifyHtmlFragment(s) {
  return s
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/>\s+</g, "><")
    .trim();
}

/** Safe CSS shrink: strip block comments and collapse whitespace. */
function minifyCssLite(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\s+/g, " ").trim();
}

/** Conservative JS shrink for inlined module code (no semantic transforms). */
function minifyModuleJsLite(js) {
  return js
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+$/gm, "")
    .replace(/\n{4,}/g, "\n\n");
}

/**
 * @param {string} full
 */
function minifyBlockedTag(full) {
  const ms = full.match(/^<script(\b[^>]*)>([\s\S]*?)<\/script>$/i);
  if (ms) {
    const attrs = ms[1];
    const body = ms[2];
    const isJson = /\btype\s*=\s*["']application\/json["']/i.test(attrs);
    if (isJson) {
      try {
        const compact = JSON.stringify(JSON.parse(body.trim()));
        return `<script${attrs}>${compact}</script>`;
      } catch {
        return full;
      }
    }
    return `<script${attrs}>${minifyModuleJsLite(body)}</script>`;
  }
  const mz = full.match(/^<style(\b[^>]*)>([\s\S]*?)<\/style>$/i);
  if (mz) {
    return `<style${mz[1]}>${minifyCssLite(mz[2])}</style>`;
  }
  return full;
}

/**
 * Minify full document: HTML between tags, plus style / script bodies with safe rules.
 * @param {string} html
 */
function minifyBundledHtml(html) {
  const re = /<(?:script|style)\b[^>]*>[\s\S]*?<\/(?:script|style)>/gi;
  let out = "";
  let last = 0;
  let m;
  while ((m = re.exec(html)) !== null) {
    out += minifyHtmlFragment(html.slice(last, m.index));
    out += minifyBlockedTag(m[0]);
    last = re.lastIndex;
  }
  out += minifyHtmlFragment(html.slice(last));
  return out;
}

function main() {
  const corpusArg = process.argv[2];
  let html = readText(indexPath);
  html = stripBundleRemoveRegion(html);
  html = inlineAssets(html);
  html = embedCorpusAndCategories(html, corpusArg && path.resolve(corpusArg));
  html = embedCourseTypeIcons(html);
  html = minifyBundledHtml(html);
  fs.mkdirSync(distDir, { recursive: true });
  fs.writeFileSync(outPath, html, "utf8");
  console.log(`Wrote ${outPath}`);
}

main();
