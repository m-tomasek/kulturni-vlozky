"""archiweb.cz – kalendář architektonických akcí (výstavy, přednášky, workshopy) z celé ČR i ciziny.

Položka: <article><a href="/e/…" title="…"> … .advertisement__title, .advertisement__name (podtitul),
.advertisement__place (místo), .advertisement__date („05.12.2026“ nebo „23.10.2026 - 03.12.2026 - …“).
Město u položky není, proto se berou jen akce na místech, která známe jako pražská (seznam PRAZSKA),
nebo s Prahou v názvu místa či akce.
"""
import datetime as dt
import re

from bs4 import BeautifulSoup

from .spolecne import akce, bez_diakritiky, cisty

ZAKLAD = "https://www.archiweb.cz"
PRAZSKA = ["praha", "prague", "prag ", "cvut", "fa cvut", "fsv", "umprum", "vsup", "camp", "kruh", "vi per",
           "fragner", "nova sin", "trafo", "hidden", "meetfactory", "koniklec", "dox", "veletrzni",
           "narodni technicke", "ntm", "rudolfinum", "galerie kvalitar", "kampus hybernska", "jatka78",
           "manes", "kamenneho zvonu", "ceska komora architektu", "cka", "galerie ceskych center", "ceske centrum",
           "upm", "umeleckoprumyslove", "artwall", "galerie 1", "ipr", "nadrazi bubny", "bubny", "desfourssky",
           "goethe-institut", "francouzsky institut", "polsky institut", "rakousko kulturni forum",
           "skautsky institut", "venuse ve svehlovce", "cross club", "pragovka", "karlin studios", "holesovic",
           "vinohrad", "smichov", "karlin", "zizkov", "letna", "dejvic"]
NE = ["brno", "ostrava", "olomouc", "zlin", "liberec", "plzen", "budejovic", "hradec", "pardubic", "jihlav",
      "berlin", "wien", "vienna", "bratislava", "aedes", "dam ", "milano", "london", "paris"]
DATUM = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")


def je_praha(*texty):
    t = " " + bez_diakritiky(" ".join(x or "" for x in texty)).lower() + " "
    if any(n in t for n in NE):
        return False
    return any(re.search(rf"(?<![a-z]){re.escape(p.strip())}(?![a-z])", t) for p in PRAZSKA)


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for art in s.select("div.eventsList article"):
            odkaz = art.find("a", href=True)
            nazev_el = art.select_one(".advertisement__title")
            datum_el = art.select_one(".advertisement__date")
            if not (odkaz and nazev_el and datum_el):
                continue
            misto = cisty((art.select_one(".advertisement__place") or {}).get_text(" ") if art.select_one(".advertisement__place") else "")
            podtitul = cisty(art.select_one(".advertisement__name").get_text(" ")) if art.select_one(".advertisement__name") else ""
            nazev = cisty(nazev_el.get_text(" "))
            if not je_praha(misto, nazev):
                continue
            data = [dt.date(int(r), int(m), int(d)) for d, m, r in DATUM.findall(datum_el.get_text(" "))]
            if not data:
                continue
            od, do = data[0], (data[1] if len(data) > 1 else None)
            href = ZAKLAD + odkaz["href"] if odkaz["href"].startswith("/") else odkaz["href"]
            if href in videno:
                continue
            videno.add(href)
            male = bez_diakritiky(nazev).lower()
            typ = ("vystava" if "vystav" in male else "prednaska" if re.search(r"prednask|diskuz|debat|konferen|talk", male)
                   else None)
            vysledek.append(akce(nazev=nazev, datum=od, konec_datum=do if do and do != od else None,
                                 misto=misto or None, url=href, typ=typ, znacky=podtitul or None))
    return vysledek
