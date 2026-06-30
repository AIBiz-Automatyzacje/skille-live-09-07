#!/usr/bin/env node
// Reddit news fetcher — listing top postów z doby przez Apify (trudax/reddit-scraper-lite).
// Oficjalne API Reddit padło (zmiana polityki) → scrapujemy przez Apify z proxy residential.
//
// Dwa tryby:
//   (domyślny)     pobierz kandydatów → zapis raw/YYYY-MM-DD.json
//   --commit FILE  dopisz post_id z FILE do _seen.json (po wygenerowaniu raportu)
//
// Użycie:
//   node fetch_subreddits.mjs [--hours 24] [--min-upvotes 50] [--max-per-sub 50]
//   node fetch_subreddits.mjs --commit Zasoby/Research/reddit-news/raw/YYYY-MM-DD.json

import { readFileSync, existsSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ACTOR = 'trudax~reddit-scraper-lite';
const API = 'https://api.apify.com/v2';
const POLL_INTERVAL_MS = 6000;
const POLL_TIMEOUT_MS = 60 * 60 * 1000; // 60 min — RESIDENTIAL mocno dławiony; pełna doba subów bywa 40-50+ min, duży zapas (job leci 5:00, długość nie przeszkadza)
const SEEN_PRUNE_DAYS = 30;

const __dirname = dirname(fileURLToPath(import.meta.url));

// STATE_DIR MUSI celować w ŻYWY vault (~/vault, syncowany przez Obsidian Sync), a NIE w realpath
// symlinka .claude → vault-git (martwy klon git, którego Obsidian Sync nie tyka). Node rozwija
// symlink w __dirname, więc kotwiczymy w cwd / CLAUDE_CRON_WORKSPACE, nie w ścieżce skryptu.
function vaultRoot() {
  if (process.env.CLAUDE_CRON_WORKSPACE) return resolve(process.env.CLAUDE_CRON_WORKSPACE);
  let cur = process.cwd();
  for (let i = 0; i < 8; i++) {
    if (existsSync(join(cur, '.obsidian'))) return cur; // marker żywego vaulta Obsidian
    const parent = dirname(cur);
    if (parent === cur) break;
    cur = parent;
  }
  return process.cwd();
}
const STATE_DIR = join(vaultRoot(), 'Zasoby/Research/reddit-news');
const SUBS_FILE = join(STATE_DIR, 'subreddity.txt');
const SEEN_FILE = join(STATE_DIR, '_seen.json');
const RAW_DIR = join(STATE_DIR, 'raw');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function fail(msg) {
  console.error(`Błąd: ${msg}`);
  process.exit(1);
}

// fetch() z retry — long-poll do Apify potrafi rzucić przejściowym ECONNRESET/timeout.
// Bez tego cały run pada na jednym zerwanym połączeniu (luźna sieć / proxy throttle).
async function safeFetch(url, opts = {}, tries = 4) {
  let lastErr;
  for (let i = 0; i < tries; i++) {
    try {
      return await fetch(url, opts);
    } catch (e) {
      lastErr = e;
      console.error(`  ⚠️ błąd sieci (próba ${i + 1}/${tries}): ${e.message} — ponawiam…`);
      await sleep(3000 * (i + 1));
    }
  }
  throw lastErr;
}

// --- Self-contained loader APIFY_API_KEY (NIE importuje z _shared/) ---
function loadApifyToken() {
  if (process.env.APIFY_API_KEY) return process.env.APIFY_API_KEY.trim();
  const starts = [__dirname, process.cwd()];
  for (const start of starts) {
    let cur = resolve(start);
    for (let i = 0; i < 8; i++) {
      const envPath = join(cur, '.env');
      if (existsSync(envPath)) {
        const line = readFileSync(envPath, 'utf8')
          .split('\n')
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

function readSubreddits() {
  if (!existsSync(SUBS_FILE)) fail(`brak listy subredditów: ${SUBS_FILE}`);
  const subs = readFileSync(SUBS_FILE, 'utf8')
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith('#'))
    .map((l) => l.replace(/^r\//i, '').replace(/\/+$/, ''));
  if (!subs.length) fail(`lista subredditów pusta: ${SUBS_FILE}`);
  return subs;
}

function loadSeen() {
  if (!existsSync(SEEN_FILE)) return {};
  try {
    return JSON.parse(readFileSync(SEEN_FILE, 'utf8'));
  } catch {
    return {};
  }
}

async function startRun(token, input) {
  // timeout po stronie Apify (sek) — zawieszony run sam się ubije zamiast bić kasę bez końca.
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

// Odchudzenie surowego itemu Apify do pól istotnych dla klasyfikacji + raportu.
function slim(item) {
  const body = item.body || '';
  const url = item.url || item.link || '';
  const link = item.link && item.link !== url ? item.link : ''; // link zewnętrzny (link-post)
  return {
    post_id: item.parsedId || (item.id || '').replace(/^t3_/, ''),
    url,
    title: item.title || '',
    subreddit: item.parsedCommunityName || (item.communityName || '').replace(/^r\//i, ''),
    author: item.username || 'deleted',
    body: body.slice(0, 2000),
    body_preview: body.slice(0, 400),
    link_url: link,
    is_self: (item.contentType || '') === 'text',
    upvotes: Number(item.upVotes) || 0,
    comments: Number(item.numberOfComments) || 0,
    created_at: item.createdAt || '',
  };
}

async function runFetch(hours, minUpvotes, maxPerSub) {
  const subs = readSubreddits();
  const seen = loadSeen();
  const token = loadApifyToken();
  const cutoff = Date.now() - hours * 3600 * 1000;

  const input = {
    startUrls: subs.map((s) => ({ url: `https://www.reddit.com/r/${s}/top/?t=day` })),
    sort: 'top',
    time: 'day',
    includeMediaLinks: true, // bez tego brak upVotes / numberOfComments
    skipComments: true,
    skipUserPosts: true,
    skipCommunity: true,
    maxPostCount: maxPerSub,
    maxItems: subs.length * maxPerSub,
    proxy: { useApifyProxy: true, apifyProxyGroups: ['RESIDENTIAL'] },
  };

  console.error(`🔍 reddit-news fetch — ${subs.length} subów | okno ${hours}h | min ${minUpvotes} ⬆️ | seen=${Object.keys(seen).length}`);
  const run = await startRun(token, input);
  console.error(`→ run ${run.id} (${run.status})…`);
  const done = await waitForRun(token, run.id);
  if (done.status !== 'SUCCEEDED') fail(`run zakończony statusem ${done.status}`);

  const items = await fetchItems(token, done.defaultDatasetId);
  const posts = items.filter((it) => (it.dataType || 'post') === 'post');

  const byId = new Map();
  let dropOld = 0;
  let dropLow = 0;
  let dropSeen = 0;
  for (const it of posts) {
    const p = slim(it);
    if (!p.post_id || !p.title) continue;
    if (p.created_at && Date.parse(p.created_at) < cutoff) { dropOld++; continue; }
    if (p.upvotes < minUpvotes) { dropLow++; continue; }
    if (seen[p.post_id]) { dropSeen++; continue; }
    if (!byId.has(p.post_id)) byId.set(p.post_id, p);
  }
  const unique = [...byId.values()].sort((a, b) => b.upvotes - a.upvotes);

  mkdirSync(RAW_DIR, { recursive: true });
  const date = new Date().toISOString().slice(0, 10);
  const rawPath = join(RAW_DIR, `${date}.json`);
  writeFileSync(
    rawPath,
    JSON.stringify(
      {
        date,
        generated_at: new Date().toISOString(),
        filters: { hours, min_upvotes: minUpvotes, max_per_sub: maxPerSub },
        subreddits: subs,
        count: unique.length,
        candidates: unique,
      },
      null,
      2
    )
  );

  console.error(`→ surowych postów: ${posts.length} | odsiane: ${dropOld} stare / ${dropLow} <${minUpvotes}⬆️ / ${dropSeen} seen`);
  console.error(`✅ Kandydatów po filtrze: ${unique.length}`);
  console.error(`🧾 Raw: ${rawPath}`);
  for (const p of unique.slice(0, 3)) {
    console.error(`  [${p.upvotes} ⬆️ ${p.comments} 💬] ${p.title.slice(0, 70)} — r/${p.subreddit}`);
  }
}

function runCommit(filePath) {
  const src = resolve(filePath);
  if (!existsSync(src)) fail(`plik do commitu nie istnieje: ${src}`);
  const data = JSON.parse(readFileSync(src, 'utf8'));
  const items = data.candidates || data.news || [];
  const ids = items.map((it) => it.post_id).filter(Boolean);

  const seen = loadSeen();
  const today = new Date().toISOString().slice(0, 10);
  for (const id of ids) seen[id] = today;

  const cutoffDate = new Date(Date.now() - SEEN_PRUNE_DAYS * 86400 * 1000).toISOString().slice(0, 10);
  const pruned = Object.fromEntries(Object.entries(seen).filter(([, d]) => d >= cutoffDate));

  mkdirSync(STATE_DIR, { recursive: true });
  writeFileSync(SEEN_FILE, JSON.stringify(pruned, null, 2));
  console.error(`✅ _seen.json: +${ids.length} oznaczonych | razem ${Object.keys(pruned).length} (przycięto do ${SEEN_PRUNE_DAYS} dni)`);
}

function parseArgs(argv) {
  const out = { hours: 24, minUpvotes: 50, maxPerSub: 15, commit: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--commit') out.commit = argv[++i];
    else if (a === '--hours') out.hours = parseInt(argv[++i], 10);
    else if (a === '--min-upvotes') out.minUpvotes = parseInt(argv[++i], 10);
    else if (a === '--max-per-sub') out.maxPerSub = parseInt(argv[++i], 10);
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.commit) runCommit(args.commit);
  else await runFetch(args.hours, args.minUpvotes, args.maxPerSub);
}

main().catch((e) => fail(e.message));
