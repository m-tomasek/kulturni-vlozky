import datetime as dt
import re

from bs4 import BeautifulSoup

from .spolecne import akce, cas, cisty


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for b in s.find_all("b"):
            m = re.fullmatch(r"\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d\d)\s*", b.get_text())
            if not m:
                continue
            radek = b.find_parent("div")
            blok = radek.find_parent("div")
            h4 = blok.find("h4")
            if not h4:
                continue
            datum = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            info = h4.find_next_sibling("span")
            info_t = cisty(info.get_text()) if info else ""
            casti = [x.strip() for x in info_t.split("|")]
            zanr = casti[0] if casti else None
            cena = next((x for x in casti if "Kč" in x), None)
            tl = blok.select_one("a.btn")
            tl_t = cisty(tl.get_text()).lower() if tl else ""
            href = tl.get("href") if tl else None
            if "vyprodáno" in tl_t:
                stav = "vyprodano"
            elif "zrušeno" in tl_t:
                stav = "zruseno"
            elif href and href.startswith("http"):
                stav = "volno"
            else:
                stav = "neznamo"
            row = blok.find_parent("div", class_="row")
            popis_el = row.find_next_sibling("div", class_="collapse") if row else None
            vysledek.append(akce(
                nazev=h4.get_text(), datum=datum, cas=cas(radek.get_text()),
                misto="Malostranská beseda", url=url.split("?")[0],
                vstupenky=href if href and href.startswith("http") else None,
                stav=stav, cena=cena, typ="koncert", znacky=zanr,
                popis=popis_el.get_text(" ") if popis_el else None,
            ))
    return vysledek
