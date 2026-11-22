"""AMU – Akademie múzických umění (HAMU, DAMU, FAMU): společné API akcí všech fakult.

amu.cz/api/events/?upcoming=1 vrací budoucí akce celé AMU (weby hamu/damu/famu sdílejí stejná data).
Časy jsou v UTC, převádějí se na pražský. Místo se odhadne z kategorií, jinak „AMU“.
Interní akce (workshopy, informační schůzky, wellbeing) se vynechávají.
"""
import datetime as dt
import json
import re
from zoneinfo import ZoneInfo

from .spolecne import akce

PRAHA = ZoneInfo("Europe/Prague")
WEB = "https://www.amu.cz"
VYNECHAT_KAT = re.compile(r"\b(workshop|wellbeing|kurz)\b", re.I)
VYNECHAT_NAZEV = re.compile(r"informační schůzk|pro pedagogy|zrušeno|workshop|kurz ", re.I)
MISTA = [  # (kategorie obsahuje, místo)
    ("Sál Martinů", "Sál Martinů, Lichtenštejnský palác (HAMU)"),
    ("Galerie", "Galerie HAMU, Lichtenštejnský palác"),
    ("Inspirace", "Klub Inspirace, Lichtenštejnský palác (HAMU)"),
    ("Katedra jazzové hudby", "Klub Inspirace, Lichtenštejnský palác (HAMU)"),
    ("FAMU", "FAMU, Smetanovo nábřeží 2"),
]
TYPY = [("Koncert", "koncert"), ("Výstava", "vystava"), ("Představení", "divadlo"),
        ("Konference", "prednaska"), ("Přednáška", "prednaska")]


def _cas(s):
    t = dt.datetime.fromisoformat(s).astimezone(PRAHA)
    return t.date(), t.strftime("%H:%M")


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        stranka = 1
        while stranka and stranka <= 10:
            d = json.loads(stahni(f"{url}{'&' if '?' in url else '?'}page={stranka}"))
            for e in d.get("items") or []:
                kat = e.get("categories") or ""
                nazev = e.get("title") or ""
                if not nazev or not e.get("start") or VYNECHAT_KAT.search(kat) or VYNECHAT_NAZEV.search(nazev):
                    continue
                datum, cas = _cas(e["start"])
                konec_datum = konec_cas = None
                if e.get("end"):
                    konec_datum, konec_cas = _cas(e["end"])
                    if konec_datum == datum:
                        konec_datum = None
                    else:
                        konec_cas = None
                misto = next((m for k, m in MISTA if k in kat), "Akademie múzických umění")
                typ = next((t for k, t in TYPY if k in kat), None)
                vysledek.append(akce(nazev=nazev, datum=datum, cas=cas, konec_datum=konec_datum,
                                     konec_cas=konec_cas, misto=misto, typ=typ, znacky=kat,
                                     url=WEB + e["url"] if e.get("url", "").startswith("/") else e.get("url")))
            stranka = d.get("next_page")
    return vysledek
