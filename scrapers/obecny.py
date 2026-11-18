"""Obecný scraper pro jednoduché weby – nastavuje se jen v zdroje.yml, bez vlastního kódu.

Použití v zdroje.yml (u zdroje uvést `scraper: obecny`):

  format: html          # html (výchozí) | jsonld (schema.org Event v <script type="application/ld+json">)
  blok: "article.event" # CSS výběr jedné akce
  nazev_css: "h3 a"     # CSS uvnitř bloku pro název akce (výchozí: první nadpis, jinak první odkaz)
  datum: ".date"        # CSS uvnitř bloku s datem (výchozí: celý text bloku)
  odkaz: "a"            # CSS odkazu (výchozí: první odkaz v bloku)
  misto: "Toulcův dvůr" # pevné místo, nebo
  misto_css: ".place"   # místo z bloku
  jen_praha: true       # brát jen akce v Praze (u celostátních webů); s misto_css se hledá jen v místě
  vynechat_css: "s"     # bloky obsahující tento prvek se přeskočí (např. přeškrtnuté = zrušené)
  nazev_bez_data: true  # z názvu se odstraní úvodní datum a čas („St 18. 11. 2026, 16.30 h Název“)
  jen_tema: true        # (v run.py) brát jen akce, které vyjdou jako příroda/architektura
  vynechat: "pro děti|tábor"   # regulární výraz – bloky s tímto textem se přeskočí
  typ: prednaska        # pevný typ akce (jinak se určí podle názvu)

Datum se hledá v atributech (datetime=, content=) a v textu: „24. 11. 2026“, „24.11.“,
„24. listopadu 2026“, rozsahy „24.–26. 11.“ i „24. 11. – 3. 12. 2026“. Čas „18:00“ / „18.00 h“.
"""
import datetime as dt
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .spolecne import MESICE, akce, bez_diakritiky, cas, cisty, odvod_rok

_D = r"(\d{1,2})\.\s*"
CISELNE = re.compile(_D + r"(\d{1,2})\.\s*(20\d\d)?")
SLOVNE = re.compile(_D + r"([a-zA-Záčďéěíňóřšťúůýž]{3,9})\.?\s*(20\d\d)?")
ROZSAH_DEN = re.compile(r"(?<!\d)(?<!\d\.)(?<!\d\.\s)(\d{1,2})\.\s*[–-]\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d\d)?")
ISO = re.compile(r"(20\d\d)-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?")


PRAHA = re.compile(r"\b(praha|prahy|praze|prazsk|prague)")
UVODNI_DATUM = re.compile(r"^\s*(?:(?:po|ut|út|st|čt|ct|pá|pa|so|ne)\.?\s+)?[\d.\s–-]+(?:20\d\d)?\s*,?\s*"
                          r"(?:\d{1,2}(?:[.:]\d{2})?\s*(?:[–-]\s*\d{1,2}(?:[.:]\d{2})?)?\s*(?:h\b\.?|(?<=\d\d)))?\s*", re.I)


def je_v_praze(text):
    return bool(PRAHA.search(bez_diakritiky(text or "").lower()))


def _datum(d, m, r, dnes):
    try:
        return dt.date(int(r), m, int(d)) if r else odvod_rok(int(d), m, dnes)
    except ValueError:
        return None


def najdi_data(text, dnes):
    """Vrátí (od, do) z textu, nebo (None, None)."""
    t = cisty(text)
    m = ROZSAH_DEN.search(t)
    if m:
        d1, d2, mes, r = m.groups()
        od, do = _datum(d1, int(mes), r, dnes), _datum(d2, int(mes), r, dnes)
        if od and do:
            return od, do
    nalezene = []
    for m in CISELNE.finditer(t):
        d, mes, r = m.groups()
        if 1 <= int(mes) <= 12:
            nalezene.append((m.start(), d, int(mes), r))
    for m in SLOVNE.finditer(t):
        slovo = bez_diakritiky(m.group(2)).lower()
        mes = MESICE.get(slovo) if slovo != "pro" else None  # „1. pro děti“ není prosinec
        if mes:
            nalezene.append((m.start(), m.group(1), mes, m.group(3)))
    nalezene.sort()
    if not nalezene:
        m = ISO.search(t)
        if m:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))), None
        return None, None
    # rok uvedený jen u druhého data rozsahu („24. 11. – 3. 12. 2026“) platí i pro první
    rok_dal = next((r for _, _, _, r in nalezene if r), None)
    _, d, mes, r = nalezene[0]
    od = _datum(d, mes, r or rok_dal, dnes)
    do = None
    if len(nalezene) > 1:
        _, d2, mes2, r2 = nalezene[1]
        kand = _datum(d2, mes2, r2 or rok_dal, dnes)
        if od and kand and 0 < (kand - od).days <= 200:
            do = kand
    return od, do


def najdi_cas(text):
    """Čas začátku – data se z textu nejdřív odstraní, aby se „22.11.“ nebralo jako 22:11."""
    t = ROZSAH_DEN.sub(" ", text or "")
    t = re.sub(r"\b\d{1,2}\.\s*\d{1,2}\.\s*(?:20\d\d)?", " ", t)
    c = cas(t)
    if not c:  # „18 h“, „13–18 h“
        m = re.search(r"\b(\d{1,2})\s*(?:[–-]\s*\d{1,2}\s*)?h\b", t)
        c = f"{int(m.group(1)):02d}:00" if m and int(m.group(1)) < 24 else None
    return c


def _z_atributu(blok):
    for el in blok.select("[datetime], [content]"):
        m = ISO.search(el.get("datetime") or el.get("content") or "")
        if m:
            d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return d, (f"{m.group(4)}:{m.group(5)}" if m.group(4) and m.group(4) + m.group(5) != "0000" else None)
    return None, None


def _jsonld(html, zdroj, url, dnes):
    s = BeautifulSoup(html, "lxml")
    out = []
    for sc in s.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(sc.string or "")
        except Exception:  # noqa: BLE001
            continue
        polozky = d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []
        for x in polozky:
            if not isinstance(x, dict) or "Event" not in str(x.get("@type")):
                continue
            m = ISO.search(str(x.get("startDate") or ""))
            if not m:
                continue
            k = ISO.search(str(x.get("endDate") or ""))
            loc = x.get("location") or {}
            loc = loc[0] if isinstance(loc, list) and loc else loc
            misto = loc.get("name") if isinstance(loc, dict) else str(loc)
            adresa = loc.get("address") if isinstance(loc, dict) else ""
            adresa = " ".join(str(v) for v in adresa.values()) if isinstance(adresa, dict) else str(adresa or "")
            if zdroj.get("jen_praha") and not je_v_praze(f"{misto} {adresa}"):
                continue
            od = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            do = dt.date(int(k.group(1)), int(k.group(2)), int(k.group(3))) if k else None
            out.append(dict(nazev=x.get("name") or "", datum=od, konec_datum=do if do and do != od else None,
                            cas=f"{m.group(4)}:{m.group(5)}" if m.group(4) and m.group(4) + m.group(5) != "0000" else None,
                            misto=zdroj.get("misto") or misto, url=x.get("url") or url,
                            popis=x.get("description") if isinstance(x.get("description"), str) else None))
    return out


def ziskej(stahni, zdroj, dnes):
    vysledek, videno = [], set()
    vynechat = re.compile(zdroj["vynechat"], re.I) if zdroj.get("vynechat") else None
    for url in zdroj["urls"]:
        html = stahni(url)
        if zdroj.get("format") == "jsonld":
            surove = _jsonld(html, zdroj, url, dnes)
        else:
            surove = []
            s = BeautifulSoup(html, "lxml")
            for blok in s.select(zdroj["blok"]):
                text = cisty(blok.get_text(" "))
                if vynechat and vynechat.search(text):
                    continue
                if zdroj.get("vynechat_css") and blok.select_one(zdroj["vynechat_css"]):
                    continue
                n_el = blok.select_one(zdroj["nazev_css"]) if zdroj.get("nazev_css") else \
                    blok.find(["h1", "h2", "h3", "h4", "h5"]) or blok.find("a")
                if n_el is None and blok.name == "a":
                    n_el = blok
                if n_el is None:
                    continue
                d_el = blok.select_one(zdroj["datum"]) if zdroj.get("datum") else None
                d_text = re.sub(r"\b(\d{1,2}),(\d{2})\b", r"\1:\2", cisty(d_el.get_text(" ")) if d_el else text)
                od, do = najdi_data(d_text, dnes)
                c = None
                if not od:
                    od, c = _z_atributu(blok)
                if not od:
                    continue
                o_el = blok.select_one(zdroj["odkaz"]) if zdroj.get("odkaz") else \
                    (blok if blok.name == "a" and blok.get("href") else blok.find("a", href=True))
                misto = zdroj.get("misto")
                if zdroj.get("misto_css"):
                    m_el = blok.select_one(zdroj["misto_css"])
                    misto = re.sub(r"^\s*místo:\s*", "", cisty(m_el.get_text(" ")), flags=re.I) if m_el else misto
                if zdroj.get("jen_praha") and not je_v_praze(misto if zdroj.get("misto_css") else text):
                    continue
                nazev = cisty(n_el.get_text(" "))
                if zdroj.get("nazev_bez_data"):
                    nazev = UVODNI_DATUM.sub("", nazev)
                surove.append(dict(nazev=nazev, datum=od, konec_datum=do, misto=misto,
                                   cas=c or najdi_cas(d_text) or (najdi_cas(text) if not zdroj.get("datum") else None),
                                   url=urljoin(url, o_el["href"]) if o_el and o_el.get("href") else url))
        for a in surove:
            nazev = cisty(a["nazev"])
            if not nazev or (nazev, a["datum"]) in videno:
                continue
            if vynechat and vynechat.search(nazev):
                continue
            videno.add((nazev, a["datum"]))
            vysledek.append(akce(nazev=nazev, datum=a["datum"], konec_datum=a.get("konec_datum"),
                                 cas=a.get("cas"), misto=a.get("misto") or zdroj.get("nazev_mista"),
                                 url=a.get("url"), popis=a.get("popis"), typ=zdroj.get("typ")))
    return vysledek
