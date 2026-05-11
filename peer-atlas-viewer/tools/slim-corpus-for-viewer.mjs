/**
 * Slim full corpus JSON to the fields the peer-atlas-viewer table + drilldown + patch editor use.
 * Omits: verification, sources, llm_rationales, dates; keeps base_url and slim core_courses for the viewer.
 *
 * Usage: node slim-corpus-for-viewer.mjs <input.json> [output.json]
 * If output omitted, prints to stdout.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * @param {unknown} c
 * @returns {object | null}
 */
function slimCoreCourse(c) {
  if (!c || typeof c !== "object" || Array.isArray(c)) return null;
  const row = /** @type {Record<string, unknown>} */ (c);
  return {
    course_id: typeof row.course_id === "string" ? row.course_id : String(row.course_id ?? ""),
    course_title: typeof row.course_title === "string" ? row.course_title : String(row.course_title ?? ""),
    primary_type: typeof row.primary_type === "string" ? row.primary_type : String(row.primary_type ?? ""),
    secondary_type:
      row.secondary_type === undefined || row.secondary_type === null
        ? null
        : String(row.secondary_type),
    units_or_credits:
      row.units_or_credits === undefined || row.units_or_credits === null
        ? null
        : Number(row.units_or_credits),
    normalized_unit_weight:
      row.normalized_unit_weight === undefined || row.normalized_unit_weight === null
        ? null
        : Number(row.normalized_unit_weight),
    course_summary: typeof row.course_summary === "string" ? row.course_summary : "",
    source_url:
      row.source_url == null || row.source_url === ""
        ? null
        : String(row.source_url),
    learning_outcomes: Array.isArray(row.learning_outcomes)
      ? row.learning_outcomes.filter((x) => typeof x === "string")
      : [],
  };
}

/**
 * @param {unknown} arr
 */
function slimCoreCourses(arr) {
  if (!Array.isArray(arr)) return [];
  return arr.map(slimCoreCourse).filter(Boolean);
}

/**
 * @param {unknown} p
 * @returns {object | null}
 */
export function slimProgram(p) {
  if (!p || typeof p !== "object" || Array.isArray(p)) return null;
  const prog = /** @type {Record<string, unknown>} */ (p);
  const id = prog.program_id;
  if (typeof id !== "string" || !id) return null;

  const ident =
    prog.identity && typeof prog.identity === "object" ? { ...prog.identity } : {};
  const rawHist = prog.historical;
  const pos = prog.positioning && typeof prog.positioning === "object" ? prog.positioning : {};
  const dur = prog.duration && typeof prog.duration === "object" ? prog.duration : {};
  const deg = prog.degree_cost && typeof prog.degree_cost === "object" ? prog.degree_cost : {};
  const cur = prog.curriculum && typeof prog.curriculum === "object" ? prog.curriculum : {};
  const electives =
    cur.electives && typeof cur.electives === "object" && !Array.isArray(cur.electives)
      ? { summary: cur.electives.summary ?? "" }
      : { summary: "" };

  /** @type {Record<string, unknown>} */
  const duration = {
    length_in_berkeley_semesters:
      dur.length_in_berkeley_semesters === undefined ? null : dur.length_in_berkeley_semesters,
    duration_category: typeof dur.duration_category === "string" ? dur.duration_category : "",
  };
  if (dur.duration_summary != null && dur.duration_summary !== "") {
    duration.duration_summary = dur.duration_summary;
  }

  const baseUrl = typeof prog.base_url === "string" ? prog.base_url.trim() : "";

  return {
    program_id: id,
    base_url: baseUrl,
    identity: ident,
    positioning: {
      positioning_summary: typeof pos.positioning_summary === "string" ? pos.positioning_summary : "",
      positioning_tags: Array.isArray(pos.positioning_tags)
        ? pos.positioning_tags.filter((t) => typeof t === "string" && t.trim())
        : [],
    },
    duration,
    degree_cost: {
      base_currency: typeof deg.base_currency === "string" ? deg.base_currency : "",
      exchange_rate_to_usd:
        deg.exchange_rate_to_usd === undefined || deg.exchange_rate_to_usd === null
          ? null
          : Number(deg.exchange_rate_to_usd),
      comparison_cost_usd:
        deg.comparison_cost_usd === undefined || deg.comparison_cost_usd === null
          ? null
          : Number(deg.comparison_cost_usd),
      cost_base_currency:
        deg.cost_base_currency === undefined || deg.cost_base_currency === null
          ? null
          : Number(deg.cost_base_currency),
      ...(typeof deg.cost_basis === "string" && deg.cost_basis
        ? { cost_basis: deg.cost_basis }
        : {}),
      ...(typeof deg.comparison_cost_method === "string" && deg.comparison_cost_method
        ? { comparison_cost_method: deg.comparison_cost_method }
        : {}),
    },
    curriculum: {
      unit_system: typeof cur.unit_system === "string" ? cur.unit_system : "",
      sequencedness: typeof cur.sequencedness === "string" ? cur.sequencedness : "",
      curriculum_summary: typeof cur.curriculum_summary === "string" ? cur.curriculum_summary : "",
      offers_specialization:
        typeof cur.offers_specialization === "boolean"
          ? cur.offers_specialization
          : cur.offers_specialization == null
            ? false
            : Boolean(cur.offers_specialization),
      electives,
      core_courses: slimCoreCourses(cur.core_courses),
    },
    historical: Array.isArray(rawHist)
      ? rawHist
          .filter((e) => e && typeof e === "object")
          .map((e) => ({
            academic_year:
              typeof e.academic_year === "string"
                ? e.academic_year
                : String(e.academic_year ?? ""),
            degrees_granted:
              e.degrees_granted === undefined || e.degrees_granted === null
                ? null
                : Number(e.degrees_granted),
          }))
      : [],
  };
}

/**
 * @param {unknown} data
 * @returns {{ corpus_metadata?: object, programs: object[] }}
 */
export function slimCorpus(data) {
  if (!data || typeof data !== "object") throw new Error("Invalid JSON root");
  const root = /** @type {Record<string, unknown>} */ (data);
  if (!Array.isArray(root.programs)) throw new Error("Expected top-level 'programs' array");
  const programs = root.programs.map(slimProgram).filter(Boolean);
  /** @type {Record<string, unknown>} */
  const out = { programs };
  if (root.corpus_metadata && typeof root.corpus_metadata === "object") {
    out.corpus_metadata = root.corpus_metadata;
  }
  return /** @type {{ corpus_metadata?: object, programs: object[] }} */ (out);
}

/**
 * @param {string} repoRoot
 */
export function loadViewerCategories(repoRoot) {
  const rulesDir = path.join(repoRoot, "categories_and_rules");
  const names = [
    "positioning_tags.json",
    "course_types.json",
    "host_academic_models.json",
    "duration_categories.json",
    "sequencedness.json",
    "unit_systems.json",
    "cip_codes.json",
  ];
  /** @type {Record<string, unknown>} */
  const out = {};
  for (const n of names) {
    const key = n.replace(/\.json$/i, "");
    const fp = path.join(rulesDir, n);
    if (fs.existsSync(fp)) {
      out[key] = JSON.parse(fs.readFileSync(fp, "utf8"));
    }
  }
  return out;
}

function main() {
  const input = process.argv[2];
  const output = process.argv[3];
  if (!input) {
    console.error("Usage: node slim-corpus-for-viewer.mjs <input.json> [output.json]");
    process.exit(1);
  }
  const raw = JSON.parse(fs.readFileSync(path.resolve(input), "utf8"));
  const slim = slimCorpus(raw);
  const text = JSON.stringify(slim, null, 2);
  if (output) {
    fs.writeFileSync(path.resolve(output), text, "utf8");
    console.error(`Wrote ${path.resolve(output)} (${slim.programs.length} programs)`);
  } else {
    process.stdout.write(text);
  }
}

if (process.argv[1]?.endsWith("slim-corpus-for-viewer.mjs")) {
  main();
}
