import datetime as dt
import json
from zoneinfo import ZoneInfo

from .spolecne import akce

PRAHA = ZoneInfo("Europe/Prague")


def _udalosti(html):
    """Wix vkládá data akcí jako JSON: najdi všechna pole "events":[...]."""
    dec = json.JSONDecoder()
    klic = '"events":{"events":['
    i = html.find(klic)
    vysledek = []
    while i != -1:
        start = i + len('"events":{"events":')
        try:
            pole, _ = dec.raw_decode(html, start)
            vysledek.extend(pole)
        except json.JSONDecodeError:
            pass
        i = html.find(klic, start)
    return vysledek


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    for url in zdroj["urls"]:
        for e in _udalosti(stahni(url)):
            if e.get("id") in videno:
                continue
            videno.add(e.get("id"))
            sch = (e.get("scheduling") or {}).get("config") or {}
            if not sch.get("startDate"):
                continue
            zac = dt.datetime.fromisoformat(sch["startDate"].replace("Z", "+00:00")).astimezone(PRAHA)
            kon = None
            if sch.get("endDate") and not sch.get("endDateHidden"):
                kon = dt.datetime.fromisoformat(sch["endDate"].replace("Z", "+00:00")).astimezone(PRAHA)
            # Letka prodává vstupenky mimo Wix (registrace typu „externí“),
            # pole soldOut je proto nespolehlivé – dostupnost neznáme.
            stav = "neznamo"
            loc = e.get("location") or {}
            adresa = loc.get("address") or ""
            detail = f"https://www.klubletka.cz/event-details/{e['slug']}" if e.get("slug") else None
            vysledek.append(akce(
                nazev=e.get("title", ""), datum=zac.date(), cas=zac.strftime("%H:%M"),
                konec_datum=kon.date() if kon and kon.date() != zac.date() else None,
                konec_cas=kon.strftime("%H:%M") if kon else None,
                misto="Klub Letka", typ=None, url=detail, vstupenky=detail, stav=stav,
                popis=e.get("description"), mimo_prahu=bool(adresa) and "Praha" not in adresa,
            ))
    return vysledek
