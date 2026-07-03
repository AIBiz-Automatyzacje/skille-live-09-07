"""CSS raportu /meta-daily v2.0 — układ zatwierdzony przez Kacpra w Figmie (03.07).

Zasady: jedna neutralna powierzchnia, jeden akcent (#FE6F00), kolor tylko tam, gdzie
niesie status (kropka KPI, chip akcji). Widoki Przegląd/Kampanie + sekcje zwijane
(<details>) zamiast jednego długiego dokumentu.
"""

STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@600;700&family=Inter:wght@400;500;700&family=JetBrains+Mono:wght@400;700&display=swap');
* { margin:0; padding:0; box-sizing:border-box; }
:root {
  --bg:#0f1012; --surface:#17181b; --surface2:#1d1e23; --border:#26272e;
  --text:#f0f0f2; --muted:#9da0a8; --faint:#6b6e76; --accent:#fe6f00;
  --green:#4ade80; --amber:#fbbf24; --red:#f87171; --blue:#60a5fa;
}
body { background:var(--bg); color:var(--text); font-family:'Inter',sans-serif; line-height:1.5; padding:28px 24px 64px; }
.wrap { max-width:1280px; margin:0 auto; display:flex; flex-direction:column; gap:20px; }
h1,h2,h3 { font-family:'Outfit',sans-serif; text-wrap:balance; }
.num { font-family:'JetBrains Mono',monospace; font-variant-numeric:tabular-nums; }

/* topbar */
.topbar { display:flex; justify-content:space-between; align-items:center; gap:16px; flex-wrap:wrap; }
.topbar .tleft { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; }
.topbar h1 { font-size:22px; font-weight:700; }
.topbar .tdate { font-size:13px; color:var(--faint); }
.seg { display:flex; gap:2px; padding:3px; background:var(--surface); border:1px solid var(--border); border-radius:9px; }
.segbtn { padding:6px 14px; border:0; border-radius:7px; background:transparent; color:var(--muted); font:inherit; font-size:13px; cursor:pointer; transition:background .15s, color .15s; }
.segbtn:active { transform:scale(.96); }
.segbtn.active { background:var(--surface2); color:var(--text); font-weight:500; }

/* karty i KPI */
.card { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:18px 22px; }
.card > h2 { font-size:16px; font-weight:600; margin-bottom:10px; }
.kpirow { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; }
.kpi { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:16px 18px; display:flex; flex-direction:column; gap:6px; }
.kpi .kl { display:flex; align-items:center; gap:6px; font-size:11px; font-weight:500; color:var(--faint); letter-spacing:.05em; text-transform:uppercase; }
.kpi .dot { width:7px; height:7px; border-radius:999px; flex-shrink:0; }
.kpi .kv { font-family:'JetBrains Mono',monospace; font-variant-numeric:tabular-nums; font-size:26px; font-weight:700; }
.kpi .ks { font-size:12px; color:var(--muted); }
.kpi .bar { height:4px; background:var(--surface2); border-radius:999px; overflow:hidden; margin-top:2px; }
.kpi .fill { height:100%; background:var(--accent); border-radius:999px; }

/* treść oceny (markdown) */
.prose { font-size:14px; color:var(--muted); line-height:1.6; }
.prose p { margin:6px 0; }
.prose strong { color:var(--text); }
.prose ul,.prose ol { margin:6px 0 6px 18px; }
.psrc { font-size:11.5px; color:var(--faint); margin-top:10px; }

/* lista akcji */
.alist { display:flex; flex-direction:column; }
.arow { display:flex; align-items:flex-start; gap:14px; padding:11px 0; border-bottom:1px solid var(--border); }
.arow:last-child { border-bottom:0; }
.arow .atext { flex:1; font-size:13.5px; color:var(--text); line-height:1.45; }
.arow .atext p { margin:0; display:inline; }
.arow .atext strong { color:var(--text); }
.arow .acamp { font-size:11.5px; color:var(--faint); white-space:nowrap; padding-top:3px; }
.chip { flex-shrink:0; width:76px; text-align:center; padding:4px 0; border-radius:6px; font-size:10px; font-weight:700; letter-spacing:.06em; margin-top:1px; }
.chip.zmien { background:rgba(248,113,113,.13); color:var(--red); }
.chip.usun { background:rgba(251,191,36,.13); color:var(--amber); }
.chip.popraw { background:rgba(96,165,250,.13); color:var(--blue); }
.chip.obserwuj { background:rgba(157,160,168,.13); color:var(--muted); }

/* widok kampanii */
.selrow { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
.campselect { background:var(--surface); border:1px solid var(--border); border-radius:10px; color:var(--text);
  font-family:'Outfit',sans-serif; font-size:17px; font-weight:600; padding:10px 16px; cursor:pointer; appearance:auto; }
.statchip { padding:4px 9px; border-radius:6px; font-size:11px; font-weight:500; background:rgba(157,160,168,.09); color:var(--muted); }
.statchip.on { background:rgba(74,222,128,.13); color:var(--green); }
.statchip.warn { background:rgba(251,191,36,.13); color:var(--amber); }
.cview { display:none; flex-direction:column; gap:20px; }
.cview.active { display:flex; }
#view-kampanie { display:none; flex-direction:column; gap:20px; }
#view-przeglad { display:flex; flex-direction:column; gap:20px; }

/* sekcje zwijane */
details.sect { background:var(--surface); border:1px solid var(--border); border-radius:12px; }
details.sect > summary { list-style:none; cursor:pointer; display:flex; align-items:center; gap:14px; padding:15px 22px; }
details.sect > summary::-webkit-details-marker { display:none; }
details.sect > summary .st { font-family:'Outfit',sans-serif; font-size:15px; font-weight:600; white-space:nowrap; }
details.sect > summary .ss { flex:1; font-size:12.5px; color:var(--faint); }
details.sect > summary .sx { font-size:13px; font-weight:500; color:var(--accent); white-space:nowrap; }
details.sect > summary .sx::before { content:'▸ Rozwiń'; }
details.sect[open] > summary .sx::before { content:'▾ Zwiń'; }
details.sect > .sbody { padding:0 22px 18px; display:flex; flex-direction:column; gap:12px; }

/* siatka kreacji */
.agrid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
@media (max-width:860px) { .agrid { grid-template-columns:repeat(2,1fr); } }
.abox { background:var(--surface2); border:1px solid var(--border); border-radius:10px; padding:12px; display:flex; flex-direction:column; gap:7px; }
.abox img { width:100%; height:140px; object-fit:cover; border-radius:7px; background:var(--border); }
.abox .noimg { width:100%; height:140px; border-radius:7px; background:var(--surface); border:1px dashed var(--border); display:flex; align-items:center; justify-content:center; font-size:11px; color:var(--faint); }
.abox .arow2 { display:flex; align-items:center; gap:8px; }
.abox .aname { flex:1; font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.abox .amain { font-size:13px; font-weight:500; color:var(--text); white-space:nowrap; }
.abox .astats { font-size:11.5px; color:var(--faint); }
.abox .averdict { font-size:12px; color:var(--muted); line-height:1.45; border-top:1px solid var(--border); padding-top:7px; margin-top:auto; }
.abox .averdict p { margin:0; }
.abox .averdict strong { color:var(--text); }
.smallline { font-size:12px; color:var(--faint); line-height:1.6; }
.smallline .rn { font-family:'JetBrains Mono',monospace; color:var(--muted); }

/* edycje / copy / wykres */
.plainlist { font-size:12.5px; color:var(--muted); line-height:1.7; }
.copyrow { padding:8px 0; border-bottom:1px solid var(--border); font-size:13px; color:var(--muted); }
.copyrow:last-child { border-bottom:0; }
.copyrow .c { font-family:'JetBrains Mono',monospace; font-size:11.5px; color:var(--text); margin-right:8px; }
.lc-bars { display:flex; align-items:flex-end; gap:3px; min-height:120px; padding:4px 0; }
.lc-col { flex:1 1 0; display:flex; flex-direction:column; justify-content:flex-end; align-items:center; gap:3px; }
.lc-val { font-family:'JetBrains Mono',monospace; font-size:10px; color:var(--muted); min-height:13px; }
.lc-bar { width:100%; min-width:2px; background:var(--accent); opacity:.75; border-radius:2px 2px 0 0; min-height:1px; }
.lc-bar.zero { background:var(--surface2); opacity:1; }
.lc-axis { display:flex; justify-content:space-between; font-size:10px; color:var(--faint); margin-top:4px; font-family:'JetBrains Mono',monospace; }
footer { color:var(--faint); font-size:12px; padding-top:8px; }
.muted { color:var(--faint); }
@media (prefers-reduced-motion: reduce) { * { transition:none !important; } }
"""

SCRIPT = """
function showView(v){
  document.getElementById('view-przeglad').style.display = v==='przeglad' ? 'flex' : 'none';
  document.getElementById('view-kampanie').style.display = v==='kampanie' ? 'flex' : 'none';
  document.querySelectorAll('.segbtn').forEach(b => b.classList.toggle('active', b.dataset.v===v));
}
function showCamp(id){
  document.querySelectorAll('.cview').forEach(c => c.classList.toggle('active', c.id==='c-'+id));
}
document.addEventListener('DOMContentLoaded', () => {
  const sel = document.getElementById('campselect');
  if (sel) showCamp(sel.value);
});
"""
