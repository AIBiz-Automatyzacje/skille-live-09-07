#!/usr/bin/env python3
"""Współdzielone helpery Meta Ads API: env, paginacja, klasyfikacja sprzedaż/lead.

Self-contained (skill marketplace-ready) — nie importuje z innych skilli.
Logika klasyfikacji wg Zadania/projekty/meta-ads/proces-klasyfikacji-kampanii.md.
"""
import os
import re

import requests
from dotenv import load_dotenv

def _find_workspace():
    """Żywy vault (Mac lokalnie / VPS ~/vault), NIE realpath symlinka .claude→vault-git.

    Na VPS .claude jest symlinkiem na vault-git (martwy klon git, którego Obsidian Sync nie
    synchronizuje). Node/Python rozwija symlink w __file__, więc kotwiczymy w env CLAUDE_CRON_WORKSPACE
    albo markerze .obsidian (żywy vault), a nie w ścieżce skryptu. Wzorzec jak w reddit-news.
    """
    env = os.environ.get("CLAUDE_CRON_WORKSPACE")
    if env:
        return os.path.abspath(env)
    for start in (os.getcwd(), os.path.dirname(os.path.abspath(__file__))):
        cur = start
        for _ in range(10):
            if os.path.isdir(os.path.join(cur, ".obsidian")):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


WORKSPACE = _find_workspace()
load_dotenv(os.path.join(WORKSPACE, ".env"))

TOKEN = os.environ["ACCESS_TOKEN"]
ACCOUNT = os.environ["AD_ACCOUNT_ID"]
API = "https://graph.facebook.com/v21.0"

# Klasyfikacja po celu kampanii (pierwszy sygnał — potwierdzany faktycznymi zdarzeniami)
SALES_OBJ = {"OUTCOME_SALES", "CONVERSIONS", "PRODUCT_CATALOG_SALES"}
LEAD_OBJ = {"OUTCOME_LEADS", "LEAD_GENERATION"}

# Miesiące PL (dopełniacz) — do wykrywania tagu live z nazwy kampanii
_MONTHS = ("stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|"
           "wrzesnia|września|pazdziernika|października|listopada|grudnia")
_LIVE_RE = re.compile(rf"live\s*#?\s*(\d{{1,2}})\s*[\.\s]\s*({_MONTHS}|\d{{1,2}})", re.IGNORECASE)

PURCHASE_TYPES = ["offsite_conversion.fb_pixel_purchase", "omni_purchase", "purchase"]
LEAD_TYPES = [
    "lead", "offsite_conversion.fb_pixel_lead", "leadgen.other",
    "onsite_conversion.lead_grouped", "complete_registration",
    "omni_complete_registration", "offsite_complete_registration_add_meta_leads",
    "offsite_conversion.fb_pixel_complete_registration",
]


def api_get(path, params=None):
    """Pojedynczy GET do Graph API. Zwraca (status_code, json)."""
    p = {"access_token": TOKEN}
    if params:
        p.update(params)
    url = path if path.startswith("http") else f"{API}/{path}"
    r = requests.get(url, params=p)
    return r.status_code, r.json()


def get_paged(path, params):
    """GET z podążaniem za paginacją. Zwraca listę wszystkich data[]."""
    p = {"access_token": TOKEN}
    p.update(params)
    url = path if path.startswith("http") else f"{API}/{path}"
    out = []
    while url:
        r = requests.get(url, params=p)
        r.raise_for_status()
        j = r.json()
        out.extend(j.get("data", []))
        url = j.get("paging", {}).get("next")
        p = None  # next zawiera już wszystkie parametry
    return out


def actions_index(actions):
    """Lista actions[] → dict {action_type: float(value)}."""
    if not actions:
        return {}
    return {a["action_type"]: float(a.get("value", 0)) for a in actions}


def pick(idx, types):
    """Pierwsza pasująca wartość wg priorytetu typów (idx = actions_index)."""
    for t in types:
        if t in idx:
            return idx[t]
    return 0.0


def get_lead_custom_conversion_ids():
    """Zbiór ID custom conversions leadowych (zapisy/rejestracje, nie zakup)."""
    _, j = api_get(f"{ACCOUNT}/customconversions", {
        "fields": "name,custom_event_type", "limit": 200,
    })
    lead = set()
    for c in j.get("data", []):
        nm = c.get("name", "").lower()
        if "zakup" in nm or "purchase" in nm or c.get("custom_event_type") == "PURCHASE":
            continue
        lead.add(c["id"])
    return lead


def count_leads(idx, lead_cc_ids):
    """Liczba zdarzeń leadowych: standardowe + leadowe custom conversions."""
    n = pick(idx, LEAD_TYPES)
    for cid in lead_cc_ids:
        n += idx.get(f"offsite_conversion.custom.{cid}", 0)
    return n


def count_purchases(idx):
    """Liczba zakupów wg priorytetu typów purchase."""
    return pick(idx, PURCHASE_TYPES)


def sum_revenue(val_idx):
    """Wartość zakupów (przychód) z action_values wg priorytetu typów purchase."""
    return pick(val_idx, PURCHASE_TYPES)


def classify_campaign(objective, idx, lead_cc_ids):
    """Zwraca 'lead' albo 'sales'. idx = actions_index insightów kampanii.

    Reguła: cel lead → lead; cel sprzedaż ale 0 zakupów + są leady → lead.
    """
    if objective in LEAD_OBJ:
        return "lead"
    purchases = count_purchases(idx)
    leads = count_leads(idx, lead_cc_ids)
    if objective in SALES_OBJ and purchases == 0 and leads > 0:
        return "lead"
    return "sales"


def live_group(name):
    """Tag grupy live wyciągnięty z nazwy kampanii (np. 'live 9 lipca'). None gdy brak.

    Pozwala spiąć kampanie tego samego live'a (aktywne + wstrzymane) i policzyć łączne
    leady. Niejednoznaczne nazwy (bez wzorca 'live <dzień> <miesiąc>') → None; takie
    przypadki można ręcznie dotagować w kolumnie campaigns.live_group (override).
    """
    if not name:
        return None
    m = _LIVE_RE.search(name)
    if not m:
        return None
    return f"live {m.group(1)} {m.group(2).lower()}"
