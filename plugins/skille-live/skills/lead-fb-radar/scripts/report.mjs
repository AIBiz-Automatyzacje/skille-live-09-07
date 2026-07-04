#!/usr/bin/env node
// lead-fb-radar — generator raportu HTML z leadów zapisanych w Zasoby/Leady-FB/.
// Czyta notatki .md (frontmatter), filtruje po dacie i renderuje przeglądarkowy raport
// w stylu AIBIZ Dark. Domyślnie: leady z dziś. Puls może wskazać datę: --date YYYY-MM-DD.
//
// Użycie:
//   node report.mjs [--date YYYY-MM-DD]   (bez daty = dzisiejsze leady wg pola `data`)

import { readFileSync, existsSync, writeFileSync, mkdirSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

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
const DIR = join(VAULT, 'Zasoby/Leady-FB');
const REPORTS = join(DIR, 'raporty');

// Prościutki parser frontmatteru (klucz: wartość, wartości w cudzysłowach lub gołe).
function parseFront(md) {
  const m = md.match(/^---\n([\s\S]*?)\n---/);
  if (!m) return { front: {}, body: md };
  const front = {};
  for (const line of m[1].split('\n')) {
    const mm = line.match(/^(\w+):\s*(.*)$/);
    if (mm) front[mm[1]] = mm[2].trim().replace(/^["']|["']$/g, '');
  }
  return { front, body: md.slice(m[0].length).trim() };
}

const esc = (s) => String(s || '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function loadLeads(date) {
  if (!existsSync(DIR)) return [];
  return readdirSync(DIR)
    .filter((f) => f.endsWith('.md') && !f.startsWith('_'))
    .map((f) => {
      const { front, body } = parseFront(readFileSync(join(DIR, f), 'utf8'));
      return { file: f, ...front, body };
    })
    .filter((l) => l.result === 'lead' && (l.data || '').startsWith(date));
}

function statusPill(s) {
  const map = { nowy: ['st-new', '🆕 NOWY'], kontakt: ['st-sent', '📤 KONTAKT'], odrzucony: ['st-off', '✖ ODRZUCONY'] };
  const [cls, lab] = map[s] || map.nowy;
  return `<span class="pill ${cls}">${lab}</span>`;
}

function card(l) {
  const konk = Number(l.konkurencja || 0);
  const konkCls = konk === 0 ? 'k-hot' : konk <= 2 ? 'k-warm' : 'k-cold';
  const konkLab = konk === 0 ? 'nikt się nie zgłosił' : `${konk} już oferuje`;
  return `
  <div class="card">
    <div class="top">
      <div class="firm">${esc(l.autor)} <small>· ${esc(l.grupa)}</small></div>
      <div class="right">${statusPill(l.status)}<span class="konk ${konkCls}">🥊 ${konkLab}</span></div>
    </div>
    <div class="snippet">${esc(l.snippet)}</div>
    ${l.nastroje ? `<div class="mood">💬 ${esc(l.nastroje)}</div>` : ''}
    <div class="actions"><a href="${esc(l.url)}" target="_blank">↗ Otwórz post na FB</a><span class="fn">${esc(l.file)}</span></div>
  </div>`;
}

function render(date, leads) {
  const hot = leads.filter((l) => Number(l.konkurencja || 0) === 0).length;
  return `<!DOCTYPE html><html lang="pl"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lead FB Radar — ${date}</title>
<style>
:root{--bg:#0f1115;--card:#171a21;--card2:#1d212b;--line:#2a2f3a;--txt:#e8eaf0;--mut:#8b93a3;--acc:#FF8C00;--acc2:#ffb04d;--green:#3dd68c;--red:#ff6b6b;--blue:#6ea8ff;--yellow:#ffd43b}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--txt);font-family:-apple-system,'Segoe UI',Roboto,sans-serif;padding:30px 18px 60px}
.wrap{max-width:820px;margin:0 auto}
.brand{display:flex;align-items:center;gap:11px;margin-bottom:5px}
.logo{width:36px;height:36px;border-radius:9px;background:linear-gradient(135deg,var(--acc),#ff5e00);display:flex;align-items:center;justify-content:center;font-size:19px}
h1{font-size:23px}h1 span{color:var(--acc)}
.sub{color:var(--mut);font-size:13px;margin-top:3px}
.kpis{display:flex;gap:11px;margin:22px 0;flex-wrap:wrap}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:13px 18px;flex:1;min-width:120px}
.kpi .n{font-size:25px;font-weight:800;color:var(--acc2)}
.kpi.hot .n{color:var(--green)}
.kpi .l{font-size:11px;color:var(--mut);margin-top:2px}
.card{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:17px 19px;margin-bottom:12px}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:9px}
.firm{font-size:16px;font-weight:700}.firm small{color:var(--mut);font-weight:400;font-size:12px}
.right{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pill{font-size:11px;font-weight:700;padding:4px 10px;border-radius:6px}
.st-new{background:rgba(255,212,59,.12);color:var(--yellow);border:1px solid rgba(255,212,59,.3)}
.st-sent{background:rgba(110,168,255,.1);color:var(--blue);border:1px solid rgba(110,168,255,.3)}
.st-off{background:rgba(139,147,163,.12);color:var(--mut);border:1px solid var(--line)}
.konk{font-size:11px;font-weight:600;padding:4px 10px;border-radius:6px}
.k-hot{background:rgba(61,214,140,.12);color:var(--green);border:1px solid rgba(61,214,140,.3)}
.k-warm{background:rgba(255,140,0,.12);color:var(--acc2);border:1px solid rgba(255,140,0,.3)}
.k-cold{background:rgba(255,107,107,.1);color:var(--red);border:1px solid rgba(255,107,107,.3)}
.snippet{font-size:14.5px;line-height:1.55;color:#d5d9e2}
.mood{margin-top:9px;font-size:13px;color:var(--mut);background:var(--card2);border-radius:8px;padding:8px 12px}
.actions{margin-top:12px;display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.actions a{color:var(--acc2);text-decoration:none;font-size:13px;font-weight:600}
.actions a:hover{text-decoration:underline}
.fn{color:var(--mut);font-size:11px;font-family:ui-monospace,Menlo,monospace}
.empty{background:var(--card);border:1px dashed var(--line);border-radius:13px;padding:40px;text-align:center;color:var(--mut)}
footer{margin-top:30px;color:var(--mut);font-size:11.5px;text-align:center;line-height:1.7}
</style></head><body><div class="wrap">
<div class="brand"><div class="logo">🎯</div><h1>LEAD FB RADAR <span>· ${date}</span></h1></div>
<div class="sub">zlecenia z publicznych grup Facebook · kwalifikacja przez asystenta</div>
<div class="kpis">
  <div class="kpi"><div class="n">${leads.length}</div><div class="l">nowych leadów</div></div>
  <div class="kpi hot"><div class="n">${hot}</div><div class="l">bez konkurencji<br>(zgłoś się pierwszy)</div></div>
</div>
${leads.length ? leads.map(card).join('') : '<div class="empty">Dziś zero nowych leadów. Radar czuwa dalej. 🛰️</div>'}
<footer>Wygenerowano przez skill <b>lead-fb-radar</b> · pełne leady + statusy w bazie <b>Leady-FB.base</b> (Obsidian)</footer>
</div></body></html>`;
}

// --- main ---
const args = process.argv.slice(2);
const date = (args[args.indexOf('--date') + 1] && args.includes('--date'))
  ? args[args.indexOf('--date') + 1]
  : new Date().toISOString().slice(0, 10);

const leads = loadLeads(date);
mkdirSync(REPORTS, { recursive: true });
const out = join(REPORTS, `${date}.html`);
writeFileSync(out, render(date, leads));
console.log(`✓ raport: ${out} (${leads.length} leadów)`);
