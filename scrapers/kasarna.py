"""Kasárna Karlín – dlaždice akcí na /cs/program (datum v <time datetime>, čas až na stránce akce)."""
import datetime as dt
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .spolecne import akce, cas, cisty


def ziskej(stahni, zdroj, dnes):
    vysledek, videno, nenacteno = [], set(), 0
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for dl in s.select("div.node--type--event"):
            a = dl.select_one("a.tile-inside")
            t = dl.select_one("time[datetime]")
            n = dl.select_one(".event-title")
            if not a or not t or not n:
                continue
            datum = dt.date.fromisoformat(t["datetime"][:10])
            nazev = cisty(n.get_text())
            odkaz = urljoin(url, a["href"])
            if odkaz in videno:
                continue
            videno.add(odkaz)
            vst = dl.select_one("a.btn[href^=http]")
            c = kc = None
            if datum >= dnes:  # čas je jen na stránce akce
                try:
                    d = BeautifulSoup(stahni(odkaz), "lxml").select_one(".field-name--field-event-time")
                    if d:
                        casy = d.get_text(" ").split("–")
                        c = cas(casy[0])
                        kc = cas(casy[1]) if len(casy) > 1 else None
                except Exception as e:  # noqa: BLE001 – bez času se akce pořád hodí
                    print(f"kasarna: detail {odkaz} nenačten: {e!r}", file=sys.stderr)
                    nenacteno += 1
            vysledek.append(akce(
                nazev=nazev, datum=datum, cas=c, konec_cas=kc, misto="Kasárna Karlín", url=odkaz,
                vstupenky=vst["href"] if vst else None, typ=None,
            ))
    if nenacteno and nenacteno >= max(3, len(vysledek) // 2):
        # bez časů by se akcím změnila identita a všechny by vypadaly jako „přesunuté“ – raději ohlásit chybu zdroje
        raise RuntimeError(f"nenačetlo se {nenacteno} stránek akcí")
    return vysledek
