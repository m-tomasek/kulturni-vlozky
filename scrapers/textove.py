"""Workshopy a kurzy popsané volným textem na stránce kurzu („KDY: neděle 8. 11. 2026 9:30–16:30“,
„Termíny workshopů: 15. 10., 29. 10., 12. 11. 2026“, „ZIMNÍ KURZY od 6.10.2026 do 18.12.2026“).

Nastavení v zdroje.yml (scraper: textove):
  urls:          stránky se seznamem kurzů (nebo rovnou stránky kurzů, když chybí `odkazy`)
  odkazy_text    regulární výraz textu odkazu (např. „ND\\+ Kurz“)
  odkazy: "re"   regulární výraz adres kurzů, které se ze seznamu otevřou (max. `max_odkazu`, výchozí 40)
  nazev_css: h1  odkud vzít název (výchozí h1, jinak <title>)
  oblast_css     kde hledat termíny (výchozí celá stránka bez hlavičky a patičky)
  bloky: "re"    místo celé stránky jednotlivé úseky textu začínající tímto výrazem, každý = jeden kurz
                 (název = text úseku před datem), např. ATVU „ZIMNÍ KURZY od … do …“
  nazev_akce     pevný název (jinak z nazev_css); delka_bloku: kolik znaků textu patří k bloku (300)
  misto, typ_akce, vynechat
Ze stránky se vezmou všechna budoucí data (do 200 dní). Data těsně za slovy „přihlášk“, „uzávěrk“,
„platba“, „do“ (termín přihlášení) se nepočítají. Do tří termínů = samostatné akce (jednodenní workshop
opakovaný), víc termínů = kurz: jedna akce v den prvního setkání s počtem setkání v názvu.
Rozsah „od 6.10.2026 do 18.12.2026“ = kurz (jedna akce v den začátku).
"""
import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .obecny import najdi_cas
from .spolecne import MESICE, akce, bez_diakritiky, cisty, odvod_rok

DATUM = re.compile(r"(?<![\d.])(\d{1,2})\.\s*(?:(\d{1,2})\.|([a-zA-Záčďéěíňóřšťúůýž]{3,9}))\s*(20\d\d)?")
AZ = re.compile(r"(?<![\d.])(\d{1,2})\.\s*(?:až|–|-)\s*(?:[a-zA-Záčďéěíňóřšťúůýž]+\s+)?(\d{1,2})\.\s*"
                r"([a-zA-Záčďéěíňóřšťúůýž]{4,9})\s*(20\d\d)?")
ROZSAH = re.compile(r"\bod\s+(\d{1,2}\.\s*\d{1,2}\.\s*(?:20\d\d)?)\s*(?:do|–|-)\s*(\d{1,2}\.\s*\d{1,2}\.\s*(?:20\d\d)?)", re.I)
NE_TERMIN = re.compile(r"(přihl\w*|uzávěrk\w*|plat\w*|uhra\w*|registr\w*|zveřejn\w*|aktualiz\w*|\bdo|\bpo|\bod\s+\d+\s*let|vydáno|"
                       r"publikov\w*|dárkov\w*|platnost\w*|prodeji\s+od)\s*:?\s*$", re.I)


def _data(text, dnes):
    """[(datum, pozice_konce)] všech dat v textu; rok chybějící u data se doplní z nejbližšího dalšího."""
    text = AZ.sub(lambda m: f"{m.group(1)}. {m.group(3)} {m.group(4) or ''}", text)  # vícedenní workshop = den začátku
    out = []
    for m in DATUM.finditer(text):
        d, mc, ms, r = m.groups()
        mes = int(mc) if mc else MESICE.get(bez_diakritiky(ms).lower())
        if not mes or not 1 <= mes <= 12 or (ms and bez_diakritiky(ms).lower() == "pro"):
            continue
        if NE_TERMIN.search(text[max(0, m.start() - 25):m.start()]):
            continue
        out.append([int(d), mes, int(r) if r else None, m.start(), m.end()])
    # „15. 10., 29. 10., 12. 11. 2026“ – rok jen u posledního platí i pro předchozí
    rok, dalsi_zac = None, None
    for x in reversed(out):
        if x[2]:
            rok = x[2]
        elif rok and dalsi_zac is not None and dalsi_zac - x[4] < 40:
            x[2] = rok
        else:
            rok = None
        dalsi_zac = x[3]
    vysl = []
    for d, mes, r, zac, kon in out:
        try:
            datum = dt.date(r, mes, d) if r else odvod_rok(d, mes, dnes)
        except ValueError:
            continue
        vysl.append((datum, zac, kon))
    return vysl


def _akce_z_textu(text, nazev, url, zdroj, dnes):
    konec = dnes + dt.timedelta(days=200)
    vysledek = []
    rozsahy = [(m, _data(m.group(1), dnes), _data(m.group(2), dnes)) for m in ROZSAH.finditer(text)]
    rozsahy = [(m, a[0][0], b[0][0]) for m, a, b in rozsahy if a and b and a[0][0] < b[0][0]]
    if rozsahy:
        for m, od, do in rozsahy:
            if dnes <= od <= konec:  # už běžící kurz se nenabízí (každý den by se „posouval“)
                cas_ = najdi_cas(text[m.end():m.end() + 40])
                vysledek.append((od, cas_, f"{nazev} (kurz od {od.day}. {od.month}. do {do.day}. {do.month}.)"))
        return vysledek
    data = sorted({d for d, _, _ in _data(text, dnes) if dnes <= d <= konec})
    if not data:
        return []
    # víkendový workshop (pá–ne) = jedna akce v den začátku
    data = [d for i, d in enumerate(data) if i == 0 or (d - data[i - 1]).days > 2 or
            not all((data[j] - data[j - 1]).days <= 2 for j in range(1, i + 1))]
    pozice = {}
    for d, zac, kon in _data(text, dnes):
        pozice.setdefault(d, kon)
    obecny_cas = najdi_cas(text[pozice[data[0]]:pozice[data[0]] + 400])
    if len(data) <= 3:
        for d in data:
            vysledek.append((d, najdi_cas(text[pozice[d]:pozice[d] + 40]) or obecny_cas, nazev))
    else:
        d = data[0]
        vysledek.append((d, najdi_cas(text[pozice[d]:pozice[d] + 40]) or obecny_cas,
                         f"{nazev} (kurz od {d.day}. {d.month}. do {data[-1].day}. {data[-1].month}.)"))
    return vysledek


def _text(s, zdroj):
    for t in s(["script", "style", "noscript", "header", "footer", "nav", "form"]):
        t.decompose()
    oblast = s.select_one(zdroj["oblast_css"]) if zdroj.get("oblast_css") else None
    return cisty((oblast or s.body or s).get_text(" "))


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    vynechat = re.compile(zdroj["vynechat"], re.I) if zdroj.get("vynechat") else None
    stranky = []
    for url in zdroj["urls"]:
        if zdroj.get("odkazy"):
            s = BeautifulSoup(stahni(url), "lxml")
            rx = re.compile(zdroj["odkazy"])
            rt = re.compile(zdroj["odkazy_text"], re.I) if zdroj.get("odkazy_text") else None
            for a in s.find_all("a", href=True):
                u = urljoin(url, a["href"]).split("#")[0]
                if rt and not rt.search(cisty(a.get_text(" "))):
                    continue
                if rx.search(u) and u not in stranky:
                    stranky.append(u)
        else:
            stranky.append(url)
    for u in stranky[: int(zdroj.get("max_odkazu", 40))]:
        try:
            s = BeautifulSoup(stahni(u), "lxml")
        except Exception:  # noqa: BLE001 – jeden nedostupný kurz nesmí shodit celý zdroj
            continue
        n = s.select_one(zdroj.get("nazev_css", "h1")) or s.title
        nazev = zdroj.get("nazev_akce") or (cisty(n.get_text(" ")).split(" | ")[0].split(" - ")[0] if n else "")
        if zdroj.get("nazev_odstranit"):
            nazev = re.sub(zdroj["nazev_odstranit"], "", nazev).strip(" –-|")
        text = _text(s, zdroj)
        if zdroj.get("bloky"):
            casti = [m for m in re.finditer(zdroj["bloky"], text)]
            delka = int(zdroj.get("delka_bloku", 300))
            useky = [(text[m.start():min(m.start() + delka, casti[i + 1].start() if i + 1 < len(casti) else len(text))],
                      m.group(0)) for i, m in enumerate(casti)]
            useky = [(t, cisty(f"{nazev} – {h.lower()}")) for t, h in useky]
        else:
            useky = [(text, nazev)]
        for t, nz in useky:
            if not nz or (vynechat and vynechat.search(nz)):
                continue
            for datum, cas_, jmeno in _akce_z_textu(t, nz, u, zdroj, dnes):
                if (jmeno, datum) in videno:
                    continue
                videno.add((jmeno, datum))
                vysledek.append(akce(nazev=jmeno, datum=datum, cas=cas_, misto=zdroj.get("misto"), url=u,
                                     typ=zdroj.get("typ_akce", "workshop")))
    return vysledek
