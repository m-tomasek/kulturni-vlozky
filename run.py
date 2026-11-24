"""Denní běh Kulturních vložek.

1. stáhne programy ze všech aktivních zdrojů (scrapers/),
2. vyfiltruje a sjednotí akce (pravidla.yml),
3. porovná s minulým během (nové, změny, přesuny, zmizelé akce),
4. zapíše data/akce.json, data/zdravi.json a data/problemy.md.
"""
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo

import requests
import yaml
from bs4 import BeautifulSoup

from nastroje.snapshot import rozbal
from scrapers import nacti
from scrapers.spolecne import bez_diakritiky, norm

KOREN = pathlib.Path(__file__).resolve().parent
DATA = KOREN / "data"
UA = "Mozilla/5.0 (X11; Linux x86_64) KulturniVlozky/1.0 (+https://gitlab.com/michal.tomasek/kulturni-vlozky)"
PRAHA = ZoneInfo("Europe/Prague")
ZMIZELA_ZRUSENO_PO = 3      # po kolika bězích bez akce ve zdroji ji odstranit
ZMIZELA_OZNACIT_PO = 2      # od kolika běhů ukazovat „zrušeno?“
HLASIT_PO = 2               # výpadek webu se hlásí až při tolikátém neúspěšném běhu po sobě
VAROVANI_MAX_BEHU = 4       # kolik běhů po sobě hlásit podezřele nízký počet, než se přijme jako nový normál
PAD_ZDROJE = 0.4            # zdroj vrátil méně než 40 % akcí oproti minule → problém

STOP = {"a", "v", "ve", "na", "do", "s", "se", "z", "the", "of", "and", "i", "u", "k", "o"}


# ---------------------------------------------------------------- pomůcky

def nacti_json(cesta, vychozi):
    try:
        return json.loads(cesta.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return vychozi


def uloz_json(cesta, data):
    cesta.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def uloz_akce(cesta, meta, akce):
    """Jedna akce = jeden řádek: soubor je menší a denní rozdíl v repu obsahuje jen změněné akce."""
    radky = ",\n".join(json.dumps(a, ensure_ascii=False, separators=(",", ":")) for a in akce)
    cesta.write_text('{"meta":' + json.dumps(meta, ensure_ascii=False) + ',\n"akce":[\n' + radky + "\n]}\n",
                     encoding="utf-8")


# Některé weby (ochrana proti botům, CDN) odmítají neznámého „robota“ chybou 403/429/503, i když stránka
# normálně funguje. U takového webu se zkusí znovu hlavičky běžného prohlížeče a pro zbytek běhu se drží.
PROHLIZEC = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.6",
}
ODMITNUTI = (403, 406, 429, 503)


def vytvor_stahovac():
    # Zdroje se stahují souběžně (viz SOUBEZNE): každé vlákno má vlastní spojení (Session není
    # mezi vlákny bezpečná), mezipaměť stránek je společná.
    mistni = threading.local()

    def sezeni_vlakna():
        if not hasattr(mistni, "s"):
            mistni.s = requests.Session()
            mistni.s.headers["User-Agent"] = UA
        return mistni.s

    cache = {}
    jako_prohlizec = set()  # weby, které chtějí hlavičky prohlížeče

    def stahni(url):
        if url in cache:
            return cache[url]
        posledni = None
        for pokus in range(3):
            host = urlsplit(url[5:].strip() if url.startswith("POST ") else url).netloc
            hlavicky = PROHLIZEC if host in jako_prohlizec else {}
            try:
                if url.startswith("POST "):  # "POST adresa?parametry" – web načítá program formulářem
                    u = urlsplit(url[5:].strip())
                    r = sezeni_vlakna().post(f"{u.scheme}://{u.netloc}{u.path}", data=parse_qsl(u.query, keep_blank_values=True),
                                    headers={**hlavicky, "X-Requested-With": "XMLHttpRequest"}, timeout=30)
                else:
                    r = sezeni_vlakna().get(url, headers=hlavicky, timeout=30)
                r.raise_for_status()
                r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else r.apparent_encoding
                cache[url] = r.text
                return r.text
            except requests.RequestException as e:
                posledni = e
                kod = getattr(getattr(e, "response", None), "status_code", None)
                if kod in ODMITNUTI and host not in jako_prohlizec:
                    jako_prohlizec.add(host)
                    print(f"{host}: chyba {kod}, zkouším hlavičky prohlížeče", file=sys.stderr)
                    continue
                if kod is not None and 400 <= kod < 500 and kod not in (408, 429):
                    break  # chyba na naší straně (404, 403…) – opakování nepomůže
                if pokus < 2:
                    time.sleep(2 * (pokus + 1))
        raise posledni

    return stahni


def mekky_stahovac(stahni, adresy):
    """Stahovač pro jeden zdroj: když selže jedna z jeho hlavních adres, vrátí prázdnou stránku a chybu si
    zapamatuje – ostatní adresy (jiné měsíce) se tak neztratí. Jiné adresy (detaily akcí) selžou normálně."""
    hlavni = set(adresy)

    def f(url):
        try:
            text = stahni(url)
        except requests.RequestException as e:
            if url not in hlavni or len(hlavni) < 2:
                raise
            f.chyby.append((url, e))
            return ""
        f.uspechy += 1
        if url in hlavni:
            f.texty[url] = text
        return text

    f.chyby, f.uspechy, f.texty = [], 0, {}
    return f


_DATUM_CS = re.compile(r"(?<![\d.])(\d{1,2})\.\s?(\d{1,2})\.(?:\s?(20\d\d))?(?![\d])")
_DATUM_ISO = re.compile(r"(?<!\d)(20\d\d)-(\d\d)-(\d\d)(?!\d)")
_DATUM_SLOVY = re.compile(r"(?<!\d)(\d{1,2})\.\s?(ledna|února|března|dubna|května|června|července|srpna|září|října|listopadu|prosince)"
                          r"(?:\s+(20\d\d))?", re.I)
_MESICE_G = ["ledna", "února", "března", "dubna", "května", "června", "července", "srpna", "září", "října",
             "listopadu", "prosince"]


def data_v_textu(text, dnes, do):
    """Budoucí data (do horizontu), která stránka zmiňuje – z textu i z atributů (JSON-LD, datetime=…)."""
    vysledek = set()

    def pridej(r, m, d):
        try:
            if r is None:
                x = dt.date(dnes.year, m, d)
                if x < dnes - dt.timedelta(days=1):
                    x = dt.date(dnes.year + 1, m, d)
            else:
                x = dt.date(r, m, d)
        except ValueError:
            return
        if dnes <= x <= do:
            vysledek.add(x.isoformat())

    for m in _DATUM_ISO.finditer(text):
        pridej(int(m[1]), int(m[2]), int(m[3]))
    for m in _DATUM_CS.finditer(text):
        pridej(int(m[3]) if m[3] else None, int(m[2]), int(m[1]))
    for m in _DATUM_SLOVY.finditer(text):
        pridej(int(m[3]) if m[3] else None, _MESICE_G.index(m[2].lower()) + 1, int(m[1]))
    return vysledek


def kontrola_uplnosti(texty, akce, dnes, do):
    """Porovná data zmíněná na stránkách programu s daty akcí, které z nich čtečka vytáhla.
    Vrací (počet zmíněných dnů, chybějící dny). Chybějící dny = čtečka možná něco přehlíží."""
    zminene = set()
    for t in texty:
        if t.lstrip()[:1] == "<":
            # jen viditelný text a obsah skriptů (JSON-LD); atributy jako <time datetime> v kalendářních
            # lištách by hlásily dny, na kterých nic není
            s = BeautifulSoup(t, "lxml")
            t = s.get_text(" ") + " ".join(x.string or "" for x in s.find_all("script"))
        zminene |= data_v_textu(t, dnes, do)
    mame = set()
    for a in akce:
        d0 = dt.date.fromisoformat(a["datum"])
        d1 = dt.date.fromisoformat(a.get("konec_datum") or a["datum"])
        for k in range(min((d1 - d0).days, 400) + 1):
            mame.add((d0 + dt.timedelta(days=k)).isoformat())
    return len(zminene), sorted(zminene - mame)


def slova(nazev):
    return {w for w in norm(nazev).split() if w not in STOP and len(w) > 1}


def podobne(a, b):
    sa, sb = slova(a), slova(b)
    if not sa or not sb:
        return False
    prunik = sa & sb
    if not prunik:
        return False
    if sa <= sb or sb <= sa:
        return any(len(w) >= 4 for w in prunik)
    return len(prunik) / len(sa | sb) >= 0.5


OBECNA_MISTA = {"galerie", "gallery", "divadlo", "theatre", "klub", "club", "kino", "bio", "studio", "jazz", "cafe",
                "kavarna", "bar", "centrum", "praha", "prague", "scena", "sal", "velky", "maly", "dum", "music", "hall"}


def stejne_misto(a, b):
    """Jsou dvě akce (podle názvu místa) na stejné scéně? Bez údaje o místě to nevíme → ano."""
    na, nb = norm(a.get("misto") or ""), norm(b.get("misto") or "")
    if not na or not nb or na == nb:
        return True
    return bool({w for w in na.split() if len(w) >= 3} & {w for w in nb.split() if len(w) >= 3} - OBECNA_MISTA)


def misto_cast(a, b):
    """Přísnější shoda místa (pro párování jen podle času): výrazná slova jednoho místa jsou celá obsažena
    v druhém („Reduta Jazz Club“ × „Reduta“, „Divadlo X – Velký sál“ × „Divadlo X“), ale „Galerie Rudolfinum“
    není „Rudolfinum – Dvořákova síň“ a „Kasárna Karlín“ není „Velká scéna HD Karlín“."""
    obecna = OBECNA_MISTA - {"galerie", "gallery"}
    wa, wb = ({w for w in norm(x.get("misto") or "").split() if len(w) >= 3} - obecna for x in (a, b))
    return bool(wa) and bool(wb) and (wa <= wb or wb <= wa)


def vzdalenost(p, q):
    """Přibližná vzdálenost dvou bodů [šířka, délka] v metrech (na pár set metrů stačí rovinný výpočet)."""
    import math
    dy = (p[0] - q[0]) * 111_320
    dx = (p[1] - q[1]) * 111_320 * math.cos(math.radians((p[0] + q[0]) / 2))
    return math.hypot(dx, dy)


def urcite_stejne_misto(a, b):
    """Jako stejne_misto, ale jen když místo známe u obou a opravdu se shoduje."""
    return bool(norm(a.get("misto") or "")) and bool(norm(b.get("misto") or "")) and stejne_misto(a, b)


def pokryti_agregatorem(vysledek, akce_podle_zdroje, typy_zdroju, okno_do):
    """Kolik akcí každého vlastního zdroje má i agregátor (GoOut) – ať je vidět, které skripty jsou navíc.

    Vrací {zdroj: {"z": akcí zdroje v okně agregátoru, "shoda": z toho je má i agregátor,
                   "navic": akce agregátoru na stejném místě, které zdroj nemá (nebo se nespárovaly)}}.
    """
    agreg = [a for a in vysledek if a["zdroj"] == "goout" and a["datum"] <= okno_do]
    vystup = {}
    for zid, xs in akce_podle_zdroje.items():
        if typy_zdroju[zid] != "primarni":
            continue
        v_okne = [a for a in xs if a["datum"] <= okno_do]
        shoda = sum(1 for a in v_okne if "goout" in a.get("dalsi_zdroje", []))
        mista = [{"misto": m} for m in {a.get("misto") for a in v_okne} if m]
        navic = sum(1 for g in agreg if any(urcite_stejne_misto(g, m) for m in mista))
        vystup[zid] = {"z": len(v_okne), "shoda": shoda, "navic": navic}
    return vystup


def minuty(c):
    if not c:
        return None
    h, m = c.split(":")
    return int(h) * 60 + int(m)


OPAKOVANI_OD = 3  # stejný pořad na stejném místě tolikrát a víckrát za den → jedna položka


def sbal_opakovani(akce):
    """Prohlídky a vstupy každých 15–30 minut (Neviditelná výstava, Signal Space…) zahlcují přehled
    stovkami řádků. Stejný název + místo + den s 3 a více časy se sbalí do jedné akce s prvním časem
    a polem opakovani = počet časů, posledni_cas = poslední začátek."""
    skupiny = {}
    for a in akce:
        if a.get("cas") and not a.get("konec_datum"):
            skupiny.setdefault((norm(a["nazev"]), a.get("misto") or "", a["datum"]), []).append(a)
    pryc = set()
    for xs in skupiny.values():
        if len(xs) < OPAKOVANI_OD:
            continue
        xs.sort(key=lambda a: a["cas"])
        prvni = xs[0]
        prvni["opakovani"] = len(xs)
        prvni["posledni_cas"] = xs[-1]["cas"]
        prvni["konec_cas"] = None
        if any(x.get("stav") != "vyprodano" for x in xs) and prvni.get("stav") == "vyprodano":
            prvni["stav"] = "neznamo"  # vyprodaný je jen některý čas
        pryc.update(id(x) for x in xs[1:])
    return [a for a in akce if id(a) not in pryc]


def ident(a):
    zaklad = f"{a['zdroj']}|{norm(a['nazev'])}|{a['datum']}|{a['cas'] or ''}"
    return hashlib.sha1(zaklad.encode()).hexdigest()[:10]


# ---------------------------------------------------------------- filtry

def priprav_pravidla(p):
    return {
        "stavy": set(p.get("vynechat_stavy", [])),
        "nazev": [bez_diakritiky(x).lower() for x in p.get("vynechat_v_nazvu_a_stitcich", [])],
        "popis": [re.compile(x) for x in p.get("vynechat_v_popisu", [])],
        "typy": [(t, [bez_diakritiky(k).lower() for k in ks]) for t, ks in (p.get("typy") or {}).items()],
    }


def duvod_vynechani(a, pr):
    if a["stav"] in pr["stavy"]:
        return "uzavřené"
    if a["mimo_prahu"]:
        return "mimo Prahu"
    # „vhodné pro děti“ = i pro dospělé; vyřazujeme jen akce určené dětem
    nz = bez_diakritiky(f"{a['nazev']} {a.get('znacky') or ''}").lower().replace("vhodne pro deti", "")
    for k in pr["nazev"]:
        if k in nz:
            return f"pravidlo: {k}"
    popis = bez_diakritiky(a.get("popis") or "").lower().replace("vhodne pro deti", "")
    for rx in pr["popis"]:
        if rx.search(popis):
            return f"popis: {rx.pattern}"
    return None


def urci_typ(a, pr):
    if a.get("typ") == "workshop":  # zdroje workshopů a kurzů (typ_akce: workshop) – i „impro kurz“ je kurz
        return "workshop"
    text = bez_diakritiky(f"{a['nazev']} {a.get('znacky') or ''}").lower().replace("improvis", "")
    text = text.replace("exkurz", "").replace("z dilny", "")  # exkurze není kurz, „z dílny autora“ není dílna
    for typ, klice in pr["typy"]:
        shoda = [k for k in klice if k in text]
        if shoda:
            # „workshop“ v názvu přebije typ ze zdroje; „dílna“, „kurz“… jen u akcí bez typu
            silne = typ != "workshop" or any(k in ("workshop", "masterclass", "master class", "open class") for k in shoda)
            if a.get("typ") in (None, "koncert") or (typ in ("improvizace", "festival", "vystava", "workshop") and silne):
                return typ
    return a.get("typ") or "jine"


# Témata napříč typy akcí (přednáška o vilách je „přednáška“ i „architektura“). Zdroj může mít téma
# v zdroje.yml (tema: architektura); jinak se hledá podle slov v názvu a štítcích. U koncertů, divadla,
# filmů, tance a impra se podle slov nehádá (kapela „Les“ není akce o přírodě).
TEMATA = {
    "architektura": re.compile(
        r"architekt|urbanis|mestsk\w* planov|\bvil[ayu]\b|\bvile\b|\bvilou\b|\bvilach\b|\bvily\b|stavb|\bbudov|sidlist"
        r"|brutalis|funkcionalis|modernis|kubis|secesn|interier|open house|kolonie|\bloos|mullerov|winternitz"
        r"|rothmayer|plecnik|kotera|gocar|krejcar|\bcamp\b|verejn\w* prostor|pamatk|industrial|vodarn"
        r"|cistirn|podzemi|kasemat|rozhledn|nadrazi|bunkr|zahradni mesto|beton|palac|\bnamesti\b"),
    "priroda": re.compile(
        r"prirod|ekolog|biodiverzit|\bptac|\bptak|ornitolog|botanick|rostlin|\bstrom|\blesn|\bles\b"
        r"|\blesy\b|\blesa\b|houb|hmyz|brouk|motyl|netopyr|zachrann\w* stanic|rezervac|chranen\w* (uzemi|druh)"
        r"|\bkrajin|mokrad|\bvcel|ekocentr|zvirat|geolog|rybnik|mykolog"
        r"|entomolog|\bhub[ay]?\b|netopyr|obojzivel|plaz|savc"),
}
BEZ_HADANI = {"koncert", "divadlo", "film", "tanec", "improvizace"}
# Příroda = ochrana přírody jako obor (botanika, zoologie, mykologie, péče o krajinu…), ne aktivismus,
# klima, odpady a udržitelný životní styl. Akce s těmito slovy téma „příroda“ nedostanou ani od
# zdroje, který ho jinak dává všem svým akcím.
NE_PRIRODA = re.compile(
    r"klimat|aktivis|protest|demonstrac|stavk|extinction|fridays|greenpeace|recykl|upcykl|zero ?waste"
    r"|udrzitel|setrn\w* vanoc|uhlik|emis[ei]|energi|fosil|kompost|uklid|den zeme|vegan|jarmark|bezobal"
    r"|spotreb|obehov|odpad")


def urci_temata(a, zdroj_tema=None):
    temata = set(zdroj_tema if isinstance(zdroj_tema, list) else [zdroj_tema] if zdroj_tema else [])
    if a.get("typ") not in BEZ_HADANI:
        text = bez_diakritiky(f"{a['nazev']} {a.get('znacky') or ''} {a.get('popis') or ''}").lower()
        temata |= {t for t, rx in TEMATA.items() if rx.search(text)}
    if "camp" in bez_diakritiky(a.get("misto") or "").lower().split():
        temata.add("architektura")
    if "priroda" in temata and NE_PRIRODA.search(
            bez_diakritiky(f"{a['nazev']} {a.get('znacky') or ''}").lower()):
        temata.discard("priroda")
    return sorted(temata)


# ---------------------------------------------------------------- sloučení zdrojů

def slouc(akce_podle_zdroje, typy_zdroju):
    """Odstraní duplicity mezi zdroji; primární zdroj má přednost před agregátorem."""
    poradi = sorted(akce_podle_zdroje, key=lambda z: 0 if typy_zdroju[z] == "primarni" else 1)
    vysledek, rozpory, podle_dne = [], 0, {}
    for zid in poradi:
        for a in akce_podle_zdroje[zid]:
            shoda = None
            den = podle_dne.setdefault(a["datum"], [])
            for b in den:
                ma, mb = minuty(a["cas"]), minuty(b["cas"])
                if ma is not None and mb is not None and abs(ma - mb) > 60:
                    continue
                if not podobne(a["nazev"], b["nazev"]):
                    continue
                # stejný název ve stejný čas na jiné scéně je jiná akce (Vernisáž, Jam session…);
                # jiný název místa u úplně shodného delšího názvu bereme jako tutéž akci (KIŠ × Karlínské Spektrum)
                if stejne_misto(a, b) or (b["zdroj"] != a["zdroj"] and norm(a["nazev"]) == norm(b["nazev"])
                                          and len(slova(a["nazev"])) >= 3):
                    shoda = b
                    break
            if shoda is None and typy_zdroju[a["zdroj"]] == "agregator" and a["cas"]:
                # agregátor má akci pod jiným názvem: stejná scéna a přesně stejný začátek = tatáž akce
                # (jen když je taková právě jedna a ještě k ní z tohoto agregátoru nic nepatří)
                kandidati = [b for b in den if typy_zdroju[b["zdroj"]] == "primarni" and b["cas"] == a["cas"]
                             and misto_cast(a, b)]
                if len(kandidati) == 1 and a["zdroj"] not in kandidati[0].get("dalsi_zdroje", []):
                    shoda = kandidati[0]
            if shoda is None and typy_zdroju[a["zdroj"]] == "agregator" and a["cas"] and a.get("poloha"):
                # dva agregátory (GoOut × Colosseum) mají tutéž akci pod jiným názvem: stejný začátek, stejné
                # místo podle názvu i podle souřadnic (do 100 m) – jen když je taková právě jedna
                kandidati = [b for b in den if typy_zdroju[b["zdroj"]] == "agregator" and b["zdroj"] != a["zdroj"]
                             and b["cas"] == a["cas"] and b.get("poloha") and vzdalenost(a["poloha"], b["poloha"]) <= 100
                             and urcite_stejne_misto(a, b)]
                if len(kandidati) == 1 and a["zdroj"] not in kandidati[0].get("dalsi_zdroje", []):
                    shoda = kandidati[0]
            if shoda is None:
                vysledek.append(a)
                den.append(a)
                continue
            if shoda["zdroj"] == a["zdroj"]:
                # stejný zdroj, stejná akce (např. dva výpisy) – nech jednu
                if a["cas"] == shoda["cas"]:
                    continue
                vysledek.append(a)
                den.append(a)
                continue
            # jiný zdroj: doplň chybějící údaje, ale primární údaje nepřepisuj
            if (a["cas"] != shoda["cas"] and a["cas"] and shoda["cas"]) or (
                    a["stav"] not in ("neznamo",) and shoda["stav"] not in ("neznamo",) and a["stav"] != shoda["stav"]):
                rozpory += 1
            for k in ("vstupenky", "cena", "popis", "url"):
                if not shoda.get(k) and a.get(k):
                    shoda[k] = a[k]
            if shoda["stav"] == "neznamo" and a["stav"] != "neznamo":
                shoda["stav"] = a["stav"]
            shoda.setdefault("dalsi_zdroje", []).append(a["zdroj"])
    return vysledek, rozpory


# ---------------------------------------------------------------- porovnání s minulým během

def porovnej(nove, minule, ok_zdroje, dnes, nove_zdroje=(), zalozeno=None, agregatory=()):
    dnes_s = dnes.isoformat()
    min_podle_id = {a["id"]: a for a in minule}
    pouzite = set()
    vysledek, statistika = [], {"nove": 0, "zmeny": 0, "presuny": 0, "zmizele": 0, "odstranene": 0}

    def zapis_zmenu(a, co):
        a.setdefault("zmeny", [])
        a["zmeny"] = ([{"kdy": dnes_s, "co": co}] + a["zmeny"])[:3]
        statistika["zmeny"] += 1

    nesparovane = []
    for a in nove:
        b = min_podle_id.get(a["id"])
        if b:
            pouzite.add(b["id"])
            a["poprve_videno"] = b.get("poprve_videno", dnes_s)
            a["zmeny"] = b.get("zmeny", [])
            if b.get("stav") != a["stav"] and b.get("stav") and a["stav"] != "neznamo":
                popis = {"vyprodano": "vyprodáno", "volno": "vstupenky znovu k dispozici",
                         "zruseno": "zrušeno", "posledni": "poslední vstupenky"}.get(a["stav"], a["stav"])
                zapis_zmenu(a, popis)
            if (b.get("misto") or "") != (a["misto"] or "") and b.get("misto"):
                zapis_zmenu(a, f"změna místa (původně {b['misto']})")
            if (b.get("konec_datum") or "") != (a.get("konec_datum") or ""):
                zapis_zmenu(a, "změna termínu konce")
            vysledek.append(a)
        else:
            nesparovane.append(a)

    # tatáž akce, kterou teď přináší jiný zdroj (typicky nově přidaný web místa místo GoOut):
    # stejný den, čas, místo a podobný název → pokračuje stará akce, nic nového ani zmizelého
    nove_podle_terminu = {}
    for a in nove:
        nove_podle_terminu.setdefault((a["datum"], a.get("cas")), []).append(a)

    sbalene = {(norm(a["nazev"]), a.get("misto") or "", a["datum"]) for a in nove if a.get("opakovani")}

    def nahrazena(b):
        if (norm(b["nazev"]), b.get("misto") or "", b["datum"]) in sbalene:
            return True  # jednotlivý čas akce, která se teď ukazuje sbalená
        return next((a for a in nove_podle_terminu.get((b["datum"], b.get("cas")), [])
                     if a["zdroj"] != b["zdroj"] and stejne_misto(a, b)
                     and (podobne(a["nazev"], b["nazev"]) or b["zdroj"] in a.get("dalsi_zdroje", []))
                     and not (b["zdroj"] not in ok_zdroje and a["zdroj"] in agregatory)), None)

    minule_podle_terminu = {}
    for b in minule:
        minule_podle_terminu.setdefault((b["datum"], b.get("cas")), []).append(b)
    zbyle = []
    for a in nesparovane:
        b = next((b for b in minule_podle_terminu.get((a["datum"], a.get("cas")), [])
                  if b["id"] not in pouzite and b["zdroj"] != a["zdroj"]
                  and stejne_misto(a, b) and podobne(a["nazev"], b["nazev"])), None) if a.get("cas") else None
        if b and b["zdroj"] not in ok_zdroje and a["zdroj"] in agregatory:
            # částečný běh (--jen): zdroj staré akce se dnes nenačítal, agregátor ji nepřebírá
            # (sloučení by ji jinak nechalo vlastnímu zdroji) – stará akce zůstane, nová se zahodí
            if a["zdroj"] not in b.setdefault("dalsi_zdroje", []):
                b["dalsi_zdroje"].append(a["zdroj"])
            continue
        if b:
            pouzite.add(b["id"])
            a["poprve_videno"] = b.get("poprve_videno", dnes_s)
            a["zmeny"] = b.get("zmeny", [])
            vysledek.append(a)
        else:
            zbyle.append(a)
    nesparovane = zbyle

    # přesuny: stejná akce stejného zdroje s jiným datem/časem, starý termín zmizel
    zbyle_minule = [b for b in minule if b["id"] not in pouzite and b["zdroj"] in ok_zdroje
                    and (b.get("konec_datum") or b["datum"]) >= dnes_s]
    for a in nesparovane:
        kandidati = [b for b in zbyle_minule if b["zdroj"] == a["zdroj"] and norm(b["nazev"]) == norm(a["nazev"])
                     and b["id"] not in pouzite
                     and abs((dt.date.fromisoformat(b["datum"]) - dt.date.fromisoformat(a["datum"])).days) <= 45]
        if kandidati:
            b = min(kandidati, key=lambda x: abs((dt.date.fromisoformat(x["datum"]) - dt.date.fromisoformat(a["datum"])).days))
            pouzite.add(b["id"])
            a["poprve_videno"] = b.get("poprve_videno", dnes_s)
            a["zmeny"] = b.get("zmeny", [])
            stary = f"{dt.date.fromisoformat(b['datum']).strftime('%-d. %-m.')} {b.get('cas') or ''}".strip()
            zapis_zmenu(a, f"přesunuto (původně {stary})")
            statistika["presuny"] += 1
        else:
            if a["stav"] == "zruseno":
                continue  # o zrušené akci, kterou jsme nikdy neviděli, není co hlásit
            # první sběr nového zdroje není „novinka“ – akce tam už byly vypsané
            a["poprve_videno"] = zalozeno if ((a["zdroj"] in nove_zdroje or a.get("_okraj")) and zalozeno) else dnes_s
            a["zmeny"] = []
            statistika["nove"] += 1
        vysledek.append(a)

    # zmizelé akce
    for b in minule:
        if b["id"] in pouzite:
            continue
        konec = b.get("konec_datum") or b["datum"]
        if konec < dnes_s:
            continue  # proběhla
        if b.get("cas") and nahrazena(b):
            continue  # akci teď přináší jiný zdroj
        if b["zdroj"] not in ok_zdroje:
            vysledek.append(b)  # zdroj se dnes nenačetl – nic nesoudíme
            continue
        b["chybi_behu"] = b.get("chybi_behu", 0) + 1
        if b["chybi_behu"] >= ZMIZELA_ZRUSENO_PO:
            statistika["odstranene"] += 1
            continue
        statistika["zmizele"] += 1
        vysledek.append(b)
    for a in vysledek:
        if a["id"] in {x["id"] for x in nove}:
            a["chybi_behu"] = 0
    return vysledek, statistika


# ---------------------------------------------------------------- hlavní běh

SOUBEZNE = 8  # kolik webů se stahuje najednou


def stahni_zdroj(z, zz, stahni, dnes):
    """Stáhne a přečte jeden zdroj. Vrátí (akce, chyba, sitova_chyba, mekky_stahovac, sekundy)."""
    zacatek = time.monotonic()
    mekke = mekky_stahovac(stahni, zz["urls"])
    sitova = False
    try:
        surove = nacti(z.get("scraper", z["id"])).ziskej(mekke, zz, dnes)
        chyba = None
        if mekke.chyby and not mekke.uspechy:
            raise mekke.chyby[0][1]
    except requests.HTTPError as e:
        sitova = e.response is None or e.response.status_code >= 500 or e.response.status_code in (408, 429)
        kod = e.response.status_code if e.response is not None else "?"
        surove, chyba = [], f"web vrací chybu {kod}" + (" (stránka zmizela nebo se přesunula)" if kod == 404 else "")
    except (requests.ConnectionError, requests.Timeout):
        sitova = True
        surove, chyba = [], "web je nedostupný (neodpovídá)"
    except Exception as e:  # noqa: BLE001
        surove, chyba = [], f"web se asi změnil, skript ho neumí přečíst ({type(e).__name__})"
        print(f"{z['id']}:", file=sys.stderr)
        traceback.print_exc()
    return surove, chyba, sitova, mekke, time.monotonic() - zacatek


def main(jen_chybne=False, jen=None):
    """jen_chybne=True: dosběr – znovu se načtou jen zdroje, které při posledním běhu selhaly nebo hlásily
    varování; akce ostatních zdrojů zůstanou, jak byly (jejich weby se znovu nestahují).
    jen={"camp", …}: stejně tak, ale jen vyjmenované zdroje (ruční běh po úpravě jednoho zdroje)."""
    ted = dt.datetime.now(PRAHA)
    dnes = ted.date()
    cfg = yaml.safe_load((KOREN / "zdroje.yml").read_text(encoding="utf-8"))
    pr = priprav_pravidla(yaml.safe_load((KOREN / "pravidla.yml").read_text(encoding="utf-8")) or {})
    horizont = dnes + dt.timedelta(days=int(cfg.get("horizont_dni", 60)))
    DATA.mkdir(exist_ok=True)

    minule_data = nacti_json(DATA / "akce.json", {"akce": [], "meta": {}})
    zdravi = nacti_json(DATA / "zdravi.json", {})
    # vypnuté (aktivni: false) nebo smazané zdroje: pryč z přehledu i s jejich akcemi
    aktivni = {z["id"] for z in cfg["zdroje"] if z.get("aktivni", True)}
    zdravi = {k: v for k, v in zdravi.items() if k in aktivni}
    minule_data["akce"] = [a for a in minule_data.get("akce", []) if a.get("zdroj") in aktivni]
    mista_cache = nacti_json(DATA / "mista.json", {})
    stahni = vytvor_stahovac()

    podle_zdroje, typy_zdroju, ok_zdroje, problemy = {}, {}, set(), []
    nove_zdroje = set()
    vynechane = {}
    uplnost_log = []
    # Zdroj, který napoprvé selže na síti (výpadek, chyba 5xx), dostane druhý pokus až na konci běhu –
    # krátké poruchy webů bývají za pár minut pryč.
    fronta = [(z, False) for z in cfg["zdroje"] if z.get("aktivni", True)]
    if jen_chybne:
        fronta = [(z, d) for z, d in fronta if not zdravi.get(z["id"], {}).get("ok", True) or zdravi.get(z["id"], {}).get("varovani")]
        if not fronta:
            print("Dosběr: všechny zdroje při posledním běhu fungovaly, není co dělat.")
            return 0
        print("Dosběr zdrojů: " + ", ".join(z["id"] for z, _ in fronta))
    if jen:
        neznam = jen - {z["id"] for z, _ in fronta}
        if neznam:
            print(f"Neznámé nebo vypnuté zdroje: {', '.join(sorted(neznam))}", file=sys.stderr)
            return 1
        fronta = [(z, d) for z, d in fronta if z["id"] in jen]
        print("Jen zdroje: " + ", ".join(z["id"] for z, _ in fronta))
    # Stažení všech zdrojů najednou (SOUBEZNE vláken; každý web dostane jen jedno spojení, jako dřív).
    # Zpracování výsledků pak běží postaru po jednom zdroji ve stálém pořadí – výsledek je stejný,
    # jen se nečeká, až odpoví web po webu. Druhý pokus po síťové chybě běží na konci, jako dřív.
    pripravene = {z["id"]: dict(z, urls=[rozbal(u, dnes) for u in z["urls"]], _horizont=(horizont - dnes).days,
                                _mista=mista_cache.setdefault(z["id"], {})) for z, _ in fronta}
    with ThreadPoolExecutor(max_workers=SOUBEZNE) as ex:
        budouci_vysledky = {z["id"]: ex.submit(stahni_zdroj, z, pripravene[z["id"]], stahni, dnes) for z, _ in fronta}
        predem = {zid: f.result() for zid, f in budouci_vysledky.items()}
    casy = {}
    i = 0
    while i < len(fronta):
        z, druhy_pokus = fronta[i]
        i += 1
        zid = z["id"]
        typy_zdroju[zid] = z.get("typ", "primarni")
        zz = pripravene[zid]
        if not zdravi.get(zid, {}).get("posledni_ok"):
            nove_zdroje.add(zid)
        stav = zdravi.get(zid, {})
        if not druhy_pokus and zid in predem:
            surove, chyba, sitova, mekke, trvani = predem.pop(zid)
        else:
            surove, chyba, sitova, mekke, trvani = stahni_zdroj(z, zz, stahni, dnes)
        casy[zid] = casy.get(zid, 0) + trvani
        if chyba and sitova and not druhy_pokus:
            print(f"{zid}: {chyba} – zkusím znovu na konci běhu", file=sys.stderr)
            fronta.append((z, True))
            continue
        budouci = [a for a in surove if (a.get("konec_datum") or a["datum"]) >= dnes.isoformat()]
        minule_pocet = stav.get("pocet")
        varovani = None
        if chyba is None and mekke.chyby and budouci:
            # část adres zdroje se nenačetla: co máme, bereme, ale nic nepovažujeme za zrušené
            varovani = f"nenačetla se část programu ({len(mekke.chyby)} z {len(mekke.chyby) + mekke.uspechy} stránek)"
            for u, e in mekke.chyby:
                print(f"{zid}: {u} – {e!r}", file=sys.stderr)
        if chyba is None and not budouci and surove:
            chyba = "zdroj ukazuje jen proběhlé akce"
        if chyba is None and not surove:
            chyba = "zdroj nevrátil žádné akce (změnil se web?)"
        if chyba is None and sum(1 for a in budouci if not a["nazev"]) > len(budouci) / 2:
            chyba = "akce bez názvů – web se asi změnil"
        if (chyba is None and not varovani and minule_pocet and minule_pocet >= 5 and len(budouci) < PAD_ZDROJE * minule_pocet
                and stav.get("varovani_behu", 0) < VAROVANI_MAX_BEHU):
            # po VAROVANI_MAX_BEHU bězích se nižší počet bere jako nový normál (konec sezóny apod.)
            varovani = f"jen {len(budouci)} akcí místo obvyklých {minule_pocet}"
        if chyba:
            stav["chyb_v_rade"] = stav.get("chyb_v_rade", 0) + 1
            stav.setdefault("nefunguje_od", dnes.isoformat())
            stav.update(ok=False, chyba=chyba, varovani=None, posledni_pokus=ted.isoformat(timespec="minutes"))
            od = dt.date.fromisoformat(stav["nefunguje_od"]).strftime("%-d. %-m.")
            # jednodenní výpadek cizího webu není důvod k poplachu (akce zůstávají); hlásí se až druhý den po sobě.
            # Chyba ve čtení (web se změnil) se hlásí hned – tu musí někdo opravit.
            stav["hlasit"] = not sitova or stav["chyb_v_rade"] >= HLASIT_PO
            if stav["hlasit"]:
                problemy.append(f"- **{z['nazev']}**: {chyba} (nefunguje od {od}) – {stav['url'] if stav.get('url') else zz['urls'][0]}")
            else:
                print(f"{zid}: {chyba} – zatím nehlásím (první den)", file=sys.stderr)
        else:
            stav["varovani_behu"] = stav.get("varovani_behu", 0) + 1 if varovani else 0
            stav["hlasit"] = bool(varovani) and stav["varovani_behu"] >= HLASIT_PO
            if varovani:
                # podezřelý pokles nebo neúplné načtení: akce bereme, ale nic ze zdroje nepovažujeme za zrušené
                if stav["hlasit"]:
                    problemy.append(f"- **{z['nazev']}**: {varovani} – možná se změnil web")
            else:
                ok_zdroje.add(zid)
            stav.pop("nefunguje_od", None)
            stav.update(ok=True, chyba=None, varovani=varovani, chyb_v_rade=0,
                        pocet=len(budouci) if not varovani else (minule_pocet or len(budouci)),
                        posledni_ok=ted.isoformat(timespec="minutes"), posledni_pokus=ted.isoformat(timespec="minutes"))
        if not chyba and typy_zdroju[zid] != "agregator" and mekke.texty:
            zminene, chybi = kontrola_uplnosti(mekke.texty.values(), budouci, dnes, horizont)
            dosah = max((a["datum"] for a in budouci), default="-")
            stav["uplnost"] = {"akci": len(budouci), "do": dosah, "dnu_na_webu": zminene, "chybi_dnu": len(chybi),
                               "chybi_priklad": chybi[:8]}
            uplnost_log.append(f"  {zid:14} {len(budouci):5} akcí, do {dosah}  | web zmiňuje {zminene:3} dnů,"
                               f" z nich bez akce {len(chybi):3}" + (f"  např. {', '.join(chybi[:6])}" if chybi else ""))
        stav["nazev"] = z["nazev"]
        stav["url"] = z.get("web") or zz["urls"][0]
        zdravi[zid] = stav

        # Okno zdroje: kolik dní dopředu se čte (GoOut má vlastní „dni“, ostatní horizont).
        # Akce na samém konci okna nejsou novinky – jen se okno posunulo o den. Když se okno rozšíří
        # (např. GoOut z 21 na 120 dní), nejsou novinky ani akce v nově přidaném úseku.
        okno = int(z.get("dni") or (horizont - dnes).days)
        drive = stav.get("okno") if not chyba else None
        okraj = (dnes + dt.timedelta(days=min(okno, drive or okno) - 1)).isoformat()
        if not chyba:
            stav["okno"] = okno
        vybrane = []
        for a in budouci:
            if a["datum"] > horizont.isoformat():
                continue
            duvod = duvod_vynechani(a, pr)
            if duvod:
                vynechane[duvod.split(":")[0]] = vynechane.get(duvod.split(":")[0], 0) + 1
                continue
            a["zdroj"] = zid
            if a["datum"] >= okraj:
                a["_okraj"] = True  # jen se posunulo okno zdroje (nebo se rozšířilo) – to není novinka
            a["typ"] = urci_typ(a, pr)
            if a["typ"] == "jine" and z.get("typ_vychozi"):  # např. přehled kurzů: co nesedí jinam, je kurz
                a["typ"] = z["typ_vychozi"]
            if (z.get("tema") == "priroda" or z.get("tema_podle_znacky")) and \
                    NE_PRIRODA.search(bez_diakritiky(f"{a['nazev']} {a.get('znacky') or ''}").lower()):
                continue  # přírodovědný zdroj: aktivistické a „klimatické“ akce vůbec nebrat
            tema = urci_temata(a, z.get("tema"))
            if z.get("tema_podle_znacky") and a.get("znacky") in z["tema_podle_znacky"]:
                tema = sorted(set(tema) | {z["tema_podle_znacky"][a["znacky"]]})
                if "priroda" in tema and NE_PRIRODA.search(bez_diakritiky(a["nazev"]).lower()):
                    tema.remove("priroda")
            if tema:
                a["temata"] = tema
            elif z.get("jen_tema"):  # široký kalendář (muzeum, městská část): jen akce o přírodě/architektuře
                continue
            a.pop("mimo_prahu", None)
            a["id"] = ident(a)
            vybrane.append(a)
        podle_zdroje[zid] = sbal_opakovani(vybrane)

    print("Úplnost zdrojů (kolik akcí čteme a jestli web nezmiňuje dny, ze kterých nemáme nic):")
    print("\n".join(uplnost_log))
    print("Nejpomalejší zdroje (sekundy stahování; stahují se souběžně, celkem trvá zhruba ten nejpomalejší):")
    print("  " + ", ".join(f"{k} {v:.0f}" for k, v in sorted(casy.items(), key=lambda x: -x[1])[:8]))
    sloucene, rozpory = slouc(podle_zdroje, typy_zdroju)
    # kontrola překryvu s agregátorem (GoOut): u každého vlastního zdroje, kolik jeho akcí má i GoOut
    okna = [int(z["dni"]) for z in cfg["zdroje"] if z.get("aktivni", True) and z["id"] == "goout" and z.get("dni")]
    if okna and "goout" in ok_zdroje and "goout" in podle_zdroje:
        okno_do = (dnes + dt.timedelta(days=min(okna) - 1)).isoformat()
        print("Překryv s GoOut (akce zdroje v příštích dnech / z toho i na GoOut / GoOut navíc na stejném místě):")
        for zid, p in sorted(pokryti_agregatorem(sloucene, podle_zdroje, typy_zdroju, okno_do).items(),
                             key=lambda x: -(x[1]["shoda"] / x[1]["z"] if x[1]["z"] else 0)):
            if zid in zdravi:
                zdravi[zid]["goout"] = p
            print(f"  {zid:14} {p['z']:4} / {p['shoda']:4} / {p['navic']:4}")
    zalozeno = minule_data.get("meta", {}).get("zalozeno")
    for b in minule_data.get("akce", []):
        # jednorázově: 16. 11. 2026 se okno GoOut rozšířilo z 21 na 120 dní a tisíce akcí se omylem
        # označily jako nové (zbytečně plnily „Nově přidané“)
        if b.get("zdroj") == "goout" and b.get("poprve_videno") == "2026-11-16" and b["datum"] >= "2026-12-06" and zalozeno:
            b["poprve_videno"] = zalozeno
    akce, stat = porovnej(sloucene, minule_data.get("akce", []), ok_zdroje, dnes, nove_zdroje, zalozeno,
                          {z for z, t in typy_zdroju.items() if t == "agregator"})
    akce.sort(key=lambda a: (a["datum"], a["cas"] or "99:99", a["nazev"]))

    meta = minule_data.get("meta", {})
    meta.setdefault("zalozeno", dnes.isoformat())
    meta.update(
        vygenerovano=ted.isoformat(timespec="minutes"),
        predchozi_beh=minule_data.get("meta", {}).get("vygenerovano"),
        horizont_dni=(horizont - dnes).days,
        statistika=dict(stat, rozpory=rozpory, vynechano=vynechane, celkem=len(akce)),
    )
    for a in akce:
        a.pop("_okraj", None)
        a.pop("popis", None)  # jen pro pravidla výše; web ho neukazuje a zbytečně by nafukoval soubor
        for k in ("url", "vstupenky"):
            if a.get(k) and not str(a[k]).lower().startswith(("http://", "https://")):
                a[k] = None  # cizí weby: nikdy nepustit javascript: apod. do odkazu
    uloz_akce(DATA / "akce.json", meta, akce)
    uloz_json(DATA / "zdravi.json", zdravi)
    uloz_json(DATA / "mista.json", mista_cache)
    (DATA / "problemy.md").write_text("\n".join(problemy) + ("\n" if problemy else ""), encoding="utf-8")

    print(json.dumps(meta["statistika"], ensure_ascii=False, indent=1))
    print("Problémy:\n" + ("\n".join(problemy) or "žádné"))
    return 0


if __name__ == "__main__":
    jen = sys.argv[sys.argv.index("--jen") + 1] if "--jen" in sys.argv[:-1] else ""
    sys.exit(main(jen_chybne="--jen-chybne" in sys.argv,
                  jen={x.strip() for x in jen.replace(",", " ").split() if x.strip()} or None))
