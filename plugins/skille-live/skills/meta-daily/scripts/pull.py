#!/usr/bin/env python3
"""PULL — pobiera z Meta API aktywne kampanie, ady, asset breakdowny i edycje.

Zwraca znormalizowane struktury (dict/list) gotowe do zapisu w store.py.
Nic nie zapisuje — czysta warstwa odczytu.
"""
import json
import sys
from datetime import date, datetime, timedelta

from compute import window_dates
from meta_common import (
    ACCOUNT, actions_index, api_get, classify_campaign, count_leads,
    count_purchases, get_lead_custom_conversion_ids, get_paged, live_group, sum_revenue,
)

# Breakdown asset → (klucz pola w odpowiedzi, jak wyciągnąć asset_key/name/thumb/copy)
ASSET_BREAKDOWNS = ["image_asset", "video_asset", "body_asset", "title_asset"]


def log(msg):
    print(msg, file=sys.stderr)


def _time_range(since):
    """Jawny zakres od startu kampanii do dziś — zamiast date_preset=maximum.

    `maximum` z time_increment=1 ucina najnowsze tygodnie (kampania wydająca dziś
    pokazywała ostatni dzień sprzed tygodni → fałszywa flaga „stoi"). time_range to naprawia.
    """
    return json.dumps({"since": since[:10], "until": date.today().isoformat()})


def fetch_report_campaigns():
    """Kampanie do raportu + statusy WSZYSTKICH kampanii konta.

    Do raportu: wszystkie ACTIVE + wstrzymane z grupy live, która ma aktywną kampanię.
    Stare wstrzymane kampanie (archiwum poprzednich live'ów) pomijamy — inaczej raport
    wciągałby tysiące historycznych leadów. Wstrzymaną doliczamy tylko, gdy należy do
    bieżącego live'a (ta sama grupa `live_group` co któraś aktywna kampania).
    Statusy wszystkich: reaper — kampania wstrzymana na Meta ma dostać świeży status
    w bazie, nawet gdy wypadła z selekcji (inaczej wisi jako ACTIVE ze starymi danymi).
    Zwraca (selected, statuses) — statuses = {campaign_id: effective_status}.
    """
    _, j = api_get(f"{ACCOUNT}/campaigns", {
        "fields": "name,objective,effective_status,daily_budget,created_time",
        "limit": 200,
    })
    all_camps = j.get("data", [])
    active_groups = {live_group(c.get("name")) for c in all_camps
                     if c.get("effective_status") == "ACTIVE"} - {None}
    selected = []
    for c in all_camps:
        if c.get("effective_status") == "ACTIVE":
            selected.append(c)
        elif live_group(c.get("name")) in active_groups:
            selected.append(c)  # wstrzymana, ale z bieżącej grupy live
    statuses = {c["id"]: c.get("effective_status") for c in all_camps}
    return selected, statuses


def fetch_campaign_actions(campaign_id, since):
    """actions_index insightów kampanii (cały okres) — do klasyfikacji sprzedaż/lead."""
    _, j = api_get(f"{campaign_id}/insights", {
        "fields": "actions", "time_range": _time_range(since), "level": "campaign",
    })
    data = j.get("data", [])
    return actions_index(data[0].get("actions") if data else None)


def fetch_ad_daily(ad_id, since, lead_cc_ids):
    """Dzienne metryki JEDNEJ reklamy (time_increment=1, bez breakdown).

    Suma po reklamach daje czyste dzienne metryki kampanii — poziom kampanii gubi dni
    przy restrukturyzacji adsetów, poziom reklamy jest wiarygodny.
    """
    _, j = api_get(f"{ad_id}/insights", {
        "fields": "impressions,clicks,spend,actions,action_values",
        "time_increment": "1", "time_range": _time_range(since), "level": "ad",
    })
    rows = []
    for row in j.get("data", []):
        idx = actions_index(row.get("actions"))
        val_idx = actions_index(row.get("action_values"))
        rows.append({
            "date": row.get("date_start"),
            "impressions": int(float(row.get("impressions", 0))),
            "clicks": int(float(row.get("clicks", 0))),
            "spend": float(row.get("spend", 0)),
            "leads": count_leads(idx, lead_cc_ids),
            "purchases": count_purchases(idx),
            "revenue": sum_revenue(val_idx),
        })
    return rows


def fetch_campaign_windows(campaign_id, ref, lead_cc_ids):
    """7 okien metryk kampanii przez time_range BEZ time_increment = dokładnie jak Ads Manager.

    Atrybucja konwersji ginęła przy time_increment=1 (okno atrybucji rozkładane na dni
    niedoszacowywało zakupy/leady). Tu każde okno = jeden zagregowany zakres → pełna atrybucja.
    ref = ostatni aktywny dzień kampanii (stojąca kampania pokazuje okna z okresu emisji).
    Daty okien zapisane w wierszu = jedno źródło prawdy, compute ich nie przelicza.
    """
    out = []
    for window, (d_from, d_to) in window_dates(ref).items():
        _, j = api_get(f"{campaign_id}/insights", {
            "fields": "impressions,clicks,spend,reach,frequency,actions,action_values",
            "time_range": json.dumps({"since": d_from, "until": d_to}),
            "level": "campaign",
        })
        data = j.get("data", [])
        row = data[0] if data else {}
        idx = actions_index(row.get("actions"))
        val_idx = actions_index(row.get("action_values"))
        out.append({
            "campaign_id": campaign_id, "window": window,
            "date_from": d_from, "date_to": d_to,
            "impressions": int(float(row.get("impressions", 0))),
            "clicks": int(float(row.get("clicks", 0))),
            "spend": float(row.get("spend", 0)),
            "leads": count_leads(idx, lead_cc_ids),
            "purchases": count_purchases(idx),
            "revenue": sum_revenue(val_idx),
            "reach": int(float(row.get("reach", 0))),
            "frequency": float(row.get("frequency", 0)),
            "link_clicks": int(idx.get("link_click", 0)),
            "lpv": int(idx.get("landing_page_view", 0)),
        })
    return out


def fetch_adsets_targeting(campaign_id):
    """Ad sety kampanii z targetingiem — kontekst dla REASON (doktryna: konfiguracja + dane).

    Wyciąga esencję: wiek/płeć, grupy odbiorców i WYKLUCZENIA (nazwy), cel optymalizacji,
    budżet zestawu. Bez tego raport ocenia wyniki w oderwaniu od tego, DO KOGO reklama leci.
    """
    _, j = api_get(f"{campaign_id}/adsets", {
        "fields": ("name,effective_status,daily_budget,optimization_goal,"
                   "targeting{age_min,age_max,genders,custom_audiences,excluded_custom_audiences}"),
        "limit": 200,
    })
    out = []
    for s in j.get("data", []):
        t = s.get("targeting") or {}
        genders = {1: "mężczyźni", 2: "kobiety"}.get((t.get("genders") or [None])[0], "wszyscy")
        out.append({
            "adset_id": s["id"], "campaign_id": campaign_id,
            "name": s.get("name"), "status": s.get("effective_status"),
            "daily_budget": int(s["daily_budget"]) if s.get("daily_budget") else None,
            "targeting": json.dumps({
                "wiek": f'{t.get("age_min", "?")}-{t.get("age_max", "?")}',
                "plec": genders,
                "optymalizacja": s.get("optimization_goal"),
                "grupy": [a.get("name") for a in (t.get("custom_audiences") or [])],
                "wykluczenia": [a.get("name") for a in (t.get("excluded_custom_audiences") or [])],
            }, ensure_ascii=False),
        })
    return out


def fetch_mailer_signups(group_id):
    """Łączna liczba zapisów na live z grupy MailerLite (organik + płatne). None gdy błąd.

    Meta widzi tylko leady z reklam — MailerLite to źródło prawdy o CAŁOŚCI zapisów,
    więc dzienny snapshot tej liczby umożliwia pacing do celu.
    """
    import os
    import requests
    token = os.environ.get("MAILER_API")
    if not token:
        log("  MAILER_API brak w env — pomijam snapshot zapisów")
        return None
    try:
        r = requests.get(f"https://connect.mailerlite.com/api/groups/{group_id}",
                         headers={"Authorization": f"Bearer {token}"}, timeout=20)
        r.raise_for_status()
        return int(r.json()["data"]["active_count"])
    except (requests.RequestException, KeyError, ValueError) as e:
        log(f"  MailerLite snapshot nieudany: {e}")
        return None


def fetch_ads(campaign_id):
    """WSZYSTKIE reklamy kampanii (też PAUSED/archiwum) — stare kreacje trzymają historię ROAS.

    Pobieranie tylko aktywnych gubiło całą wartość kampanii (np. KursCC: spauzowana stara
    reklama = 90 zakupów/ROAS 2,65; aktywna nowa = 0 zakupów).
    """
    _, j = api_get(f"{campaign_id}/ads", {
        "fields": "name,effective_status",
        "limit": 200,
    })
    return j.get("data", [])


def fetch_object_map(campaign_id):
    """Wszystkie zestawy i reklamy kampanii (też nieaktywne) → mapowanie edycji na kampanię."""
    objs = []
    _, adsets = api_get(f"{campaign_id}/adsets", {"fields": "id", "limit": 200})
    for s in adsets.get("data", []):
        objs.append({"object_id": s["id"], "object_type": "adset", "campaign_id": campaign_id})
    _, ads = api_get(f"{campaign_id}/ads", {"fields": "id", "limit": 200})
    for a in ads.get("data", []):
        objs.append({"object_id": a["id"], "object_type": "ad", "campaign_id": campaign_id})
    return objs


def _asset_meta(breakdown, blob):
    """Z bloku asset (np. row['image_asset']) wyciąga (asset_key, name, thumb, copy)."""
    if breakdown == "image_asset":
        return blob.get("hash"), blob.get("name"), blob.get("url"), None
    if breakdown == "video_asset":
        return blob.get("video_id"), blob.get("video_name"), blob.get("thumbnail_url"), None
    # body_asset / title_asset — to copy, klucz = id, treść = text
    return blob.get("id"), None, None, blob.get("text")


def _emission_dates(ad_id, breakdown, since):
    """{asset_key: (first_day, last_day, active_days)} z dziennego rozkładu impresji.

    Lekkie zapytanie (tylko impressions) z time_increment=1 — wyłącznie do okresu emisji kreacji.
    NIE dotyka konwersji (te liczone lifetime bez increment), więc atrybucja zostaje nietknięta.
    """
    sc, j = api_get(f"{ad_id}/insights", {
        "fields": "impressions", "breakdowns": breakdown,
        "time_increment": "1", "time_range": _time_range(since), "level": "ad",
    })
    if sc != 200:
        return {}
    days = {}  # asset_key → set dni z impr>0
    for row in j.get("data", []):
        blob = row.get(breakdown)
        if not blob or int(float(row.get("impressions", 0))) <= 0:
            continue
        key = _asset_meta(breakdown, blob)[0]
        if not key:
            continue
        days.setdefault(key, set()).add(row.get("date_start"))
    return {k: (min(v), max(v), len(v)) for k, v in days.items() if v}


def fetch_asset_lifetime(ad_id, ad_name, campaign_id, since, lead_cc_ids):
    """Wszystkie 4 breakdowny dla jednej reklamy, lifetime (od since do dziś) BEZ time_increment.

    1 wiersz per asset = dokładne totale z atrybucją Ads Manager. time_increment=1 rozbijał
    atrybucję na dni i niedoszacowywał konwersje (KursCC: 47 vs realne 90 zakupów).
    Zwraca (asset_rows, creative_rows). asset_type bez sufiksu '_asset'.
    """
    asset_rows = []
    creatives = {}
    for breakdown in ASSET_BREAKDOWNS:
        sc, j = api_get(f"{ad_id}/insights", {
            "fields": "impressions,clicks,spend,ctr,actions,action_values",
            "breakdowns": breakdown,
            "time_range": _time_range(since),
            "level": "ad",
        })
        if sc != 200:
            log(f"    [{ad_id}/{breakdown}] status {sc}: {j.get('error', {}).get('message')}")
            continue
        asset_type = breakdown.replace("_asset", "")
        # Okres emisji liczymy tylko dla kreacji wizualnych (grafika/wideo) — dla copy bez sensu.
        emis = _emission_dates(ad_id, breakdown, since) if breakdown in ("image_asset", "video_asset") else {}
        for row in j.get("data", []):
            blob = row.get(breakdown)
            if not blob:
                continue
            key, name, thumb, copy_text = _asset_meta(breakdown, blob)
            if not key:
                continue
            idx = actions_index(row.get("actions"))
            val_idx = actions_index(row.get("action_values"))
            first_day, last_day, active_days = emis.get(key, (None, None, 0))
            asset_rows.append({
                "campaign_id": campaign_id, "ad_id": ad_id, "ad_name": ad_name,
                "asset_type": asset_type, "asset_key": key,
                "impressions": int(float(row.get("impressions", 0))),
                "clicks": int(float(row.get("clicks", 0))),
                "spend": float(row.get("spend", 0)),
                "ctr": float(row.get("ctr", 0)),
                "leads": count_leads(idx, lead_cc_ids),
                "purchases": count_purchases(idx),
                "revenue": sum_revenue(val_idx),
                "first_day": first_day, "last_day": last_day, "active_days": active_days,
            })
            creatives[key] = {
                "asset_key": key, "asset_type": asset_type,
                "name": name, "thumbnail_url": thumb, "copy_text": copy_text,
            }
    return asset_rows, list(creatives.values())


def fetch_activities(since=None):
    """Log edycji z konta (od 'since' jeśli podane). Mapuje campaign_id z extra_data."""
    params = {
        "fields": "event_type,event_time,actor_name,object_id,object_type,object_name,extra_data",
        "limit": 500,
    }
    if since:
        params["since"] = since[:10]
    rows = get_paged(f"{ACCOUNT}/activities", params)
    out = []
    for r in rows:
        extra = r.get("extra_data")
        campaign_id = None
        if isinstance(extra, str):
            import json as _json
            try:
                campaign_id = _json.loads(extra).get("campaign_id")
            except (ValueError, AttributeError):
                campaign_id = None
        out.append({**r, "campaign_id": str(campaign_id) if campaign_id else None})
    return out


def _campaign_ref(day_agg):
    """Ostatni ZAMKNIĘTY dzień z wydatkiem (spend>0) jako date — wokół niego liczone są okna.

    Bieżący (niepełny) dzień pomijamy, żeby okna nie łapały ogryzka „dziś" przy ręcznym
    odpaleniu w środku dnia. Bez dnia z wydatkiem: ostatni zamknięty dzień z danymi, a w
    ostateczności wczoraj.
    """
    today = date.today().isoformat()
    active = [d for d, a in day_agg.items() if a["spend"] > 0 and d < today]
    closed = [d for d in day_agg if d < today]
    ref_str = (max(active) if active else
               max(closed) if closed else
               (date.today() - timedelta(days=1)).isoformat())
    return datetime.strptime(ref_str, "%Y-%m-%d").date()


def pull_all(since=None):
    """Pełny pull. Zwraca campaigns, campaign_daily, assets (lifetime), campaign_windows,
    creatives, activities, ad_objects."""
    lead_cc_ids = get_lead_custom_conversion_ids()
    campaigns_out, campaign_daily_out, assets_out = [], [], []
    creatives_out, objects_out, windows_out, adsets_out = [], [], [], []

    campaigns, statuses = fetch_report_campaigns()
    log(f"Kampanie do raportu (aktywne + wstrzymane z bieżącego live): {len(campaigns)}")
    for c in campaigns:
        cid = c["id"]
        camp_since = (c.get("created_time") or "2024-01-01")[:10]  # cały okres kampanii
        idx = fetch_campaign_actions(cid, camp_since)
        klasa = classify_campaign(c.get("objective"), idx, lead_cc_ids)
        campaigns_out.append({
            "id": cid, "name": c.get("name"), "objective": c.get("objective"),
            "klasa": klasa, "daily_budget": int(c["daily_budget"]) if c.get("daily_budget") else None,
            "status": c.get("effective_status"), "created_time": c.get("created_time"),
            "live_group": live_group(c.get("name")),
        })
        objects_out.extend(fetch_object_map(cid))
        adsets_out.extend(fetch_adsets_targeting(cid))
        ads = fetch_ads(cid)
        log(f"  {c.get('name')} [{klasa}] — reklam (wszystkie statusy): {len(ads)}")
        day_agg = {}  # date → sumy metryk kampanii (z reklam) — trend spend + days_inactive
        for a in ads:
            for d in fetch_ad_daily(a["id"], camp_since, lead_cc_ids):
                agg = day_agg.setdefault(d["date"], {
                    "impressions": 0, "clicks": 0, "spend": 0.0,
                    "leads": 0.0, "purchases": 0.0, "revenue": 0.0})
                for m in agg:
                    agg[m] += d[m]
            arows, crows = fetch_asset_lifetime(a["id"], a.get("name"), cid, camp_since, lead_cc_ids)
            assets_out.extend(arows)
            creatives_out.extend(crows)
        for day, agg in day_agg.items():
            campaign_daily_out.append({
                "campaign_id": cid, "date": day,
                "ctr": round(agg["clicks"] / agg["impressions"] * 100, 4) if agg["impressions"] else 0,
                **agg})
        windows_out.extend(fetch_campaign_windows(cid, _campaign_ref(day_agg), lead_cc_ids))

    activities = fetch_activities(since)
    log(f"Zdarzeń edycji: {len(activities)}")
    return {
        "campaigns": campaigns_out, "campaign_daily": campaign_daily_out,
        "assets": assets_out, "campaign_windows": windows_out,
        "creatives": creatives_out, "activities": activities, "ad_objects": objects_out,
        "adsets": adsets_out, "statuses": statuses,
    }
