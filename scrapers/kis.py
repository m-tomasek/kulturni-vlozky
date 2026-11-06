import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .spolecne import MESICE, akce, bez_diakritiky, cas, cisty, odvod_rok


def ziskej(stahni, zdroj, dnes):
    vysledek = []
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for k in s.select("a.show-card"):
            meta = k.select_one(".meta-row")
            m = re.search(r"(\d{1,2})\.\s*([a-zA-Zá-žÁ-Ž]+)", meta.get_text() if meta else "")
            if not m:
                continue
            mesic = MESICE.get(bez_diakritiky(m.group(2)).lower()[:3]) or MESICE.get(bez_diakritiky(m.group(2)).lower())
            if not mesic:
                continue
            nazev = k.select_one(".title")
            misto = k.select_one(".ink-soft")
            misto_t = cisty(misto.get_text()).replace("📍", "").strip() if misto else ""
            vysledek.append(akce(
                nazev=nazev.get_text() if nazev else "KIŠ",
                datum=odvod_rok(int(m.group(1)), mesic, dnes),
                cas=cas(meta.get_text()),
                misto=f"KIŠ – {misto_t}" if misto_t and misto_t != "Praha" else "KIŠ (Praha)",
                url=urljoin(url, k["href"]), stav="neznamo", typ="improvizace",
            ))
    return vysledek
