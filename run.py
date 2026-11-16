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
import time
import traceback
from zoneinfo import ZoneInfo

import requests
import yaml

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


def vytvor_stahovac():
    sezeni = requests.Session()
    sezeni.headers["User-Agent"] = UA
    cache = {}

    def stahni(url):
        if url in cache:
            return cache[url]
        posledni = None
        for pokus in range(3):
            try:
                r = sezeni.get(url, timeout=30)
                r.raise_for_status()
                r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else r.apparent_encoding
                cache[url] = r.text
                return r.text
            except requests.RequestException as e:
                posledni = e
                kod = getattr(getattr(e, "response", None), "status_code", None)
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
        return text

    f.chyby, f.uspechy = [], 0
    return f


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


def urcite_stejne_misto(a, b):
    """Jako stejne_misto, ale jen když místo známe u obou a opravdu se shoduje."""
    return bool(norm(a.get("misto") or "")) and bool(norm(b.get("misto") or "")) and stejne_misto(a, b)


def pokryti_agregatorem(vysledek, akce_podle_zdroje, typy_zdroju, okno_do):
    """Kolik akcí každého vlastního zdroje má i agregátor (GoOut) – ať je vidět, které skripty jsou navíc.

    Vrací {zdroj: {"z": akcí zdroje v okně agregátoru, "shoda": z toho je má i agregátor,
                   "navic": akce agregátoru na stejném místě, které zdroj nemá (nebo se nespárovaly)}}.
    """
    agreg = [a for a in vysledek if typy_zdroju[a["zdroj"]] == "agregator" and a["datum"] <= okno_do]
    vystup = {}
    for zid, xs in akce_podle_zdroje.items():
        if typy_zdroju[zid] != "primarni":
            continue
        v_okne = [a for a in xs if a["datum"] <= okno_do]
        shoda = sum(1 for a in v_okne if any(typy_zdroju.get(z) == "agregator" for z in a.get("dalsi_zdroje", [])))
        mista = [{"misto": m} for m in {a.get("misto") for a in v_okne} if m]
        navic = sum(1 for g in agreg if any(urcite_stejne_misto(g, m) for m in mista))
        vystup[zid] = {"z": len(v_okne), "shoda": shoda, "navic": navic}
    return vystup


def minuty(c):
    if not c:
        return None
    h, m = c.split(":")
    return int(h) * 60 + int(m)


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
    text = bez_diakritiky(f"{a['nazev']} {a.get('znacky') or ''}").lower().replace("improvis", "")
    for typ, klice in pr["typy"]:
        if any(k in text for k in klice):
            if a.get("typ") in (None, "koncert") or typ in ("improvizace", "festival", "vystava"):
                return typ
    return a.get("typ") or "jine"


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

def porovnej(nove, minule, ok_zdroje, dnes, nove_zdroje=(), zalozeno=None):
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

def main():
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
    # Zdroj, který napoprvé selže na síti (výpadek, chyba 5xx), dostane druhý pokus až na konci běhu –
    # krátké poruchy webů bývají za pár minut pryč.
    fronta = [(z, False) for z in cfg["zdroje"] if z.get("aktivni", True)]
    i = 0
    while i < len(fronta):
        z, druhy_pokus = fronta[i]
        i += 1
        zid = z["id"]
        typy_zdroju[zid] = z.get("typ", "primarni")
        zz = dict(z, urls=[rozbal(u, dnes) for u in z["urls"]], _horizont=(horizont - dnes).days,
                  _mista=mista_cache.setdefault(zid, {}))
        if not zdravi.get(zid, {}).get("posledni_ok"):
            nove_zdroje.add(zid)
        stav = zdravi.get(zid, {})
        mekke = mekky_stahovac(stahni, zz["urls"])
        sitova = False
        try:
            surove = nacti(zid).ziskej(mekke, zz, dnes)
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
            traceback.print_exc()
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
        stav["nazev"] = z["nazev"]
        stav["url"] = zz["urls"][0]
        zdravi[zid] = stav

        vybrane = []
        for a in budouci:
            if a["datum"] > horizont.isoformat():
                continue
            duvod = duvod_vynechani(a, pr)
            if duvod:
                vynechane[duvod.split(":")[0]] = vynechane.get(duvod.split(":")[0], 0) + 1
                continue
            a["zdroj"] = zid
            if z.get("dni") and a["datum"] >= (dnes + dt.timedelta(days=int(z["dni"]) - 1)).isoformat():
                a["_okraj"] = True  # jen se posunulo okno zdroje o den – to není novinka
            a["typ"] = urci_typ(a, pr)
            a.pop("mimo_prahu", None)
            a["id"] = ident(a)
            vybrane.append(a)
        podle_zdroje[zid] = vybrane

    sloucene, rozpory = slouc(podle_zdroje, typy_zdroju)
    # kontrola překryvu s agregátorem (GoOut): u každého vlastního zdroje, kolik jeho akcí má i GoOut
    okna = [int(z["dni"]) for z in cfg["zdroje"] if z.get("aktivni", True) and z.get("typ") == "agregator" and z.get("dni")]
    if okna and any(typy_zdroju[z] == "agregator" and z in ok_zdroje for z in podle_zdroje):
        okno_do = (dnes + dt.timedelta(days=min(okna) - 1)).isoformat()
        print("Překryv s GoOut (akce zdroje v příštích dnech / z toho i na GoOut / GoOut navíc na stejném místě):")
        for zid, p in sorted(pokryti_agregatorem(sloucene, podle_zdroje, typy_zdroju, okno_do).items(),
                             key=lambda x: -(x[1]["shoda"] / x[1]["z"] if x[1]["z"] else 0)):
            if zid in zdravi:
                zdravi[zid]["goout"] = p
            print(f"  {zid:14} {p['z']:4} / {p['shoda']:4} / {p['navic']:4}")
    zalozeno = minule_data.get("meta", {}).get("zalozeno")
    akce, stat = porovnej(sloucene, minule_data.get("akce", []), ok_zdroje, dnes, nove_zdroje, zalozeno)
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
    sys.exit(main())
