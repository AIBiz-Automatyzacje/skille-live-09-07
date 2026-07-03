#!/usr/bin/env python3
"""Benchmark historyczny: kumulacja zapisów z reklam poprzednich live'ów dzień po dniu.

Zaciąga z Meta API dzienne leady WSTRZYMANYCH kampanii poprzednich live'ów (wciąż siedzą
na koncie) i zapisuje do benchmarki-livow.json krzywą „ile zapisów z reklam było na X dni
przed live". Dzięki temu dzienny raport może powiedzieć: „na 6 dni przed live 21.05
reklamy miały ~N zapisów — teraz macie M". Uruchamiać raz po każdym live (odświeżenie).

Użycie: python3 benchmark_livow.py
"""
import json
import sys
from datetime import datetime, timedelta

import compute
from meta_common import (ACCOUNT, actions_index, api_get, count_leads,
                         get_lead_custom_conversion_ids, live_group)

MAX_DAYS_BEFORE = 14


def log(msg):
    print(msg, file=sys.stderr)


def month_tag(iso_date):
    """'2026-05-21' → 'live 21 maja' (dopasowanie do live_group z nazw kampanii)."""
    months = {1: "stycznia", 2: "lutego", 3: "marca", 4: "kwietnia", 5: "maja", 6: "czerwca",
              7: "lipca", 8: "sierpnia", 9: "września", 10: "października", 11: "listopada", 12: "grudnia"}
    d = datetime.strptime(iso_date, "%Y-%m-%d")
    return f"live {d.day} {months[d.month]}"


def fetch_daily_leads(campaign_id, since, until, lead_cc_ids):
    """{data: leady} kampanii z time_increment=1 (leady mają atrybucję natychmiastową)."""
    _, j = api_get(f"{campaign_id}/insights", {
        "fields": "actions", "time_increment": "1", "level": "campaign",
        "time_range": json.dumps({"since": since, "until": until}),
    })
    out = {}
    for row in j.get("data", []):
        out[row["date_start"]] = count_leads(actions_index(row.get("actions")), lead_cc_ids)
    return out


def main():
    bench = compute._load_json(compute.BENCHMARKS)
    if not bench:
        log("Brak benchmarki-livow.json — najpierw uzupełnij dane live'ów.")
        return
    lead_cc_ids = get_lead_custom_conversion_ids()
    _, j = api_get(f"{ACCOUNT}/campaigns", {"fields": "name", "limit": 200})
    by_group = {}
    for c in j.get("data", []):
        g = live_group(c.get("name"))
        if g:
            by_group.setdefault(g, []).append(c["id"])
    for l in bench["livy"]:
        # grupa z daty live; wyjątek: live 02.04 nazywany w kampaniach „live 26 marca"
        tags = {month_tag(l["data"])}
        if "26 marca" in l["live"]:
            tags.add("live 26 marca")
        cids = [cid for t in tags for cid in by_group.get(t, [])]
        if not cids:
            log(f"  {l['live']}: brak kampanii z tagiem {tags} — pomijam")
            continue
        live_d = datetime.strptime(l["data"], "%Y-%m-%d").date()
        since = (live_d - timedelta(days=MAX_DAYS_BEFORE)).isoformat()
        daily = {}
        for cid in cids:
            for day, n in fetch_daily_leads(cid, since, live_d.isoformat(), lead_cc_ids).items():
                daily[day] = daily.get(day, 0) + n
        # kumulacja od początku kampanii do dnia D: dolicz leady sprzed okna 14 dni
        base = 0
        for cid in cids:
            _, jj = api_get(f"{cid}/insights", {"fields": "actions", "level": "campaign",
                                                "time_range": json.dumps({"since": "2025-11-01", "until": (live_d - timedelta(days=MAX_DAYS_BEFORE + 1)).isoformat()})})
            data = jj.get("data", [])
            if data:
                base += count_leads(actions_index(data[0].get("actions")), lead_cc_ids)
        cum, curve = base, {}
        for off in range(MAX_DAYS_BEFORE, -1, -1):
            day = (live_d - timedelta(days=off)).isoformat()
            cum += daily.get(day, 0)
            curve[str(-off)] = round(cum)
        l["reklamy_kumulacja_przed_live"] = curve
        log(f"  {l['live']}: kampanii {len(cids)}, kumulacja D-7={curve.get('-7')}, D-0={curve.get('0')}")
    bench["kumulacja_info"] = ("reklamy_kumulacja_przed_live = łączna liczba leadów z reklam kampanii "
                               "danego live'a od startu kampanii do dnia -N przed live (0 = dzień live).")
    with open(compute.BENCHMARKS, "w", encoding="utf-8") as f:
        json.dump(bench, f, ensure_ascii=False, indent=2)
    log("Zapisano krzywe do benchmarki-livow.json")


if __name__ == "__main__":
    main()
