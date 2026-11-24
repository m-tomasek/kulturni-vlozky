"""Improbox.cz – přehled impro akcí v Česku (představení, workshopy, kurzy, jamy).

Bere se jen horní část stránky (nadcházející akce, před tlačítkem „Zobrazit uplynulé akce“),
jen Praha a jen workshopy, kurzy a jamy (představení mají vlastní zdroje / GoOut).
Karta: zkratka dne („Pá“), den („27“), měsíc („Lis.“), typ akce, město, název s odkazem, pořadatel.
Rok na stránce není – určí se podle dne v týdnu.
"""
import datetime as dt
import re

from bs4 import BeautifulSoup

from .spolecne import akce, bez_diakritiky, cisty

MES = {"led": 1, "uno": 2, "bre": 3, "dub": 4, "kve": 5, "cer": 6, "cec": 7, "srp": 8, "zar": 9, "rij": 10,
       "lis": 11, "pro": 12}
DNY = {"po": 0, "ut": 1, "st": 2, "ct": 3, "pa": 4, "so": 5, "ne": 6}
TYPY = re.compile(r"workshop|kurz|jam|lekce|trénink|trenink", re.I)


def _mesic(t):
    t = bez_diakritiky(t).lower().strip(". ")
    if t.startswith("cerv"):  # červen × červenec
        return 7 if t.startswith("cervene") else 6
    return MES.get(t[:3])


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        text = stahni(url)
        i = text.find("Zobrazit uplynulé")
        s = BeautifulSoup(text[:i] if i > 0 else text, "lxml")
        for k in s.select('div[aria-controls="event-description-collapse"]'):
            sp = [cisty(x.get_text(" ")) for x in k.select("span")]
            if len(sp) < 3 or not sp[1].isdigit():
                continue
            den, mes, wd = int(sp[1]), _mesic(sp[2]), DNY.get(bez_diakritiky(sp[0]).lower()[:2])
            if not mes:
                continue
            obsah = cisty(k.get_text(" "))
            if not re.search(r"\bPraha\b", obsah) or not TYPY.search(obsah):
                continue
            kand = []
            for r in (dnes.year - 1, dnes.year, dnes.year + 1):
                try:
                    d = dt.date(r, mes, den)
                except ValueError:
                    continue
                if wd is None or d.weekday() == wd:
                    kand.append(d)
            if not kand:
                continue
            datum = min(kand, key=lambda d: abs((d - dnes).days))
            a = k.find("a", href=True)
            h3 = k.find("h3")
            if not a:
                continue
            nazev = re.sub(r"^[^\w„\"(]+", "", cisty(a.get_text(" ")))
            vysledek.append(akce(nazev=nazev, datum=datum, misto=zdroj.get("misto") or "Praha",
                                 url=a["href"], typ="workshop",
                                 popis=cisty(h3.get_text(" ")) if h3 else None))
    return vysledek
