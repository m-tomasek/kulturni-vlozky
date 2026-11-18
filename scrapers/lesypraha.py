"""Lesy hl. m. Prahy – akce pro veřejnost (lesypraha.cz/akce): vycházky, workshopy v ekocentrech
(Prales, Kaskáda…), záchranná stanice. Karta article.event.main: nadpis s odkazem, kategorie,
jedno nebo víc dat (span.day), čas od–do, místo.
"""
import re

from bs4 import BeautifulSoup

from .spolecne import akce, cas, cisty, odvod_rok
import datetime as dt

DEN = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d\d)?")


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for art in s.select("article.event.main"):
            h = art.select_one(".headline a[href]")
            if not h:
                continue
            nazev = cisty(h.get_text(" "))
            kategorie = " · ".join(cisty(a.get_text()) for a in art.select(".categories a"))
            od_el, do_el = art.select_one(".time-of-event .from"), art.select_one(".time-of-event .to")
            misto = art.select_one(".place")
            for d in art.select(".date-of-event .day"):
                m = DEN.search(d.get_text(" "))
                if not m:
                    continue
                try:
                    datum = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m.group(3) \
                        else odvod_rok(int(m.group(1)), int(m.group(2)), dnes)
                except ValueError:
                    continue
                if (h["href"], datum) in videno:
                    continue
                videno.add((h["href"], datum))
                vysledek.append(akce(
                    nazev=nazev, datum=datum, cas=cas(od_el.get_text()) if od_el else None,
                    konec_cas=cas(do_el.get_text()) if do_el else None,
                    misto=(cisty(misto.get_text(" ")) if misto else "") or "Lesy hl. m. Prahy", url=h["href"],
                    typ="jine", znacky=kategorie or None,
                ))
    return vysledek
