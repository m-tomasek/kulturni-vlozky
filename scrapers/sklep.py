"""Divadlo Sklep – termíny z úvodní stránky (blok „next-shows“).

Seznam je rozdělený podle měsíců (<h3>Listopad 2026</h3>), každý termín jsou dvě buňky:
"Ne 29. 11. Besídka 2026" a "Praha, Dobeška, VYPRODÁNO - 19:30" (+ odkaz Koupit vstupenku).
Hrají hlavně v Divadle Dobeška; představení mimo Prahu se označí jako mimo Prahu.
"""
import datetime as dt
import re

from bs4 import BeautifulSoup

from .spolecne import akce, bez_diakritiky, cas, cisty, odvod_rok

WEB = "https://divadlosklep.cz/"


def _misto(text):
    t = re.sub(r",?\s*vyprod[áa]no", "", text, flags=re.I)
    t = re.sub(r"\s*-\s*\d{1,2}[:.]\d{2}.*$", "", t).strip(" ,")
    casti = [c.strip() for c in t.split(",") if c.strip()]
    mesto = casti[0] if casti else ""
    scena = ", ".join(casti[1:])
    if bez_diakritiky(scena).lower().startswith("dobesk"):
        scena = "Divadlo Dobeška"
    return mesto, scena or mesto


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for seznam in s.select(".shows-list"):
            rok = None
            for el in seznam.find_all(["h3", "div"], recursive=True):
                if el.name == "h3":
                    m = re.search(r"(20\d\d)", el.get_text())
                    rok = int(m.group(1)) if m else None
                    continue
                if "row" not in el.get("class", []):
                    continue
                bunky = el.find_all("div", recursive=False)
                for nazev_b, misto_b in zip(bunky[::2], bunky[1::2]):
                    t = cisty(nazev_b.get_text(" "))
                    m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(.+)", t)
                    if not m:
                        continue
                    d, mes, nazev = int(m.group(1)), int(m.group(2)), m.group(3).strip()
                    try:
                        datum = dt.date(rok, mes, d) if rok else odvod_rok(d, mes, dnes)
                    except ValueError:
                        continue
                    mt = cisty(misto_b.get_text(" "))
                    mesto, scena = _misto(mt)
                    if (nazev, datum) in videno:
                        continue
                    videno.add((nazev, datum))
                    odkaz = misto_b.find("a", href=True)
                    vyprodano = "vyprod" in mt.lower()
                    a = akce(
                        nazev=nazev, datum=datum, cas=cas(mt), misto=scena or "Divadlo Sklep", url=WEB,
                        vstupenky=odkaz["href"] if odkaz and not vyprodano else None,
                        stav="vyprodano" if vyprodano else ("volno" if odkaz else "neznamo"),
                        typ="divadlo", znacky="Divadlo Sklep",
                    )
                    a["mimo_prahu"] = bool(mesto) and bez_diakritiky(mesto).lower() not in ("praha", "prague")
                    vysledek.append(a)
    return vysledek
