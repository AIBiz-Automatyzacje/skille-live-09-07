#!/usr/bin/env node
// lead-fb-radar — pobiera świeże posty z publicznych grup Facebook przez Apify
// (aktor memo23/facebook-public-group-posts-scraper, BEZ cookies — tylko grupy publiczne).
//
// Dwa tryby:
//   (domyślny)     scrapuj posty z ostatnich N h → dedup vs _seen → manifest nowych postów
//   --commit       dopisz URL-e z manifestu do _seen.json (po zakwalifikowaniu przez asystenta)
//
// Świadomie NIE kwalifikujemy tutaj — to robi asystent natywnie (patrz SKILL.md), bez kosztu
// zewnętrznego API i bez drugiego modelu z fallbackiem, jak było w scenariuszu n8n.
//
// Użycie:
//   node fetch.mjs [--hours 24] [--max-per-group 100]
//   node fetch.mjs --commit

import { readFileSync, existsSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const ACTOR = 'memo23~facebook-public-group-posts-scraper';
const API = 'https://api.apify.com/v2';
const POLL_INTERVAL_MS = 6000;
const POLL_TIMEOUT_MS = 30 * 60 * 1000; // 30 min — 2 grupy publiczne to nie doba subów; z zapasem

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = resolve(__dirname, '..');

// Kotwica w ŻYWYM vaulcie (marker .obsidian), nie w realpath symlinka .claude → vault-git
// (martwy klon git, którego Obsidian Sync nie tyka). Ten sam pattern co reddit-news.
function vaultRoot() {
  if (process.env.CLAUDE_CRON_WORKSPACE) return resolve(process.env.CLAUDE_CRON_WORKSPACE);
  let cur = process.cwd();
  for (let i = 0; i < 8; i++) {
    if (existsSync(join(cur, '.obsidian'))) return cur;
    const parent = dirname(cur);
    if (parent === cur) break;
    cur = parent;
  }
  return process.cwd();
}

const VAULT = vaultRoot();
const STATE_DIR = join(VAULT, 'Zasoby/Leady-FB');
const SEEN_FILE = join(STATE_DIR, '_seen.json');
const GROUPS_FILE = join(SKILL_DIR, 'config/grupy.md');
const MANIFEST = join(STATE_DIR, '_nowe-posty.json');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function fail(msg) { console.error(`Błąd: ${msg}`); process.exit(1); }

// fetch() z retry — long-poll do Apify potrafi rzucić przejściowym ECONNRESET/timeout.
async function safeFetch(url, opts = {}, tries = 4) {
  let lastErr;
  for (let i = 0; i < tries; i++) {
    try { return await fetch(url, opts); }
    catch (e) {
      lastErr = e;
      console.error(`  ⚠️ błąd sieci (próba ${i + 1}/${tries}): ${e.message} — ponawiam…`);
      await sleep(3000 * (i + 1));
    }
  }
  throw lastErr;
}

// Self-contained loader APIFY_API_KEY (NIE importuje z _shared/, marketplace-ready).
function loadApifyToken() {
  if (process.env.APIFY_API_KEY) return process.env.APIFY_API_KEY.trim();
  for (const start of [__dirname, process.cwd(), VAULT]) {
    let cur = resolve(start);
    for (let i = 0; i < 8; i++) {
      const envPath = join(cur, '.env');
      if (existsSync(envPath)) {
        const line = readFileSync(envPath, 'utf8').split('\n')
          .find((l) => /^\s*APIFY_API_KEY\s*=/.test(l));
        if (line) {
          const val = line.split('=').slice(1).join('=').trim().replace(/^["']|["']$/g, '');
          if (val) return val;
        }
      }
      const parent = dirname(cur);
      if (parent === cur) break;
      cur = parent;
    }
  }
  fail('nie znaleziono APIFY_API_KEY (sprawdź .env w root workspace)');
}

// Lista grup z config/grupy.md — linie z URL-em grupy (reszta = komentarz/nagłówki).
function readGroups() {
  if (!existsSync(GROUPS_FILE)) fail(`brak listy grup: ${GROUPS_FILE}`);
  const urls = readFileSync(GROUPS_FILE, 'utf8').split('\n')
    .map((l) => l.trim())
    .map((l) => (l.match(/https?:\/\/(?:www\.)?facebook\.com\/groups\/[^\s)]+/) || [])[0])
    .filter(Boolean);
  if (!urls.length) fail(`lista grup pusta: ${GROUPS_FILE}`);
  return [...new Set(urls)];
}

function loadSeen() {
  if (!existsSync(SEEN_FILE)) return {};
  try { return JSON.parse(readFileSync(SEEN_FILE, 'utf8')); } catch { return {}; }
}

// Klucz dedup = hash URL posta (stabilny identyfikator między runami).
function postKey(url) {
  return createHash('sha1').update(url).digest('hex').slice(0, 12);
}

async function startRun(token, input) {
  const runTimeoutSecs = Math.round(POLL_TIMEOUT_MS / 1000);
  const res = await safeFetch(`${API}/acts/${ACTOR}/runs?token=${token}&timeout=${runTimeoutSecs}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!res.ok) fail(`Apify start HTTP ${res.status}: ${await res.text()}`);
  return (await res.json()).data;
}

async function waitForRun(token, runId) {
  const deadline = Date.now() + POLL_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const res = await safeFetch(`${API}/actor-runs/${runId}?token=${token}`);
    if (!res.ok) fail(`Apify poll HTTP ${res.status}`);
    const data = (await res.json()).data;
    if (['SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'].includes(data.status)) return data;
    await sleep(POLL_INTERVAL_MS);
  }
  fail(`timeout — run Apify nie skończył w ${Math.round(POLL_TIMEOUT_MS / 60000)} min`);
}

async function fetchItems(token, datasetId) {
  const res = await safeFetch(`${API}/datasets/${datasetId}/items?token=${token}&clean=true`);
  if (!res.ok) fail(`Apify dataset HTTP ${res.status}`);
  return res.json();
}

// Odchudzenie surowego itemu Apify do pól istotnych dla kwalifikacji + notatki leada.
// topComments (top/najciekawsze komentarze) niosą sygnał konkurencji ("zapraszam na priv" =
// ktoś już się zgłosił) i nastrojów — asystent używa ich przy kwalifikacji.
function slim(item) {
  const url = item.url || item.facebookUrl || '';
  const komentarze = (item.topComments || []).map((c) => ({
    autor: c.profileName || '',
    tekst: (c.text || '').slice(0, 600),
  })).filter((c) => c.tekst.trim());
  return {
    key: postKey(url),
    url,
    grupa: item.groupTitle || '',
    autor: (item.user && item.user.name) || '',
    tekst: (item.text || '').slice(0, 3000),
    data: item.time || '',
    is_listing: !!item.isMarketplaceListing,
    komentarze,
  };
}

function commit() {
  if (!existsSync(MANIFEST)) fail(`brak manifestu do commit: ${MANIFEST}`);
  const posts = JSON.parse(readFileSync(MANIFEST, 'utf8'));
  const seen = loadSeen();
  const stamp = new Date(Date.now()).toISOString().slice(0, 10);
  let added = 0;
  for (const p of posts) {
    if (!seen[p.key]) { seen[p.key] = stamp; added++; }
  }
  writeFileSync(SEEN_FILE, JSON.stringify(seen, null, 0));
  console.log(`✓ commit: dopisano ${added} URL-i do _seen (łącznie ${Object.keys(seen).length}).`);
}

async function runFetch(hours, maxPerGroup) {
  const groups = readGroups();
  const seen = loadSeen();
  const token = loadApifyToken();

  const input = {
    startUrls: groups,
    onlyPostsNewerThanHours: hours,
    maxItems: maxPerGroup,
    viewOption: 'CHRONOLOGICAL',
    includeComments: true, // topComments = sygnał konkurencji + nastrojów pod postem
    proxy: { useApifyProxy: true, apifyProxyGroups: ['RESIDENTIAL'] },
  };

  console.log(`🕷️  Scrapuję ${groups.length} grup (ostatnie ${hours} h, max ${maxPerGroup}/grupę)…`);
  const run = await startRun(token, input);
  const done = await waitForRun(token, run.id);
  if (done.status !== 'SUCCEEDED') fail(`run Apify zakończył się statusem ${done.status}`);

  const items = await fetchItems(token, done.defaultDatasetId);
  const slimmed = items.map(slim).filter((p) => p.url && p.tekst.trim());

  // Dedup vs _seen — do kwalifikacji idą TYLKO nowe posty (nie palimy tokenów na to, co już było).
  const fresh = slimmed.filter((p) => !seen[p.key]);

  mkdirSync(STATE_DIR, { recursive: true });
  writeFileSync(MANIFEST, JSON.stringify(fresh, null, 1));
  console.log(`✓ pobrano ${slimmed.length} postów, ${fresh.length} nowych → ${MANIFEST}`);
  if (fresh.length === 0) console.log('  (brak nowych postów — nic do kwalifikacji)');
}

// --- main ---
const args = process.argv.slice(2);
if (args.includes('--commit')) {
  commit();
} else {
  const hours = Number((args[args.indexOf('--hours') + 1]) || 24);
  const maxPerGroup = Number((args[args.indexOf('--max-per-group') + 1]) || 100);
  runFetch(hours, maxPerGroup);
}
