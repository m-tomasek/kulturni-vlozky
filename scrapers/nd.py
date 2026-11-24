"""Národní divadlo – celý program z Atom feedu /eventfeed (asi 100 nejbližších představení všech scén).

Název položky: „24.11.2026 17:30 - Státní opera - Národní divadlo - "Dramaturgický úvod | Don Quijote"“.
Patří sem i doprovodné programy ND+ (dílny pro veřejnost, úvody); dílny pro školy vyřadí pravidla.
"""
import datetime as dt
import html
import re

from .spolecne import akce, cisty

POLOZKA = re.compile(r"<entry>(.*?)</entry>", re.S)
TITUL = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(20\d\d)\s+(\d{1,2}:\d{2})\s*-\s*(.*?)\s*-\s*\"(.*)\"\s*$", re.S)


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    vynechat = re.compile(zdroj["vynechat"], re.I) if zdroj.get("vynechat") else None
    for url in zdroj["urls"]:
        for e in POLOZKA.findall(stahni(url)):
            t = re.search(r"<title>(.*?)</title>", e, re.S)
            m = TITUL.match(html.unescape(t.group(1)).strip()) if t else None
            if not m:
                continue
            d, mes, r, cas, scena, nazev = m.groups()
            if vynechat and vynechat.search(nazev):
                continue
            scena = re.sub(r"\s*-\s*Národní divadlo$", "", cisty(scena)).replace(" - ", " – ")
            scena = re.sub(r"^.*?(Národní divadlo|Státní opera|Stavovské divadlo|Nová scéna|Divadlo Kolowrat)", r"\1", scena)
            odkaz = re.search(r'<link[^>]*href="([^"]+)"', e)
            popis = re.search(r"<summary>(.*?)</summary>", e, re.S)
            vysledek.append(akce(nazev=cisty(nazev), datum=dt.date(int(r), int(mes), int(d)), cas=cas,
                                 misto=scena or "Národní divadlo",
                                 url=html.unescape(odkaz.group(1)) if odkaz else "https://www.narodni-divadlo.cz/",
                                 popis=cisty(html.unescape(popis.group(1))) if popis else None))
    return vysledek
