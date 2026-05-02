/**
 * Bundle peer-atlas-viewer into a single HTML file for sharing.
 * Usage: node peer-atlas-viewer/tools/bundle.mjs [optional/path/to/corpus.json]
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const viewerRoot = path.resolve(__dirname, "..");
const indexPath = path.join(viewerRoot, "index.html");
const distDir = path.join(viewerRoot, "dist");
const outPath = path.join(distDir, "atlas-viewer.html");

function readText(p) {
  return fs.readFileSync(p, "utf8");
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
  out = out.replace(
    sm[0],
    `<script type="module">\n${js}\n</script>`
  );
  return out;
}

function optionalCorpusEmbed(html, corpusPath) {
  if (!corpusPath) return html;
  const json = readText(corpusPath);
  JSON.parse(json);
  const embed = `\n<script id="corpus-data" type="application/json">\n${json}\n</script>\n`;
  return html.replace("</body>", `${embed}</body>`);
}

function main() {
  const corpusArg = process.argv[2];
  let html = readText(indexPath);
  html = inlineAssets(html);
  html = optionalCorpusEmbed(html, corpusArg && path.resolve(corpusArg));
  fs.mkdirSync(distDir, { recursive: true });
  fs.writeFileSync(outPath, html, "utf8");
  console.log(`Wrote ${outPath}`);
}

main();
