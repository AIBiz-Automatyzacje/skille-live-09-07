#!/usr/bin/env python3
"""RENDER v2.0 — interaktywny raport HTML wg układu zatwierdzonego w Figmie (03.07).

Dwa widoki w jednym pliku (czysty JS, zero zależności):
- Przegląd: KPI (zapisy/tempo/prognoza/koszt) + Ocena dnia + lista Akcji z chipami.
- Kampanie: selektor kampanii, KPI kampanii, akcje kampanii, ocena, sekcje zwijane
  (kreacje w siatce, historia zmian, teksty reklam, wykres zapisów).
Zasady wizualne: jedna powierzchnia, jeden akcent; kolor tylko dla statusu (kropka/chip).
Panel „wartość nowego zapisu" NIE jest renderowany (insight jednorazowy — decyzja Kacpra
03.07); benchmarki zostają w wsadzie REASON jako wiedza do oceny.

Użycie: python3 report.py
"""
import base64
import html
import json
import os
from datetime import date, datetime, timedelta

import requests
from markdown_it import MarkdownIt

import db
import compute
from enrich import CACHE_DIR, MIN_IMPR
from meta_common import WORKSPACE
from style import SCRIPT, STYLE

REPORTS_DIR = os.path.join(WORKSPACE, "Zadania", "projekty", "meta-ads", "raporty")
REASON_PATH = os.path.join(WORKSPACE, "Zadania", "projekty", "meta-ads", "reason.json")

_MD = MarkdownIt()
ARCHIVE_DAYS = 5   # kreacja bez emisji dłużej → linia „poza codzienną oceną", nie boks

EDIT_PL = {
    "edit_images": "zmiana grafik", "add_images": "dodanie grafik",
    "update_ad_creative": "zmiana kreacji", "update_ad_set_target_spec": "zmiana grupy odbiorców",
    "update_campaign_budget": "zmiana budżetu kampanii", "update_ad_set_budget": "zmiana budżetu zestawu",
    "update_ad_set_optimization_goal": "zmiana celu optymalizacji",
    "update_ad_set_bid_strategy": "zmiana strategii stawek",
}
CHIP_PL = {"zmien": "ZMIEŃ", "usun": "USUŃ", "popraw": "POPRAW", "obserwuj": "UWAGA"}
FUNNEL_PL = {"form": "FORMULARZ BŁYSKAWICZNY", "lp": "LANDING PAGE"}


def _money(v):
    return f"{v:,.0f} zł".replace(",", " ") if v else "0 zł"


def _md(text):
    return _MD.render(text) if text else ""


def _dm(iso):
    return f"{iso[8:10]}.{iso[5:7]}" if iso else ""


def _b64_img(asset_key, fallback_url=None):
    path = os.path.join(CACHE_DIR, f"{asset_key}.png")
    if not os.path.exists(path) and fallback_url:
        try:
            r = requests.get(fallback_url, timeout=20)
            r.raise_for_status()
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(path, "wb") as f:
                f.write(r.content)
        except (requests.RequestException, OSError):
            return None
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


# ---------- WIDOK 1: PRZEGLĄD ----------

def _kpi(label, value, sub, dot=None, progress=None):
    d = f'<span class="dot" style="background:{dot}"></span>' if dot else ""
    bar = (f'<div class="bar"><div class="fill" style="width:{min(progress, 100)}%"></div></div>'
           if progress is not None else "")
    return (f'<div class="kpi"><div class="kl">{d}{label}</div>'
            f'<div class="kv">{value}</div><div class="ks">{sub}</div>{bar}</div>')


def _live_cpl_week(camps):
    """Ważony koszt zapisu 7 dni z kampanii leadowych bieżącego live."""
    spend = leads = 0
    for c in camps:
        if c["campaign"]["klasa"] == "lead" and c["campaign"].get("live_group"):
            w = c["periods"].get("week") or {}
            spend += w.get("spend") or 0
            leads += w.get("leads") or 0
    return round(spend / leads, 2) if leads else None


def render_kpi_przeglad(lc, camps):
    if not lc:
        return ""
    tiles = []
    tmin = lc.get("target_min")
    pct = round(lc["signups_total"] / tmin * 100) if tmin else None
    tiles.append(_kpi("Zapisy na live", f'{lc["signups_total"]:,}'.replace(",", " "),
                      f'cel {tmin}–{lc.get("target_max")} · {pct}%' if tmin else "brak celu",
                      dot="var(--accent)", progress=pct))
    rate, need = lc.get("rate_per_day"), lc.get("needed_per_day")
    if rate is not None:
        ok = need is None or rate >= need
        tiles.append(_kpi("Tempo / dzień", f"{rate:.0f}",
                          f"potrzeba {need:.0f}" if need is not None else "śr. 3 dni",
                          dot="var(--green)" if ok else "var(--amber)"))
    fc = lc.get("forecast")
    if fc:
        gap = fc["gap_to_min"]
        tiles.append(_kpi(f'Prognoza na {_dm(lc["config"]["live_date"])}',
                          f'~{fc["projected"]:,}'.replace(",", " "),
                          f"{gap} poniżej celu" if gap > 0 else "cel min. osiągnięty",
                          dot="var(--amber)" if gap > 0 else "var(--green)"))
    cpl = _live_cpl_week(camps)
    if cpl:
        tiles.append(_kpi("Koszt zapisu (7 dni)", f"{cpl:.0f} zł", "granica 25 zł",
                          dot="var(--green)" if cpl < 25 else "var(--red)"))
    return f'<div class="kpirow">{"".join(tiles)}</div>'


def render_ocena_dnia(lc, reason_map):
    summary = reason_map.get("_summary")
    if not summary:
        return ""
    src = []
    rc = (lc or {}).get("recon")
    if rc and rc.get("meta_leads"):
        src.append(f'kontrola {_dm(rc["date"])}: Meta {rc["meta_leads"]} leadów, lista +{rc["list_delta"]}'
                   + (f' (koszt realnego adresu {rc["cpl_list"]:.0f} zł)' if rc.get("cpl_list") else ""))
    if lc:
        src.append(f'zapisy: MailerLite „{lc["config"].get("mailer_group_name", "")}" (stan {lc["signups_date"]}), '
                   f'wszystkie źródła · tempo = śr. 3 dni')
    src_html = f'<div class="psrc">{html.escape(" · ".join(src))}</div>' if src else ""
    return (f'<div class="card"><h2>Ocena dnia</h2>'
            f'<div class="prose">{_md(summary)}</div>{src_html}</div>')


def _action_rows(actions, name_map, camp_id=None):
    rows = ""
    for a in actions:
        if camp_id is not None and a.get("kampania_id") != camp_id:
            continue
        typ = a.get("typ", "obserwuj")
        camp = ""
        if camp_id is None:
            camp = name_map.get(a.get("kampania_id"), "—" if not a.get("kampania_id") else "")
            camp = f'<span class="acamp">{html.escape(camp)}</span>'
        rows += (f'<div class="arow"><span class="chip {typ}">{CHIP_PL.get(typ, typ.upper())}</span>'
                 f'<div class="atext">{_md(a.get("tekst", ""))}</div>{camp}</div>')
    return rows


def render_akcje(actions, name_map, camp_id=None, title="Akcje na dziś"):
    rows = _action_rows(actions, name_map, camp_id)
    if not rows:
        return ""
    return f'<div class="card"><h2>{title}</h2><div class="alist">{rows}</div></div>'


# ---------- WIDOK 2: KAMPANIE ----------

def _short_name(name):
    return name if len(name) <= 40 else name[:38] + "…"


def _camp_budget(conn, cid):
    """Suma budżetów AKTYWNYCH zestawów kampanii (zł/dzień) + ostatnia zmiana budżetu."""
    row = conn.execute(
        "SELECT SUM(daily_budget) b FROM adsets WHERE campaign_id=? AND status='ACTIVE'", (cid,),
    ).fetchone()
    budget = round(row["b"] / 100) if row and row["b"] else None
    ed = conn.execute(
        """SELECT event_time, extra_data FROM activities
           WHERE event_type IN ('update_ad_set_budget','update_campaign_budget')
             AND (campaign_id=? OR object_id IN (SELECT object_id FROM ad_objects WHERE campaign_id=?))
           ORDER BY event_time DESC LIMIT 1""", (cid, cid),
    ).fetchone()
    note = ""
    if ed:
        try:
            e = json.loads(ed["extra_data"])
            old = e.get("old_value", {}).get("old_value")
            new = e.get("new_value", {}).get("new_value")
            if old and new:
                note = f'zmiana {_dm(ed["event_time"][:10])}: {int(old)/100:.0f}→{int(new)/100:.0f} zł'
        except (ValueError, TypeError, AttributeError):
            pass
    return budget, note


def render_camp_kpi(conn, c):
    cm, klasa = c["campaign"], c["campaign"]["klasa"]
    p = c["periods"]
    t, w, m = p.get("today", {}), p.get("week", {}), p.get("month", {})
    ref = c["ref_date"]
    tiles = []
    if klasa == "lead":
        tiles.append(_kpi(f"Koszt zapisu · {_dm(ref)}", f'{t["cpl"]:.0f} zł' if t.get("cpl") else "—",
                          f'{t.get("leads", 0):.0f} zapisów · {_money(t.get("spend", 0))}'))
        tiles.append(_kpi("Koszt zapisu · 7 dni", f'{w["cpl"]:.0f} zł' if w.get("cpl") else "—",
                          f'{w.get("leads", 0):.0f} zapisów · {w.get("spend_per_day", 0):.0f} zł/d'))
        tiles.append(_kpi("Koszt zapisu · 30 dni", f'{m["cpl"]:.0f} zł' if m.get("cpl") else "—",
                          f'{m.get("leads", 0):.0f} zapisów'))
    else:
        tiles.append(_kpi("ROAS · 7 dni", f'{w["roas"]}×' if w.get("roas") else "—",
                          f'{w.get("purchases", 0):.0f} zakupów · {_money(w.get("spend", 0))}'))
        tiles.append(_kpi("ROAS · 30 dni", f'{m["roas"]}×' if m.get("roas") else "—",
                          f'{m.get("purchases", 0):.0f} zakupów'))
        tiles.append(_kpi("Koszt zakupu · 30 dni", f'{m["cpa"]:.0f} zł' if m.get("cpa") else "—",
                          f'{_money(m.get("spend", 0))} wydane'))
    cpm_sub = f'CPC {w["cpc"]:.2f} zł' if w.get("cpc") else ""
    tiles.append(_kpi("CPM · 7 dni", f'{w["cpm"]:.0f} zł' if w.get("cpm") else "—", cpm_sub))
    budget, note = _camp_budget(conn, cm["id"])
    tiles.append(_kpi("Budżet dziś", _money(budget * 1.0) if budget else "—", note or "suma aktywnych zestawów"))
    return f'<div class="kpirow">{"".join(tiles)}</div>'


def _camp_chips(c):
    cm = c["campaign"]
    chips = ""
    if cm.get("status") == "ACTIVE":
        chips += '<span class="statchip on">AKTYWNA</span>'
    else:
        chips += '<span class="statchip warn">⏸ WSTRZYMANA</span>'
    if c.get("funnel") in FUNNEL_PL:
        chips += f'<span class="statchip">{FUNNEL_PL[c["funnel"]]}</span>'
    f = (c["periods"].get("week") or {}).get("frequency") or 0
    if f:
        warn = " warn" if f >= 2.5 else ""
        chips += f'<span class="statchip{warn}">freq 7d: {f:.1f}</span>'.replace(".", ",")
    if c["days_inactive"] > 1:
        chips += f'<span class="statchip warn">stoi {c["days_inactive"]} dni</span>'
    return chips


def _abox(a, klasa, verdicts, ref):
    t = a["total"]
    img = _b64_img(a["asset_key"], a.get("thumbnail_url"))
    img_tag = f'<img src="{img}" loading="lazy">' if img else '<div class="noimg">brak podglądu</div>'
    main = (f'zapis {t["cpl"]:.0f} zł' if klasa == "lead" and t["cpl"]
            else f'ROAS {t["roas"]}×' if t.get("roas")
            else f'zakup {t["cpa"]:.0f} zł' if t.get("cpa")
            else "bez konwersji")
    konw = (f'{t["leads"]:.0f} zapisów' if klasa == "lead" else f'{t["purchases"]:.0f} zakupów')
    last = min(a.get("last_day") or "", ref) if a.get("last_day") else None
    emis = f' · emisja {_dm(a.get("first_day"))}–{_dm(last)}' if a.get("first_day") and last else ""
    verdict = verdicts.get(a["asset_key"])
    v_html = f'<div class="averdict">{_md(verdict)}</div>' if verdict else ""
    impr = f'{t["impressions"]:,}'.replace(",", " ")
    return (f'<div class="abox">{img_tag}'
            f'<div class="arow2"><span class="aname">{html.escape(a["name"] or a["asset_key"][:16])}</span>'
            f'<span class="amain">{main}</span></div>'
            f'<div class="astats">{konw} · CTR {t["ctr"]}% · {_money(t["spend"])} · {impr} wyśw.{emis}</div>'
            f'{v_html}</div>')


def render_kreacje(c, verdicts):
    """Sekcja zwijana: siatka boksów kreacji aktywnych + linia z resztą."""
    klasa, ref = c["campaign"]["klasa"], c["ref_date"]
    cutoff = (datetime.strptime(ref, "%Y-%m-%d") - timedelta(days=ARCHIVE_DAYS)).date().isoformat()
    boxes, rest = [], []
    for typ in ("image", "video"):
        for a in c["assets"][typ]:
            t = a["total"]
            if not t["impressions"]:
                continue
            fresh = (a.get("last_day") or ref) >= cutoff
            if t["impressions"] >= MIN_IMPR and fresh:
                boxes.append(a)
            else:
                why = "mała próba" if t["impressions"] < MIN_IMPR else "bez emisji >5 dni"
                rest.append((a, why))
    if not boxes and not rest:
        return ""
    # najlepsza/najsłabsza wg głównej metryki — do podsumowania w zwiniętym wierszu
    key = (lambda a: a["total"]["cpl"]) if klasa == "lead" else (lambda a: a["total"]["cpa"])
    rated = sorted([a for a in boxes if key(a)], key=key)
    summ = f'{len(boxes)} aktywnych'
    if rated:
        lbl = "zapis" if klasa == "lead" else "zakup"
        summ += f' · najlepsza: {_short_name(rated[0]["name"] or "?")} ({lbl} {key(rated[0]):.0f} zł)'
        if len(rated) > 1:
            summ += f' · najsłabsza: {_short_name(rated[-1]["name"] or "?")} ({key(rated[-1]):.0f} zł)'
    grid = f'<div class="agrid">{"".join(_abox(a, klasa, verdicts, ref) for a in boxes)}</div>' if boxes else ""
    rest_html = ""
    if rest:
        rest.sort(key=lambda x: -x[0]["total"]["spend"])
        items = " · ".join(f'<span class="rn">{html.escape(a["name"] or a["asset_key"][:12])}</span> ({why})'
                           for a, why in rest)
        rest_html = f'<div class="smallline">Poza codzienną oceną: {items}</div>'
    return (f'<details class="sect"><summary><span class="st">Kreacje</span>'
            f'<span class="ss">{html.escape(summ)}</span><span class="sx"></span></summary>'
            f'<div class="sbody">{grid}{rest_html}</div></details>')


def render_edycje(c):
    edits = c["edits_in_week"]
    if not edits:
        return ""
    last = edits[0]
    summ = f'{len(edits)} edycji w tym tygodniu · ostatnia: {_dm(last["time"])}, {EDIT_PL.get(last["type"], last["type"])} {last["detail"]}'
    lines = "<br>".join(
        f'{EDIT_PL.get(e["type"], e["type"])} · {e["time"]} · {html.escape(e["object"] or "")} {e["detail"]}'
        for e in edits[:8])
    note = ('Zmiana wyników może pochodzić z tych edycji, nie ze skuteczności reklam — '
            'porównania w oknach obejmujących edycję czytaj ostrożnie.')
    return (f'<details class="sect"><summary><span class="st">Historia zmian</span>'
            f'<span class="ss">{html.escape(summ)}</span><span class="sx"></span></summary>'
            f'<div class="sbody"><div class="plainlist">{lines}</div>'
            f'<div class="smallline">{note}</div></div></details>')


def render_teksty(conn, cid, klasa):
    rows = conn.execute(
        """SELECT cr.copy_text, SUM(a.clicks) clicks, SUM(a.impressions) impr,
                  SUM(a.spend) spend, SUM(a.leads) leads, SUM(a.purchases) purch
           FROM assets a JOIN creatives cr ON cr.asset_key=a.asset_key
           WHERE a.campaign_id=? AND a.asset_type='body' AND cr.copy_text IS NOT NULL
             AND LENGTH(cr.copy_text) >= 40
           GROUP BY cr.copy_text HAVING impr>0
           ORDER BY CASE WHEN SUM(a.leads)>0 THEN SUM(a.spend)/SUM(a.leads) ELSE 1e9 END
           LIMIT 5""", (cid,)).fetchall()
    if not rows:
        return ""
    best = rows[0]
    b_cpl = f'{best["spend"] / best["leads"]:.0f} zł' if best["leads"] else "—"
    summ = f'{len(rows)} wariantów · najlepszy: „{best["copy_text"][:60]}…" (zapis {b_cpl})'
    items = ""
    for r in rows:
        konw = (f'zapis {r["spend"] / r["leads"]:.0f} zł ({r["leads"]:.0f})' if r["leads"]
                else f'zakup {r["spend"] / r["purch"]:.0f} zł' if r["purch"] else 'bez konwersji')
        items += (f'<div class="copyrow"><span class="c">{konw} · CTR '
                  f'{round(r["clicks"] / r["impr"] * 100, 2)}%</span>{html.escape(r["copy_text"][:220])}</div>')
    return (f'<details class="sect"><summary><span class="st">Teksty reklam</span>'
            f'<span class="ss">{html.escape(summ)}</span><span class="sx"></span></summary>'
            f'<div class="sbody">{items}</div></details>')


def render_wykres(c):
    series = c.get("lead_series") or []
    total = sum(d["leads"] for d in series)
    if not series or total <= 0:
        return ""
    series = series[-30:]
    mx = max(d["leads"] for d in series) or 1
    bars = ""
    for d in series:
        n = d["leads"]
        h = round(n / mx * 100) if n else 2
        cls = "lc-bar" if n else "lc-bar zero"
        bars += (f'<div class="lc-col" title="{_dm(d["date"])}: {n:.0f}">'
                 f'<div class="lc-val">{f"{n:.0f}" if n else ""}</div>'
                 f'<div class="{cls}" style="height:{h}px"></div></div>')
    summ = f'razem {total:.0f} zapisów · ostatnie {len(series)} dni'
    axis = f'<div class="lc-axis"><span>{_dm(series[0]["date"])}</span><span>{_dm(series[-1]["date"])}</span></div>'
    return (f'<details class="sect"><summary><span class="st">Zapisy dziennie</span>'
            f'<span class="ss">{html.escape(summ)}</span><span class="sx"></span></summary>'
            f'<div class="sbody"><div class="lc-bars">{bars}</div>{axis}</div></details>')


def render_camp_view(conn, c, reason_map, actions, name_map):
    cm = c["campaign"]
    verdicts = reason_map.get("_assets") or {}
    ocena = reason_map.get(cm["id"])
    ocena_html = (f'<div class="card"><h2>Ocena</h2><div class="prose">{_md(ocena)}</div></div>'
                  if ocena else "")
    return (f'<div class="cview" id="c-{cm["id"]}">'
            f'<div class="selrow"><span style="width:4px"></span>{_camp_chips(c)}</div>'
            f'{render_camp_kpi(conn, c)}'
            f'{render_akcje(actions, name_map, camp_id=cm["id"], title="Akcje dla tej kampanii")}'
            f'{ocena_html}'
            f'{render_kreacje(c, verdicts)}'
            f'{render_edycje(c)}'
            f'{render_teksty(conn, cm["id"], cm["klasa"])}'
            f'{render_wykres(c)}'
            f'</div>')


# ---------- SKŁADANIE ----------

def build_html(conn, res, reason_map):
    camps = res["campaigns"]
    camps.sort(key=lambda c: (c["campaign"]["status"] != "ACTIVE",
                              -(c["periods"].get("week") or {}).get("spend", 0)))
    lc = res.get("live_context")
    actions = reason_map.get("_actions") or []
    name_map = {c["campaign"]["id"]: _short_name(c["campaign"]["name"]) for c in camps}
    name_map[None] = "—"
    today = date.today().isoformat()

    topbar = (f'<div class="topbar"><div class="tleft"><h1>Meta Ads</h1>'
              f'<span class="tdate">raport {today} · dane do {res["ref_date"]} włącznie</span></div>'
              f'<div class="seg">'
              f'<button class="segbtn active" data-v="przeglad" onclick="showView(\'przeglad\')">Przegląd</button>'
              f'<button class="segbtn" data-v="kampanie" onclick="showView(\'kampanie\')">Kampanie</button>'
              f'</div></div>')

    przeglad = (f'<div id="view-przeglad">'
                f'{render_kpi_przeglad(lc, camps)}'
                f'{render_ocena_dnia(lc, reason_map)}'
                f'{render_akcje(actions, name_map)}'
                f'</div>')

    options = "".join(
        f'<option value="{c["campaign"]["id"]}">{html.escape(c["campaign"]["name"])}'
        + (' (wstrzymana)' if c["campaign"]["status"] != "ACTIVE" else "") + '</option>'
        for c in camps)
    selector = (f'<div class="selrow"><select id="campselect" class="campselect" '
                f'onchange="showCamp(this.value)">{options}</select></div>')
    cviews = "".join(render_camp_view(conn, c, reason_map, actions, name_map) for c in camps)
    kampanie = f'<div id="view-kampanie">{selector}{cviews}</div>'

    skipped = res.get("skipped") or []
    skipped_txt = f' · pominięto bez danych: {", ".join(skipped)}' if skipped else ""
    footer = (f'<footer>Wygenerowano przez /meta-daily · dane: Meta Marketing API + MailerLite'
              f'{html.escape(skipped_txt)}</footer>')

    return (f'<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Meta Ads — raport {today}</title><style>{STYLE}</style></head>'
            f'<body><div class="wrap">{topbar}{przeglad}{kampanie}{footer}</div>'
            f'<script>{SCRIPT}</script></body></html>')


def main():
    conn = db.connect()
    res = compute.compute_all(conn)
    reason_map = {}
    if os.path.exists(REASON_PATH):
        with open(REASON_PATH, encoding="utf-8") as f:
            reason_map = json.load(f)
    html_out = build_html(conn, res, reason_map)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    today = date.today().isoformat()
    out_path = os.path.join(REPORTS_DIR, f"{today}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    conn.execute("INSERT OR REPLACE INTO reports (date,html_path,created_at) VALUES (?,?,?)",
                 (today, out_path, today))
    conn.commit()
    print(f"Raport: {out_path}")
    conn.close()


if __name__ == "__main__":
    main()
