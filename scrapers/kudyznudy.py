"""Kudy z nudy (CzechTourism) – kalendář akcí, rubriky „Příroda a ekologie“ a „Komentované prohlídky“
pro Prahu. Agregátor: vypisuje akce jiných pořadatelů (Toulcův dvůr, botanické zahrady, procházky…).

Položka je schema.org Event v mikrodatech: startDate, endDate, name, location, odkaz /akce/…
Čas začátku na přehledu není. Stránka ukazuje nejbližších ~15 akcí (další stránky jen přes formulář),
což při denním sběru stačí – vzdálenější akce přibudou, až se přiblíží.
Trhy, burzy a jarmarky se vynechávají (nejsou to akce o přírodě ani architektuře).
"""
import datetime as dt
import re

from bs4 import BeautifulSoup

from .spolecne import akce, bez_diakritiky, cisty

ZAKLAD = "https://www.kudyznudy.cz"
PRYC = re.compile(r"\btrh|\btrhy|burz|jarmark|vanocni trh|adventni trh|pro deti|detsk", re.I)


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        rubrika = zdroj.get("rubrika") or ("komentovaná prohlídka" if "komentovane-prohlidky" in url else "příroda a ekologie")
        for it in s.select('[itemtype$="schema.org/Event"]'):
            jmeno = it.select_one('[itemprop="name"]')
            zac = it.select_one('meta[itemprop="startDate"]')
            if not (jmeno and zac):
                continue
            nazev = cisty(jmeno.get_text(" "))
            if PRYC.search(bez_diakritiky(nazev).lower()):
                continue
            try:
                od = dt.date.fromisoformat(zac["content"][:10])
                kon = it.select_one('meta[itemprop="endDate"]')
                do = dt.date.fromisoformat(kon["content"][:10]) if kon else None
            except ValueError:
                continue
            odkaz = it.select_one("h3 a[href]") or it.select_one("a[href]")
            href = (ZAKLAD + odkaz["href"]) if odkaz and odkaz["href"].startswith("/") else (odkaz["href"] if odkaz else url)
            if (href, od) in videno:
                continue
            videno.add((href, od))
            misto = it.select_one('[itemprop="location"] [itemprop="name"]')
            popis = it.select_one('meta[itemprop="description"]')
            vysledek.append(akce(
                nazev=nazev, datum=od, konec_datum=do if do and do != od else None,
                misto=cisty(misto.get_text(" ")) if misto else None, url=href,
                popis=popis["content"] if popis else None, znacky=rubrika,
                typ=zdroj.get("typ_akce", "jine"),
            ))
    return vysledek
