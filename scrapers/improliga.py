import re

from bs4 import BeautifulSoup

from .spolecne import akce, bez_diakritiky, cas, cisty, odvod_rok

# Místa, o kterých víme, že jsou / nejsou v Praze. Neznámá místa se ověří
# na stránce akce (hledá se „Praha“ v adrese) a výsledek se uloží do cache.
PRAHA_KLICE = ["praha", "prague", "kamen", "letka", "music lab", "karlinske spektrum",
               "open gate", "citadela", "d21", "staromak", "bez hranic", "kampus hybernska"]


def _je_v_praze(misto, url, stahni, cache):
    k = bez_diakritiky(misto).lower()
    if k in cache:
        return cache[k]
    if any(p in k for p in PRAHA_KLICE):
        cache[k] = True
        return True
    v = None
    try:
        text = bez_diakritiky(BeautifulSoup(stahni(url), "lxml").get_text(" ")).lower()
        v = bool(re.search(r"\bpraha\b|\bprague\b|\bpraze\b", text))
    except Exception:  # noqa: BLE001
        v = None
    if v is not None:
        cache[k] = v
    return v


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    cache = zdroj.setdefault("_mista", {})
    for url in zdroj["urls"]:
        s = BeautifulSoup(stahni(url), "lxml")
        for den in s.select("div.wpimprov_day"):
            h = den.find("h3")
            m = re.search(r"(\d{1,2})\.(\d{1,2})\.", h.get_text() if h else "")
            if not m:
                continue
            datum = odvod_rok(int(m.group(1)), int(m.group(2)), dnes)
            for ev in den.select("div.wpimprov_event"):
                a = ev.select_one("h3 a")
                if not a:
                    continue
                nazev = cisty(a.get_text())
                t = ev.select_one(".wpimprov_time")
                misto = cisty(ev.select_one(".wpimprov_venue").get_text()) if ev.select_one(".wpimprov_venue") else ""
                klic = (nazev.lower(), datum, misto.lower())
                if klic in videno:  # Improliga uvádí akce často dvakrát
                    continue
                videno.add(klic)
                praha = _je_v_praze(misto, a["href"], stahni, cache) if misto else None
                vysledek.append(akce(
                    nazev=nazev, datum=datum, cas=cas(t.get_text()) if t else None,
                    misto=misto or None, url=a["href"], stav="neznamo", typ="improvizace",
                    mimo_prahu=praha is not True,
                ))
    return vysledek
