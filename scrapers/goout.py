"""GoOut – všechny akce v Praze přes veřejné API, které používá web goout.net.

Dotazuje se po dnech (after/before), stránkuje přes scrollId. Názvy akcí a místa jsou
v části "included". Vynechává trvalé položky (isPermanent) a akce v kategorii pro děti.
Každá akce nese polohu místa (a["poloha"]), aby ji šlo ukázat na mapě.
"""
import datetime as dt
import json
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from .spolecne import akce, cisty

PRAHA = ZoneInfo("Europe/Prague")
API = "https://goout.net/services/entities/v1/schedules?"
TYPY = {"concerts": "koncert", "concert": "koncert", "play": "divadlo", "theatre": "divadlo", "theater": "divadlo",
        "exhibitions": "vystava", "exhibition": "vystava", "film": "film", "films": "film", "cinema": "film",
        "talks": "prednaska", "talk": "prednaska", "lectures": "prednaska", "dance": "tanec",
        "festivals": "festival", "festival": "festival", "parties": "spolecenska", "party": "spolecenska",
        "clubbing": "spolecenska", "for_children": None}
DETSKE = {"for_children", "children", "family"}


def _cena(attr):
    p, mena = attr.get("pricing"), (attr.get("currency") or "czk").upper()
    if not p:
        return "zdarma" if attr.get("ticketingState") == "free" else None
    if p == "0":
        return "zdarma"
    return f"{p} {'Kč' if mena == 'CZK' else mena}"


def ziskej(stahni, zdroj, dnes):
    mesto = zdroj.get("mesto_id")
    dni = int(zdroj.get("dni", 21))
    vysledek, videno = [], set()
    for i in range(dni):
        den = dnes + dt.timedelta(days=i)
        od = dt.datetime.combine(den, dt.time(0, 0), PRAHA).isoformat()
        do = dt.datetime.combine(den + dt.timedelta(days=1), dt.time(0, 0), PRAHA).isoformat()
        scroll = None
        for _ in range(40):  # stránky jednoho dne
            q = [("languages[]", "cs"), ("cityIds[]", mesto), ("include", "events,venues"),
                 ("limit", 100), ("after", od), ("before", do)]
            if scroll:
                q.append(("scrollId", scroll))
            d = json.loads(stahni(API + urlencode(q)))
            inc = d.get("included") or {}
            udalosti = {e["id"]: e for e in inc.get("events") or []}
            mista = {v["id"]: v for v in inc.get("venues") or []}
            for s in d.get("schedules") or []:
                if s["id"] in videno:
                    continue
                videno.add(s["id"])
                at = s.get("attributes") or {}
                if at.get("isPermanent") or at.get("state") not in (None, "approved", "cancelled"):
                    continue
                rel = s.get("relationships") or {}
                e = udalosti.get((rel.get("event") or {}).get("id")) or {}
                v = mista.get((rel.get("venue") or {}).get("id")) or {}
                ea = e.get("attributes") or {}
                if DETSKE & set(ea.get("categories") or []):
                    continue
                nazev = ((e.get("locales") or {}).get("cs") or {}).get("name")
                if not nazev:
                    continue
                zac = dt.datetime.fromisoformat(at["startAt"])
                kon = dt.datetime.fromisoformat(at["endAt"]) if at.get("endAt") else None
                if zac.date() > den:  # patří do jiného dne
                    videno.discard(s["id"])
                    continue
                va = v.get("attributes") or {}
                misto = ((v.get("locales") or {}).get("cs") or {}).get("name") or "?"
                stage = ((s.get("locales") or {}).get("cs") or {}).get("stage")
                a = akce(
                    nazev=nazev, datum=zac.date(), cas=zac.strftime("%H:%M") if at.get("hasTime") else None,
                    konec_datum=kon.date() if kon and (kon - zac).days >= 1 else None,
                    konec_cas=kon.strftime("%H:%M") if kon and at.get("hasTimeEnd") and kon.date() == zac.date() else None,
                    misto=f"{misto} – {stage}" if stage else misto,
                    url=((s.get("locales") or {}).get("cs") or {}).get("siteUrl") or s.get("url"),
                    stav="zruseno" if at.get("state") == "cancelled" else
                         "vyprodano" if at.get("ticketingState") in ("sold_out", "soldout") else "neznamo",
                    cena=_cena(at), typ=TYPY.get(ea.get("mainCategory")),
                    znacky=cisty(" · ".join(ea.get("categories") or [])) or None,
                    popis=((e.get("locales") or {}).get("cs") or {}).get("description"),
                )
                if va.get("latitude") and va.get("longitude"):
                    a["poloha"] = [va["latitude"], va["longitude"]]
                vysledek.append(a)
            scroll = (d.get("meta") or {}).get("nextScrollId")
            if not scroll or not d.get("schedules"):
                break
    return vysledek
