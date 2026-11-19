#!/usr/bin/env node
/**
 * NV8 protocol-recovery runner template.
 *
 * Copy into the TARGET project (not into the NV8 repo, not into the skill dir).
 * Declare the dependency first:
 *
 *   package.json ->  "dependencies": { "nv8": "file:D:/path/to/nv8" }
 *   npm install
 *
 * Run (host script using only EdgeSandbox does NOT need the vm-modules flag,
 * but it is harmless and keeps createNv8 usable if you switch later):
 *
 *   node nv8_runner.mjs
 */

import { readFile } from 'node:fs/promises';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { EdgeSandbox } from 'nv8';

// ─────────────────────────────────────────────────────────────────────────────
// 1. EDIT THIS BLOCK — target-specific facts only.
// ─────────────────────────────────────────────────────────────────────────────

const TARGET = {
  /** Page the scripts expect. Keep the SPA route the signed request originates from. */
  url: 'https://target.test/list',
  /** Inline HTML when the bundle needs specific DOM. Read the real page HTML if it matters. */
  html: '<!doctype html><html><body><main id="app"></main></body></html>',

  /** Local copies of the target's scripts, fetched in the SAME session as the cookies. */
  scripts: [
    // './js_reverse_cache/target/main.min.js',
  ],

  /**
   * Offline replay records. The runtime NEVER falls back to the real network.
   * Add one record per request the bundle makes during bootstrap.
   */
  replay: [
    // {
    //   request: { method: 'GET', url: 'https://target.test/api/seed' },
    //   response: { status: 200, headers: { 'content-type': 'application/json' }, body: '{"k":"v"}' },
    // },
  ],

  /**
   * The expression that drives the signer. Prefer calling the entry the trace
   * already proved, rather than re-deriving it here.
   */
  invoke: `
    (() => {
      // Example: call the recovered entry and return the signed payload.
      // const sign = globalThis.__entry;
      // return JSON.stringify({ sign: sign({ a: 1 }), ts: Date.now() });
      return JSON.stringify({ note: 'replace invoke with the recovered entry' });
    })()
  `,
};

/** Everything generated at runtime lands in the executing project's workspace. */
const CACHE_DIR = path.resolve(process.cwd(), 'js_reverse_cache', 'tasks', 'TEMPLATE');

// ─────────────────────────────────────────────────────────────────────────────
// 2. Runner
// ─────────────────────────────────────────────────────────────────────────────

mkdirSync(CACHE_DIR, { recursive: true });

const report = [];
const say = (label, value) => {
  const line = `${label}: ${typeof value === 'string' ? value : JSON.stringify(value)}`;
  report.push(line);
  console.log(line);
};

/**
 * Frozen NV8 values are authoritative: they are the contract the target saw.
 * Probe these BEFORE touching the signer, so a wrong environment is caught early.
 */
const IDENTITY_PROBES = {
  userAgent: 'navigator.userAgent',
  platform: 'navigator.platform',
  language: 'navigator.language',
  screen: 'screen.width + "x" + screen.height + " dpr=" + devicePixelRatio',
  webdriver: 'String(navigator.webdriver)',
  uaBrands: 'navigator.userAgentData ? navigator.userAgentData.brands.map(b=>b.brand+"/"+b.version).join(" | ") : "absent"',
  nativeToString: 'Function.prototype.toString.call(document.addEventListener)',
  isolatedProcess: 'typeof process',
};

const sandbox = await EdgeSandbox.create({
  page: { url: TARGET.url, html: TARGET.html },
  replay: TARGET.replay,
  // MEASURED: first create() takes ~20s (subprocess spawn + full surface assembly).
  // The 5000ms default fails every time. Always raise it.
  limits: { timeoutMs: 60_000 },
});

try {
  // ── Step 1: environment sanity ────────────────────────────────────────────
  console.log('\n=== environment ===');
  for (const [label, expr] of Object.entries(IDENTITY_PROBES)) {
    try {
      const r = await sandbox.evaluate(expr);
      say(label, r?.value);
    } catch (e) {
      say(label, `FAILED ${e.constructor.name}: ${e.message}`);
    }
  }

  // ── Step 2: load the target bundle AS SOURCE (never `node bundle.js`) ─────
  console.log('\n=== load target scripts ===');
  for (const rel of TARGET.scripts) {
    const abs = path.resolve(process.cwd(), rel);
    if (!existsSync(abs)) {
      say(`skip ${rel}`, 'not found');
      continue;
    }
    const source = await readFile(abs, 'utf8');
    try {
      await sandbox.evaluate(source);
      say(`loaded ${path.basename(rel)}`, `${source.length} bytes`);
    } catch (e) {
      say(`load ${path.basename(rel)}`, `FAILED ${e.constructor.name}: ${e.message}`);
    }
  }

  // ── Step 3: drive the signer ─────────────────────────────────────────────
  console.log('\n=== invoke ===');
  try {
    const r = await sandbox.evaluate(TARGET.invoke);
    say('result', r?.value ?? r);
  } catch (e) {
    say('invoke', `FAILED ${e.constructor.name}: ${e.message}`);
  }

  // ── Step 4: wire evidence — the actual recovery output ───────────────────
  console.log('\n=== networkRequests ===');
  const requests = await sandbox.networkRequests();
  say('count', Array.isArray(requests) ? requests.length : typeof requests);
  if (Array.isArray(requests)) {
    for (const [i, req] of requests.entries()) {
      // An offline replay MISS still lands here. That is useful: it proves what
      // the script tried to request even when we have no response for it.
      say(`[${i}]`, JSON.stringify(req).slice(0, 400));
    }
    writeFileSync(path.join(CACHE_DIR, 'network.jsonl'), requests.map((r) => JSON.stringify(r)).join('\n'), 'utf8');
  }

  // ── Step 5: resources / diagnosis ────────────────────────────────────────
  console.log('\n=== resources ===');
  say('resources', JSON.stringify(await sandbox.resources()).slice(0, 300));
} finally {
  // close() is idempotent; always release the subprocess.
  await sandbox.close();
}

writeFileSync(path.join(CACHE_DIR, 'report.md'), report.join('\n'), 'utf8');
console.log(`\nreport -> ${path.join(CACHE_DIR, 'report.md')}`);
