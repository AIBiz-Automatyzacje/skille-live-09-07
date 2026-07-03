#!/usr/bin/env python3
"""REASON (wsad) — zbiera komplet danych per kampania do oceny przez LLM.

Krok REASON jest krokiem LLM (jak analiza wizualna): ten skrypt dumpuje structured JSON
(metryki w oknach + edycje + analizy wizualne assetów + copy), Claude czyta go i pisze
reason.json (ocena → sugestia per kampania). Bez progów — synteza wszystkich sygnałów.

Użycie: python3 reason_input.py  → JSON na stdout
"""
import json
import os
import sys

import db
import compute
from compute import PROJECT_DIR

PLAN_PATH = os.path.join(PROJECT_DIR, "_plan-marcina.md")
PLAYBOOK_PATH = os.path.join(PROJECT_DIR, "playbook-meta.md")


def _read(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def _plan_marcina():
    """Treść _plan-marcina.md — świadome decyzje Marcina, których REASON nie może 'odkrywać'
    jako problemów ani doradzać ich cofnięcia."""
    return _read(PLAN_PATH)


def _playbook():
    """Playbook Meta (destylat bazy Loomera 2026) — metodyka ocen i rekomendacji.

    Zastępuje ogólne defaulty modelu regułami praktyka: atrybucja, kontrola vs sugestia
    w targetingu, progi budżetowe, ocena kreacji agregatem, kolejność diagnostyki spadków.
    """
    return _read(PLAYBOOK_PATH)


def _adsets(conn, cid):
    """Ad sety kampanii z targetingiem (wiek/płeć/grupy/wykluczenia/budżet) — kontekst setupu."""
    rows = conn.execute(
        "SELECT name, status, daily_budget, targeting FROM adsets WHERE campaign_id=?", (cid,),
    ).fetchall()
    out = []
    for r in rows:
        try:
            t = json.loads(r["targeting"]) if r["targeting"] else {}
        except ValueError:
            t = {}
        out.append({
            "name": r["name"], "status": r["status"],
            "daily_budget_zl": round(r["daily_budget"] / 100) if r["daily_budget"] else None,
            **t,
        })
    return out


def _vis_and_copy(conn, cid):
    """Analizy wizualne assetów + copy warianty kampanii (kontekst do oceny)."""
    vis = conn.execute(
        """SELECT cr.asset_key, cr.asset_type, cr.name, cr.visual_analysis,
                  ROUND(SUM(a.spend),0) spend,
                  ROUND(SUM(a.clicks)*100.0/NULLIF(SUM(a.impressions),0),2) ctr,
                  SUM(a.leads) leads, SUM(a.purchases) purch, SUM(a.impressions) impr
           FROM creatives cr JOIN assets a ON a.asset_key=cr.asset_key
           WHERE a.campaign_id=? AND cr.asset_type IN ('image','video') AND cr.visual_analysis IS NOT NULL
           GROUP BY cr.asset_key ORDER BY spend DESC""", (cid,)).fetchall()
    copy = conn.execute(
        """SELECT cr.copy_text,
                  ROUND(SUM(a.clicks)*100.0/NULLIF(SUM(a.impressions),0),2) ctr, SUM(a.impressions) impr
           FROM assets a JOIN creatives cr ON cr.asset_key=a.asset_key
           WHERE a.campaign_id=? AND a.asset_type IN ('body','title') AND cr.copy_text IS NOT NULL
           GROUP BY cr.copy_text HAVING impr>0 ORDER BY (SUM(a.clicks)*1.0/SUM(a.impressions)) DESC LIMIT 6""",
        (cid,)).fetchall()
    return ([dict(r) for r in vis], [dict(r) for r in copy])


def build_input(conn):
    res = compute.compute_all(conn)
    out = {
        "ref_date": res["ref_date"],
        # Świadome decyzje Marcina — twardy kontekst: nie rekomendować ich cofnięcia
        "plan_marcina": _plan_marcina(),
        # Metodyka ocen: playbook z bazy Loomera 2026 (reguły > defaulty modelu)
        "playbook": _playbook(),
        # Pacing do celu + ekonomia leada z poprzednich live'ów — do panelu decyzyjnego
        "live_context": res.get("live_context"),
        "campaigns": [],
    }
    for c in res["campaigns"]:
        cm = c["campaign"]
        vis, copy = _vis_and_copy(conn, cm["id"])
        out["campaigns"].append({
            "id": cm["id"], "name": cm["name"], "klasa": cm["klasa"],
            "status": cm["status"], "live_group": cm["live_group"],
            # 'form' = formularz błyskawiczny, 'lp' = landing page — inne wyjście z reklamy,
            # inna jakość leada; NIE porównywać CPL między lejkami 1:1
            "funnel": c.get("funnel"),
            "days_inactive": c["days_inactive"], "ref_date": c["ref_date"],
            "periods": c["periods"], "week_vs_prev": {
                "this_week": c["periods"]["this_week"], "prev_week": c["periods"]["prev_week"]},
            "edits": c["edits_in_week"], "adsets": _adsets(conn, cm["id"]),
            "assets": vis, "copy": copy,
        })
    return out


def main():
    conn = db.connect()
    print(json.dumps(build_input(conn), ensure_ascii=False, indent=2))
    conn.close()


if __name__ == "__main__":
    main()
