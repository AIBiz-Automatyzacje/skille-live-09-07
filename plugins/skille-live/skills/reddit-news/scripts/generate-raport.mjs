#!/usr/bin/env node
// Generator raportu HTML z newsami z Reddita (brand AIBIZ Dark Impact).
// Użycie: node generate-raport.mjs [data/YYYY-MM-DD.json]
// Czyta sklasyfikowany data json, pisze Raporty/raport-aktualny.html + Raporty/YYYY-MM-DD.html.

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// STATE_DIR MUSI celować w ŻYWY vault (~/vault, Obsidian Sync), NIE w realpath symlinka
// .claude → vault-git. Node rozwija symlink w __dirname — kotwiczymy w cwd / CLAUDE_CRON_WORKSPACE.
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
const STATE_DIR = join(vaultRoot(), 'Zasoby/Research/reddit-news');
const todayISO = () => new Date().toISOString().slice(0, 10);
const DATA = process.argv[2] ? resolve(process.argv[2]) : join(STATE_DIR, 'data', `${todayISO()}.json`);
const RAPORTY = join(STATE_DIR, 'Raporty');

const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const safeUrl = (u) => {
  try {
    const p = new URL(u);
    return ['http:', 'https:'].includes(p.protocol) ? p.href : '#';
  } catch {
    return '#';
  }
};
const fmtNum = (n) => {
  const v = Number(n) || 0;
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
  return String(v);
};
const fmtData = (iso) => {
  if (!iso) return '';
  const d = String(iso).slice(0, 10).split('-');
  return d.length === 3 ? `${d[2]}.${d[1]}` : iso;
};
// Klasa koloru badge'a score: 8-10 mocny pomarańcz, 6-7 stonowany, <6 wyblakły.
const scoreCls = (s) => (s >= 8 ? 'sc-hot' : s >= 6 ? 'sc-mid' : 'sc-low');

function card(n) {
  const tag = n.tag ? `<span class="tag">${esc(n.tag)}</span>` : '';
  const score = Number(n.score) || 0;
  const sub = esc(n.subreddit || '');
  const meta = [
    `<span class="m-up">▲ ${fmtNum(n.upvotes)}</span>`,
    `<span class="m-com">💬 ${fmtNum(n.comments)}</span>`,
    n.created_at ? `<span class="m-date">${esc(fmtData(n.created_at))}</span>` : '',
  ].filter(Boolean).join('');
  const summary = n.summary ? `<p class="summary">${esc(n.summary)}</p>` : '';
  const ext = n.link_url
    ? `<a class="ext" href="${esc(safeUrl(n.link_url))}" target="_blank" rel="noopener">🔗 link zewnętrzny</a>`
    : '';

  return `<article class="card" data-score="${score}" data-up="${Number(n.upvotes) || 0}" data-date="${esc(n.created_at || '')}">
    <div class="body">
      <div class="chips">
        ${tag}
        <span class="score ${scoreCls(score)}">${score}/10</span>
        <span class="sub">r/${sub}</span>
      </div>
      <h3 class="title"><a href="${esc(safeUrl(n.url))}" target="_blank" rel="noopener">${esc(n.title)}</a></h3>
      <div class="meta">${meta}</div>
      ${summary}
      <footer class="foot">
        ${ext}
        <a class="cta" href="${esc(safeUrl(n.url))}" target="_blank" rel="noopener">Zobacz na Reddicie →</a>
      </footer>
    </div>
  </article>`;
}

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');
  :root {
    color-scheme: dark;
    --primary: #FE6F00; --primary-strong: #FF8A1F;
    --bg: #0A0A0A; --surface: #161616; --surface-2: #1F1F1F;
    --on: #F4F4F5; --muted: #9A9A9F; --faint: #6B6B70;
    --border: #FFFFFF12; --border-2: #FFFFFF1F; --success: #34D399; --glow: #FE6F0040;
  }
  * { box-sizing: border-box; margin: 0; }
  body {
    background: var(--bg); color: var(--on);
    font: 16px/1.55 Inter, -apple-system, 'Segoe UI', sans-serif;
    padding: 56px 20px 80px; max-width: 680px; margin: 0 auto;
    -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
  }
  .overline { font: 700 11px/1.3 Inter; letter-spacing: .12em; text-transform: uppercase; color: var(--primary); }
  h1 { font: 800 34px/1.1 Outfit, sans-serif; letter-spacing: -.02em; margin: 8px 0 6px; text-wrap: balance; }
  h1 .accent { color: var(--primary); }
  .sub-head { color: var(--muted); font-size: 14px; }

  .funnel { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 28px 0 36px; }
  .stat { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 16px 14px; }
  .stat b { display: block; font: 800 26px/1 Outfit, sans-serif; letter-spacing: -.02em; font-variant-numeric: tabular-nums; }
  .stat.accent b { color: var(--primary); }
  .stat .lab { display: block; color: var(--muted); font-size: 11.5px; margin-top: 7px; line-height: 1.3; }

  .listhead { display: flex; align-items: center; justify-content: space-between; gap: 12px; font: 600 13px/1.2 Inter; color: var(--faint); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 14px; flex-wrap: wrap; }
  .sortbar { display: flex; gap: 4px; background: var(--surface); border: 1px solid var(--border); border-radius: 9999px; padding: 3px; }
  .sortbtn { border: none; cursor: pointer; background: transparent; color: var(--muted); border-radius: 9999px; padding: 7px 13px; font: 700 11.5px/1 Inter; letter-spacing: .02em; transition: background-color .15s ease, color .15s ease, transform .1s ease; }
  .sortbtn:hover { color: var(--on); }
  .sortbtn:active { transform: scale(.96); }
  .sortbtn.on { background: var(--primary); color: #fff; }
  .sortbtn:focus-visible { outline: 2px solid var(--primary-strong); outline-offset: 2px; }

  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 20px; margin-bottom: 14px; overflow: hidden; transition: border-color .18s ease; }
  .card:hover { border-color: var(--border-2); }
  .body { padding: 20px 24px; }

  .chips { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
  .tag { background: #FE6F001F; color: var(--primary-strong); border-radius: 9999px; padding: 4px 11px; font: 700 11px/1.3 Inter; box-shadow: inset 0 0 0 1px #FE6F0033; text-transform: uppercase; letter-spacing: .04em; }
  .score { border-radius: 9999px; padding: 4px 10px; font: 800 11.5px/1.3 Inter; font-variant-numeric: tabular-nums; }
  .sc-hot { background: var(--primary); color: #fff; box-shadow: 0 3px 16px var(--glow); }
  .sc-mid { background: var(--border-2); color: #d2d2d6; }
  .sc-low { background: #ffffff0a; color: var(--faint); }
  .sub { margin-left: auto; color: var(--faint); font: 600 12px/1.3 Inter; }

  .title { font: 700 19px/1.3 Outfit, sans-serif; letter-spacing: -.01em; text-wrap: balance; }
  .title a { color: var(--on); text-decoration: none; }
  .title a:hover { color: var(--primary); }

  .meta { display: flex; gap: 14px; margin: 10px 0 14px; color: var(--faint); font: 600 12.5px/1.3 Inter; font-variant-numeric: tabular-nums; }
  .m-up { color: var(--primary-strong); }

  .summary { color: #d4d4d8; font-size: 14.5px; line-height: 1.62; }

  .foot { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--border); flex-wrap: wrap; }
  .ext { color: var(--muted); font: 600 12.5px/1 Inter; text-decoration: none; border-bottom: 1px solid var(--border-2); }
  .ext:hover { color: var(--primary); }
  .cta { display: inline-flex; align-items: center; min-height: 38px; padding: 0 18px; margin-left: auto; background: var(--primary); color: #fff; border-radius: 9999px; text-decoration: none; font: 700 13.5px/1 Inter; transition: background-color .15s ease, transform .1s ease; }
  .cta:hover { background: var(--primary-strong); }
  .cta:active { transform: scale(.96); }
  .cta:focus-visible { outline: 2px solid var(--primary-strong); outline-offset: 2px; }

  .empty { color: var(--muted); background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 32px; text-align: center; }
  @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
  @media (max-width: 460px) { .funnel { grid-template-columns: repeat(3, 1fr); } }
`;

const SORT_JS = `
  (function () {
    var box = document.getElementById('cards');
    if (!box) return;
    var btns = document.querySelectorAll('.sortbtn');
    function sortCards(mode) {
      var arr = Array.prototype.slice.call(box.children);
      arr.sort(function (a, b) {
        if (mode === 'date') return (b.dataset.date || '').localeCompare(a.dataset.date || '');
        if (mode === 'up') return (+b.dataset.up) - (+a.dataset.up);
        var d = (+b.dataset.score) - (+a.dataset.score);
        return d || ((+b.dataset.up) - (+a.dataset.up));
      });
      arr.forEach(function (c) { box.appendChild(c); });
    }
    btns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        btns.forEach(function (b) { b.classList.remove('on'); });
        btn.classList.add('on');
        sortCards(btn.dataset.sort);
      });
    });
  })();
`;

function page(title, body) {
  return `<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(title)}</title>
<style>${CSS}</style></head><body>${body}<script>${SORT_JS}</script></body></html>`;
}

function main() {
  let data = { news: [], stats: {} };
  try {
    data = JSON.parse(readFileSync(DATA, 'utf8'));
  } catch {
    data = { news: [], stats: {} };
  }
  const news = Array.isArray(data.news) ? data.news : [];
  mkdirSync(RAPORTY, { recursive: true });

  // Domyślny sort = score desc, potem upvotes.
  const sorted = [...news].sort(
    (a, b) => (Number(b.score) || 0) - (Number(a.score) || 0) || (Number(b.upvotes) || 0) - (Number(a.upvotes) || 0)
  );

  const fetched = data.stats?.fetched ?? '–';
  const kept = data.stats?.kept ?? news.length;
  const topScore = sorted.length ? sorted[0].score : '–';

  const cards = sorted.length
    ? sorted.map(card).join('\n')
    : '<div class="empty">Brak newsów po filtrze dziś. Próg 50 ⬆️ / 24h nic nie przepuścił — albo cisza na subach.</div>';

  const body = `
    <div class="overline">Newsy z Reddita</div>
    <h1>Reddit <span class="accent">Newsy</span></h1>
    <p class="sub-head">AI · agenci · narzędzia · automatyzacja · ${data.date || todayISO()}</p>
    <div class="funnel">
      <div class="stat"><b>${fetched}</b><span class="lab">Pobranych</span></div>
      <div class="stat accent"><b>${kept}</b><span class="lab">Przeszło filtr</span></div>
      <div class="stat"><b>${topScore}</b><span class="lab">Top score</span></div>
    </div>
    <div class="listhead">
      <span>Newsy (${sorted.length})</span>
      <div class="sortbar" role="group" aria-label="Sortowanie">
        <button class="sortbtn on" data-sort="score">🔥 Score</button>
        <button class="sortbtn" data-sort="up">▲ Upvotes</button>
        <button class="sortbtn" data-sort="date">🕐 Najnowsze</button>
      </div>
    </div>
    <div id="cards">${cards}</div>`;

  const html = page(`Reddit Newsy · ${data.date || todayISO()}`, body);
  writeFileSync(join(RAPORTY, 'raport-aktualny.html'), html);
  writeFileSync(join(RAPORTY, `${data.date || todayISO()}.html`), html);
  console.error(`→ raport zapisany: Raporty/raport-aktualny.html (${sorted.length} newsów)`);
}

main();
