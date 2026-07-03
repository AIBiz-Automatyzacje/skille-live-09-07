#!/usr/bin/env python3
"""COMPUTE — liczy metryki kampanii i assetów w oknach czasowych + edit-flag.

Czyta z meta-ads.db. Okna kampanii z campaign_windows (dokładna atrybucja, bez time_increment),
days_inactive/trend z campaign_daily, per-asset lifetime z assets. Wskaźniki ważone (sum/sum), nie AVG.
Brak progów alertów — zwraca wartości, ocenę robi warstwa REASON.
"""
import json
import os
from datetime import date, datetime, timedelta

import db
from meta_common import WORKSPACE

PROJECT_DIR = os.path.join(WORKSPACE, "Zadania", "projekty", "meta-ads")
LIVE_CONFIG = os.path.join(PROJECT_DIR, "live-config.json")
BENCHMARKS = os.path.join(PROJECT_DIR, "benchmarki-livow.json")

# Edycje istotne dla czystości porównań (reszta = szum: billing, delivery, run_status)
SIGNIFICANT_EDITS = {
    "edit_images", "add_images", "update_ad_creative", "update_ad_set_target_spec",
    "update_campaign_budget", "update_ad_set_budget",
    "update_ad_set_optimization_goal", "update_ad_set_bid_strategy",
}


def _d(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def window_dates(ref):
    """Okna względem ref (date). Zwraca dict {nazwa: (from, to)} inclusive, jako stringi."""
    def rng(days_back_from, days_back_to):
        return ((ref - timedelta(days=days_back_from)).isoformat(),
                (ref - timedelta(days=days_back_to)).isoformat())
    return {
        "today": (ref.isoformat(), ref.isoformat()),
        "yesterday": rng(1, 1),
        "short": rng(2, 0),       # ostatnie 3 dni
        "week": rng(6, 0),        # ostatnie 7 dni
        "month": rng(29, 0),      # ostatnie 30 dni
        "this_week": rng(6, 0),
        "prev_week": rng(13, 7),
    }


def derive(s):
    """s = wiersz sum (impressions,clicks,spend,leads,purchases,revenue,days [+reach,frequency,
    link_clicks,lpv]). Dodaje wskaźniki."""
    impr = s["impressions"] or 0
    clicks = s["clicks"] or 0
    spend = s["spend"] or 0
    leads = s["leads"] or 0
    purch = s["purchases"] or 0
    rev = s["revenue"] or 0
    days = s["days"] or 0
    lpv = s.get("lpv") or 0
    return {
        "impressions": impr, "clicks": clicks, "spend": round(spend, 2),
        "leads": round(leads, 1), "purchases": round(purch, 1), "revenue": round(rev, 2),
        "days": days,
        "ctr": round(clicks / impr * 100, 3) if impr else 0.0,
        # CPM/CPC — rozróżnienie „drożeje aukcja" od „zmęczona kreacja" (audyt 03.07)
        "cpm": round(spend / impr * 1000, 2) if impr else None,
        "cpc": round(spend / clicks, 2) if clicks else None,
        "cpl": round(spend / leads, 2) if leads else None,
        "cpa": round(spend / purch, 2) if purch else None,
        "roas": round(rev / spend, 2) if spend else None,
        "spend_per_day": round(spend / days, 2) if days else 0.0,
        "leads_per_day": round(leads / days, 1) if days else 0.0,
        "purch_per_day": round(purch / days, 2) if days else 0.0,
        "reach": s.get("reach") or 0,
        "frequency": round(s.get("frequency") or 0, 2),
        "link_clicks": s.get("link_clicks") or 0,
        "lpv": lpv,
        # konwersja landinga (leady/LPV) — sens tylko dla kampanii z ruchem na LP;
        # forma błyskawiczna zbiera leady bez LPV (leads>lpv = wskaźnik bez sensu → None)
        "lp_conv": round(leads / lpv * 100, 1) if lpv >= 30 and leads and leads <= lpv else None,
    }


def _window_days(conn, cid, date_from, date_to):
    """Realne dni z wydatkiem (spend>0) w oknie — do precyzyjnego spend_per_day.

    Konwersje/spend okna pochodzą z campaign_windows (dokładna atrybucja), ale liczbę dni
    bierzemy z campaign_daily, żeby spend/dzień nie dzielił przez dni kalendarzowe bez emisji.
    """
    row = conn.execute(
        """SELECT COUNT(DISTINCT date) days FROM campaign_daily
           WHERE campaign_id=? AND spend>0 AND date BETWEEN ? AND ?""",
        (cid, date_from, date_to),
    ).fetchone()
    return row["days"] or 0


def read_windows(conn, cid):
    """Okna kampanii z campaign_windows (dokładne konwersje). days doliczone z campaign_daily."""
    out = {}
    keys = None
    for r in conn.execute("SELECT * FROM campaign_windows WHERE campaign_id=?", (cid,)).fetchall():
        if keys is None:
            keys = set(r.keys())
        out[r["window"]] = derive({
            "impressions": r["impressions"], "clicks": r["clicks"], "spend": r["spend"],
            "leads": r["leads"], "purchases": r["purchases"], "revenue": r["revenue"],
            "days": _window_days(conn, cid, r["date_from"], r["date_to"]),
            "reach": r["reach"] if "reach" in keys else 0,
            "frequency": r["frequency"] if "frequency" in keys else 0,
            "link_clicks": r["link_clicks"] if "link_clicks" in keys else 0,
            "lpv": r["lpv"] if "lpv" in keys else 0,
        })
    return out


def significant_edits(conn, cid, date_from, date_to):
    """Istotne edycje kampanii w oknie (kreacja/target/budżet/optymalizacja)."""
    rows = conn.execute(
        """SELECT event_time, event_type, object_name, object_type, extra_data
           FROM activities
           WHERE substr(event_time,1,10) BETWEEN ? AND ?
             AND (campaign_id=? OR object_id=?
                  OR object_id IN (SELECT object_id FROM ad_objects WHERE campaign_id=?))
           ORDER BY event_time DESC""",
        (date_from, date_to, cid, cid, cid),
    ).fetchall()
    out = []
    for r in rows:
        if r["event_type"] not in SIGNIFICANT_EDITS:
            continue
        out.append({
            "time": r["event_time"][:10], "type": r["event_type"],
            "object": r["object_name"], "detail": _budget_detail(r),
        })
    return out


def _budget_detail(r):
    """Dla zmian budżetu wyciąga 'X zł → Y zł'. Inaczej pusty string."""
    if "budget" not in r["event_type"]:
        return ""
    import json
    try:
        ed = json.loads(r["extra_data"])
        old = ed.get("old_value", {}).get("old_value")
        new = ed.get("new_value", {}).get("new_value")
        if old and new:
            return f"{int(old)/100:.0f} zł → {int(new)/100:.0f} zł"
    except (ValueError, TypeError, AttributeError):
        pass
    return ""


def campaign_last_active(conn, cid):
    """Ostatni ZAMKNIĘTY dzień, w którym kampania wydała (spend>0). Dziś pomijamy. None jeśli nigdy."""
    today = date.today().isoformat()
    row = conn.execute(
        "SELECT MAX(date) d FROM campaign_daily WHERE campaign_id=? AND spend>0 AND date < ?",
        (cid, today),
    ).fetchone()
    return _d(row["d"]) if row and row["d"] else None


def compute_campaign(conn, campaign, ref_global):
    """Pełna analiza jednej kampanii. Okna liczone od ostatniego AKTYWNEGO dnia kampanii.

    Dzięki temu kampania, która stoi od dni, pokazuje swoje realne metryki z okresu emisji,
    a osobno flagujemy ile dni nie wydaje.
    """
    cid = campaign["id"]
    ref = campaign_last_active(conn, cid) or ref_global
    days_inactive = (ref_global - ref).days
    edits_from, edits_to = window_dates(ref)["week"]
    return {
        "campaign": dict(campaign),
        "ref_date": ref.isoformat(),
        "days_inactive": days_inactive,   # 0 = wydaje na bieżąco; >1 = stoi
        "funnel": campaign_funnel(conn, cid),  # 'form' | 'lp' — inne wyjście z reklamy
        "periods": read_windows(conn, cid),
        "edits_in_week": significant_edits(conn, cid, edits_from, edits_to),
        "assets": compute_assets(conn, cid),
        "lead_series": lead_daily(conn, cid) if campaign["klasa"] == "lead" else [],
    }


def lead_daily(conn, cid):
    """Dzienna liczba leadów kampanii (z campaign_daily) — do wykresu trendu + sumy.

    Leady mają w praktyce natychmiastową atrybucję (zapis formularza = dzień kliknięcia),
    więc dzienny rozkład z time_increment jest tu wiarygodny.
    """
    today = date.today().isoformat()
    rows = conn.execute(
        "SELECT date, leads FROM campaign_daily WHERE campaign_id=? AND date < ? ORDER BY date",
        (cid, today),
    ).fetchall()
    return [{"date": r["date"], "leads": r["leads"] or 0} for r in rows]


def campaign_total_leads(conn, cid, as_of=None):
    """Łączne leady kampanii do dnia `as_of` włącznie (domyślnie: ostatni zamknięty dzień).

    Suma z campaign_daily — pozwala policzyć stan leadów na dowolny dzień (też wstecz,
    do przeliczenia starszych raportów).
    """
    cutoff = (as_of or date.today().isoformat())
    op = "<=" if as_of else "<"
    row = conn.execute(
        f"SELECT SUM(leads) s FROM campaign_daily WHERE campaign_id=? AND date {op} ?",
        (cid, cutoff),
    ).fetchone()
    return row["s"] or 0.0


def live_summary(conn, computed, as_of=None):
    """Łączne leady per grupa live — tylko grupy z aktywną kampanią (bieżący live).

    Grupy w 100% wstrzymane (archiwum poprzednich live'ów) pomijamy. Rozbicie na leady
    z aktywnych i wstrzymanych kampanii daje insight 'ilu realnie zapisało się na live'.
    """
    groups = {}
    for c in computed:
        g = c["campaign"].get("live_group")
        if g:
            groups.setdefault(g, []).append(c["campaign"])
    out = []
    for g, members in groups.items():
        if not any(m["status"] == "ACTIVE" for m in members):
            continue  # sama wstrzymane = archiwum, nie bieżący live
        active = paused = 0.0
        detail = []
        for m in members:
            leads = campaign_total_leads(conn, m["id"], as_of)
            if m["status"] == "ACTIVE":
                active += leads
            else:
                paused += leads
            detail.append({"name": m["name"], "status": m["status"], "leads": leads})
        out.append({
            "group": g, "leads_active": active, "leads_paused": paused,
            "leads_total": active + paused,
            "campaigns": sorted(detail, key=lambda d: -d["leads"]),
        })
    return sorted(out, key=lambda x: -x["leads_total"])


def _load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def live_context(conn, ref):
    """Pacing do celu + ekonomia leada — warstwa, której panel Meta nie pokazuje.

    Zapisy ŁĄCZNE (organik+płatne) z dziennych snapshotów MailerLite (live_signups),
    cel i data live'a z live-config.json, ekonomia z benchmarki-livow.json (poprzednie
    live'y: przychód kasowy na zapis wg kodów rabatowych). None gdy brak configu.
    """
    cfg = _load_json(LIVE_CONFIG)
    if not cfg or not cfg.get("mailer_group_id"):
        return None
    gid = cfg["mailer_group_id"]
    snaps = conn.execute(
        "SELECT date, signups FROM live_signups WHERE group_id=? ORDER BY date", (gid,),
    ).fetchall()
    if not snaps:
        return None
    latest = snaps[-1]
    # dzienne tempo zapisów (wszystkie źródła) = delta snapshotów; delta z dnia D
    # odzwierciedla zapisy z dnia D-1 (snapshoty robione rano)
    deltas = [{"date": b["date"], "signups": b["signups"] - a["signups"]}
              for a, b in zip(snaps, snaps[1:])]
    rate = None
    if deltas:
        last = deltas[-3:]  # średnia z 3 dni — jeden dzień to za mała próba na pacing
        rate = round(sum(d["signups"] for d in last) / len(last), 1)
    live_date = _d(cfg["live_date"])
    days_left = (live_date - date.today()).days
    tmin, tmax = cfg.get("target_min"), cfg.get("target_max")
    needed = None
    if tmin and days_left > 0:
        needed = round(max(tmin - latest["signups"], 0) / days_left, 1)
    # REKONSYLIACJA Meta ↔ lista (audyt 03.07): leady wg Meta vs realny przyrost listy.
    # Meta liczy duplikaty/osoby z bazy/niespłynięte formularze — realny koszt NOWEGO
    # adresu bywa wyższy niż raportowany CPL. Porównujemy dobę zapisową ostatniej delty.
    recon = None
    if deltas and cfg.get("live_group"):
        d_day = (_d(deltas[-1]["date"]) - timedelta(days=1)).isoformat()
        row = conn.execute(
            """SELECT SUM(cd.leads) l, SUM(cd.spend) s FROM campaign_daily cd
               JOIN campaigns c ON c.id=cd.campaign_id
               WHERE c.live_group=? AND cd.date=?""",
            (cfg["live_group"], d_day),
        ).fetchone()
        meta_leads = row["l"] or 0
        spend = row["s"] or 0
        list_delta = deltas[-1]["signups"]
        recon = {
            "date": d_day,
            "meta_leads": round(meta_leads),
            "list_delta": list_delta,
            "spend": round(spend, 2),
            "cpl_meta": round(spend / meta_leads, 2) if meta_leads else None,
            # koszt nowego adresu na liście — górna granica (delta zawiera też organik)
            "cpl_list": round(spend / list_delta, 2) if list_delta > 0 else None,
        }
    # PROGNOZA (audyt 03.07): dokąd dojedziemy obecnym tempem + luka w złotówkach
    forecast = None
    if rate is not None and days_left > 0 and tmin:
        projected = round(latest["signups"] + rate * days_left)
        gap_total = max(tmin - projected, 0)
        cpl_ref = (recon or {}).get("cpl_meta") or 20.0
        forecast = {
            "projected": projected,
            "gap_to_min": gap_total,
            "gap_per_day": round(gap_total / days_left, 1),
            "extra_budget_per_day": round(gap_total / days_left * cpl_ref),
            "cpl_ref": cpl_ref,
        }
    return {
        "config": cfg,
        "signups_total": latest["signups"],       # MailerLite: organik + płatne
        "signups_date": latest["date"],
        "daily_series": deltas[-14:],
        "rate_per_day": rate,                     # None dopóki < 2 snapshoty
        "days_to_live": days_left,
        "target_min": tmin, "target_max": tmax,
        "needed_per_day": needed,                 # ile zapisów/dzień do celu min
        "recon": recon,
        "forecast": forecast,
        "benchmarks": _load_json(BENCHMARKS),
    }


def campaign_funnel(conn, cid):
    """Typ lejka kampanii: 'form' (formularz błyskawiczny) | 'lp' (landing page) | None.

    Z celu optymalizacji ad setów. Kluczowe dla oceny: lead z formularza i lead z landinga
    to inne wyjście z reklamy i inna jakość — CPL między nimi nie porównuje się 1:1.
    """
    rows = conn.execute("SELECT targeting FROM adsets WHERE campaign_id=?", (cid,)).fetchall()
    goals = set()
    for r in rows:
        try:
            goals.add((json.loads(r["targeting"]) or {}).get("optymalizacja"))
        except (ValueError, TypeError):
            pass
    if "LEAD_GENERATION" in goals:
        return "form"
    if goals & {"OFFSITE_CONVERSIONS", "VALUE", "LANDING_PAGE_VIEWS", "LINK_CLICKS"}:
        return "lp"
    return None


def compute_assets(conn, cid):
    """Per image/video asset: lifetime totale z tabeli `assets` (1 wiersz/asset, agregat po reklamach).

    total = cała historia kreacji z dokładną atrybucją (bez time_increment). CTR/ROAS liczone
    z sum (derive), nie z surowego ctr per wiersz. Sortowane malejąco po wydatku.
    """
    out = {"image": [], "video": []}
    for asset_type in ("image", "video"):
        rows = conn.execute(
            """SELECT a.asset_key, c.name, c.thumbnail_url,
                      SUM(a.impressions) impressions, SUM(a.clicks) clicks, SUM(a.spend) spend,
                      SUM(a.leads) leads, SUM(a.purchases) purchases, SUM(a.revenue) revenue,
                      MIN(a.first_day) first_day, MAX(a.last_day) last_day, SUM(a.active_days) active_days
               FROM assets a LEFT JOIN creatives c ON c.asset_key=a.asset_key
               WHERE a.campaign_id=? AND a.asset_type=?
               GROUP BY a.asset_key""",
            (cid, asset_type),
        ).fetchall()
        for r in rows:
            total = derive({
                "impressions": r["impressions"], "clicks": r["clicks"], "spend": r["spend"],
                "leads": r["leads"], "purchases": r["purchases"], "revenue": r["revenue"], "days": 1,
            })
            out[asset_type].append({
                "asset_key": r["asset_key"], "name": r["name"],
                "thumbnail_url": r["thumbnail_url"], "total": total,
                "first_day": r["first_day"], "last_day": r["last_day"],
                "active_days": r["active_days"] or 0,
            })
        out[asset_type].sort(key=lambda x: x["total"]["spend"], reverse=True)
    return out


def latest_date(conn):
    """Ostatni ZAMKNIĘTY dzień z metrykami (bieżący, niepełny dzień pomijamy)."""
    today = date.today().isoformat()
    row = conn.execute(
        "SELECT MAX(date) d FROM campaign_daily WHERE date < ?", (today,)).fetchone()
    return _d(row["d"]) if row and row["d"] else date.today() - timedelta(days=1)


def _has_data(c):
    """Czy kampania ma jakiekolwiek dane w oknie 30 dni (impresje lub wydatek).

    Wyłączone kampanie bez żadnej historii (zero wszędzie) nie wnoszą nic do raportu
    — pomijamy je, żeby nie zaśmiecały widoku ani oceny REASON.
    """
    m = c["periods"]["month"]
    return (m["impressions"] or 0) > 0 or (m["spend"] or 0) > 0


def compute_all(conn):
    """Analiza wszystkich kampanii z bazy. Kampanie bez żadnych danych pomijane."""
    ref = latest_date(conn)
    camps = conn.execute("SELECT * FROM campaigns ORDER BY klasa DESC, name").fetchall()
    computed = [compute_campaign(conn, c, ref) for c in camps]
    with_data = [c for c in computed if _has_data(c)]
    return {
        "ref_date": ref.isoformat(),
        "campaigns": with_data,
        "skipped": [c["campaign"]["name"] for c in computed if not _has_data(c)],
        "live_groups": live_summary(conn, with_data),
        "live_context": live_context(conn, ref),
    }
