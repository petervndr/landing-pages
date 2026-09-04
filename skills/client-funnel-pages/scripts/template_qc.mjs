// template_qc.mjs — fold-gate + embed QC for the HOUSE TEMPLATE itself.
//
// Why this exists: the most expensive recurring funnel-qc failure (primary CTA below
// the fold on short phones) turned out to be a property of the house template, not of
// any one client build — it kept getting re-found and re-fixed per client because
// nothing ever tested the template centrally. This script does: it builds the bundled
// SYAF example brief from the raw templates, serves the standalone pages, and runs
// funnel-qc's fold_check.js across the full 8-device matrix on every hero-CTA page.
//
// Run it BEFORE publishing any template/CSS change:
//   node scripts/template_qc.mjs
//
// Exits non-zero on any BLOCKING failure (CTA cut at any viewport) — fail loudly.
// Dependencies: python3 (build + http server), Chrome, playwright/playwright-core
// (same resolution as style-creator's inspect_site.mjs).

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn, execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require_ = createRequire(import.meta.url);
const SKILL_DIR = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

function resolvePlaywright() {
  const names = ["playwright", "playwright-core"];
  const roots = [
    process.env.PLAYWRIGHT_NODE_MODULES,
    `${process.env.HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules`,
  ].filter(Boolean);
  for (const n of names) {
    try { return require_(n); } catch {}
    for (const r of roots) { try { return createRequire(path.join(r, "noop.js"))(n); } catch {} }
  }
  console.error("✗ playwright not found. npm install --prefix /tmp/pw playwright-core, then " +
                "re-run with PLAYWRIGHT_NODE_MODULES=/tmp/pw/node_modules");
  process.exit(1);
}
function chromePath() {
  for (const p of [process.env.CHROME_PATH,
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium"].filter(Boolean))
    if (fs.existsSync(p)) return p;
  console.error("✗ No Chrome found. Set CHROME_PATH."); process.exit(1);
}

// The funnel-qc 8-device matrix (viewport CSS px, chrome/scaling already subtracted).
const MATRIX = [
  ["iPhone SE", 375, 553], ["iPhone 14/15/16", 390, 664], ["iPhone Pro Max", 430, 752],
  ["iPad mini", 744, 1026], ["iPad Air", 820, 1073], ["1080p laptop", 1536, 734],
  ["1440p laptop", 1707, 830], ["4K desktop", 1920, 970],
];
// Pages with a fold-critical hero CTA (confirmation/legal/404 are N/A per doctrine).
const PAGES = ["vsl-page.html", "opt-in.html", "book-a-call.html"];
const TYPEFORM_MOBILE_MATRIX = [
  ["iPhone SE", 375, 553], ["iPhone 14/15/16", 390, 664],
  ["iPhone Pro Max", 430, 752], ["iPad mini", 744, 1026],
  ["767px breakpoint", 767, 900],
];

// 1. Build the example brief from the raw templates into a temp dir.
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "template-qc-"));
const brief = JSON.parse(
  // strip // comments (string-aware enough for the bundled example)
  fs.readFileSync(path.join(SKILL_DIR, "assets/brand-brief.example.jsonc"), "utf8")
    .replace(/^\s*\/\/.*$/gm, "").replace(/([^:"])\/\/[^"\n]*$/gm, "$1")
);
brief.prior_art_checked = true;   // template QC, not a client build
brief.brand_lock_confirmed = true;
const briefPath = path.join(tmp, "brief.jsonc");
fs.writeFileSync(briefPath, JSON.stringify(brief, null, 2));
execFileSync("python3", [path.join(SKILL_DIR, "scripts/build_funnel.py"),
  briefPath, "--out", tmp, "--allow-out-anywhere"], { stdio: "inherit" });
const standalone = fs.readdirSync(tmp)
  .map((d) => path.join(tmp, d, "standalone")).find((p) => fs.existsSync(p));
if (!standalone) { console.error("✗ build produced no standalone/ dir"); process.exit(1); }

// 2. Serve over http (embeds mis-render on file:// and can shift hero geometry).
const PORT = 8123;
const server = spawn("python3", ["-m", "http.server", String(PORT)], { cwd: standalone, stdio: "ignore" });
await new Promise((r) => setTimeout(r, 1200));

// 3. Fold-check every hero-CTA page at every viewport, reusing funnel-qc's script.
const foldSrc = fs.readFileSync(
  path.join(SKILL_DIR, "../funnel-qc/scripts/fold_check.js"), "utf8");
const { chromium } = resolvePlaywright();
const browser = await chromium.launch({ headless: true, executablePath: chromePath(), args: ["--disable-gpu"] });

let blocking = 0, warnings = 0;
const report = [];
for (const pageName of PAGES) {
  if (!fs.existsSync(path.join(standalone, pageName))) continue;
  for (const [device, w, h] of MATRIX) {
    const page = await browser.newPage({ viewport: { width: w, height: h } });
    await page.goto(`http://localhost:${PORT}/${pageName}`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(1200);
    const res = await page.evaluate(foldSrc);
    await page.close();
    const cta = (res.rows || []).find((r) => r.severity === "BLOCKING");
    const line = `${pageName} @ ${w}x${h} (${device}): ${res.gate}`;
    report.push(line);
    if (!res.gate.startsWith("PASS")) { blocking++; console.log("  ❌ " + line); }
    else {
      const high = (res.rows || []).filter((r) => r.severity === "high" && r.status.startsWith("FAIL"));
      if (high.length) { warnings++; console.log("  ⚠  " + line + " — " + high.map((r) => `${r.element} ${r.status}`).join(", ")); }
      else console.log("  ✅ " + line + (cta ? ` — CTA ${cta.status}` : ""));
    }
  }
}

// 4. Regression-gate the full Typeform application's mobile canvas. Typeform's
// launch UI clips when the generated iframe is allowed to collapse below 560px.
for (const [device, w, h] of TYPEFORM_MOBILE_MATRIX) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  await page.goto(`http://localhost:${PORT}/vsl-page.html`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(500);
  const tf = await page.evaluate(() => {
    const section = document.querySelector(".book--typeform");
    const wrap = section?.querySelector(".wrap");
    const shell = section?.querySelector(".typeform-shell");
    const live = shell?.querySelector(":scope > [data-tf-live]");
    const iframe = shell?.querySelector("iframe");
    const snap = (el) => el ? {
      height: el.getBoundingClientRect().height,
      minHeight: getComputedStyle(el).minHeight,
      overflow: getComputedStyle(el).overflow,
    } : null;
    const shellStyle = shell ? getComputedStyle(shell) : null;
    const before = shell ? getComputedStyle(shell, "::before") : null;
    const after = shell ? getComputedStyle(shell, "::after") : null;
    return {
      section: snap(section), wrap: snap(wrap), shell: snap(shell), live: snap(live), iframe: snap(iframe),
      shellClip: shellStyle?.clipPath, shellTransform: shellStyle?.transform,
      beforeDisplay: before?.display, afterDisplay: after?.display,
    };
  });
  await page.close();
  const problems = [];
  if (!tf.section || !tf.wrap || !tf.shell || !tf.live) problems.push("missing canonical Typeform structure");
  for (const [label, item] of [["shell", tf.shell], ["live element", tf.live], ["iframe", tf.iframe]]) {
    if (!item) continue;
    if (Math.abs(item.height - 560) > 1) problems.push(`${label} height ${item.height}px`);
    if (parseFloat(item.minHeight) < 560) problems.push(`${label} min-height ${item.minHeight}`);
  }
  if (tf.section && tf.section.overflow !== "visible") problems.push(`section overflow ${tf.section.overflow}`);
  if (tf.wrap && tf.wrap.overflow !== "visible") problems.push(`wrap overflow ${tf.wrap.overflow}`);
  if (tf.shell && tf.shell.overflow !== "visible") problems.push(`shell overflow ${tf.shell.overflow}`);
  if (tf.shellClip && tf.shellClip !== "none") problems.push(`shell clip-path ${tf.shellClip}`);
  if (tf.shellTransform && tf.shellTransform !== "none") problems.push(`shell transform ${tf.shellTransform}`);
  if (tf.beforeDisplay && tf.beforeDisplay !== "none") problems.push(`::before display ${tf.beforeDisplay}`);
  if (tf.afterDisplay && tf.afterDisplay !== "none") problems.push(`::after display ${tf.afterDisplay}`);
  const line = `Typeform mobile @ ${w}x${h} (${device}): ${problems.length ? "FAIL — " + problems.join(", ") : "PASS — 560px canvas"}`;
  report.push(line);
  if (problems.length) { blocking++; console.log("  ❌ " + line); }
  else console.log("  ✅ " + line);
}

// The mobile override must stop after 767px; desktop retains responsive 62dvh sizing.
{
  const page = await browser.newPage({ viewport: { width: 820, height: 1073 } });
  await page.goto(`http://localhost:${PORT}/vsl-page.html`, { waitUntil: "domcontentloaded", timeout: 30000 });
  const height = await page.locator(".book--typeform .typeform-shell").evaluate((el) => el.getBoundingClientRect().height);
  await page.close();
  const ok = Math.abs(height - 560) > 1;
  const line = `Typeform desktop @ 820x1073: ${ok ? `PASS — responsive height ${height}px` : "FAIL — mobile 560px override leaked"}`;
  report.push(line);
  if (!ok) { blocking++; console.log("  ❌ " + line); }
  else console.log("  ✅ " + line);
}

await browser.close();
server.kill();
fs.writeFileSync(path.join(tmp, "template-qc-report.txt"), report.join("\n") + "\n");

console.log(`\nTemplate QC: ${blocking} blocking failure(s), ${warnings} high-severity warning(s).`);
console.log(`Report: ${path.join(tmp, "template-qc-report.txt")}`);
if (blocking > 0) {
  console.error("\n✗ TEMPLATE QC FAILED — fix assets/templates/styles.css before publishing.");
  process.exit(1);
}
console.log("✓ House template passes the fold gate and Typeform mobile-canvas gate.");
