"""CAMP – Centrum architektury a městského plánování (praha.camp/program).

Program je na jedné stránce jako karty: odkaz /program/detail/…, štítky (přednáška, kino, „kapacita
naplněna“, „pro děti“…), <time datetime="2026-11-24"> a <time datetime="19:00/22:00">, název.
Akce pro děti se vynechávají (stejně jako u ostatních zdrojů). Konají se hlavně v CAMPu v Karlíně,
ale některé (procházky, Archirun) jinde – místo z karty nevyčteme, uvádí se CAMP.
"""
import datetime as dt
import re

from bs4 import BeautifulSoup

from .spolecne import akce, cisty

ZAKLAD = "https://praha.camp"
TYPY = {"přednáška": "prednaska", "diskuze": "prednaska", "debata": "prednaska", "talk show": "prednaska",
        "kino": "film", "film": "film", "vernisáž": "vystava", "výstava": "vystava", "koncert": "koncert",
        "workshop": "jine", "procházka": "jine", "komentovaná prohlídka": "jine", "tour": "jine"}


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for karta in s.select('a.card[href*="/program/detail/"]'):
            nazev_el = karta.select_one(".card__title")
            if not nazev_el:
                continue
            datum = cas = konec_cas = None
            for t in karta.select("time[datetime]"):
                v = t["datetime"]
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) and not datum:
                    datum = dt.date.fromisoformat(v)
                m = re.fullmatch(r"(\d{1,2}:\d{2})(?:/(\d{1,2}:\d{2}))?", v)
                if m and not cas:
                    cas, konec_cas = m.group(1).zfill(5), (m.group(2) or "").zfill(5) or None
            if not datum:
                continue
            stitky = [cisty(t.get_text()) for t in karta.select(".card__tags .tag")]
            male = [x.lower() for x in stitky]
            if any(x in ("pro děti", "pro rodiče") or re.match(r"\d+\s*[–-]\s*\d+\s*let", x) for x in male):
                continue
            href = ZAKLAD + karta["href"]
            if href in videno:
                continue
            videno.add(href)
            typ = next((TYPY[x] for x in male if x in TYPY), None)
            vysledek.append(akce(
                nazev=nazev_el.get_text(" "), datum=datum, cas=cas, konec_cas=konec_cas,
                misto="CAMP – Centrum architektury a městského plánování", url=href,
                stav="vyprodano" if "kapacita naplněna" in male else "neznamo",
                typ=typ, znacky=" · ".join(x for x in stitky if x.lower() != "kapacita naplněna") or None,
            ))
    return vysledek
