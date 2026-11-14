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
UA = "Mozilla/5.0 (X11; Linux x86_64) KulturniVlozky/1.0 (+https://github.com/m-tomasek/kulturni-vlozky)"
PRAHA = ZoneInfo("Europe/Prague")
ZMIZELA_ZRUSENO_PO = 3      # po kolika bězích bez akce ve zdroji ji odstranit
ZMIZELA_OZNACIT_PO = 2      # od kolika běhů ukazovat „zrušeno?“
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
                time.sleep(2 * (pokus + 1))
        raise posledni

    return stahni


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
                if podobne(a["nazev"], b["nazev"]):
                    shoda = b
                    break
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
            a["poprve_videno"] = zalozeno if (a["zdroj"] in nove_zdroje and zalozeno) else dnes_s
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
    for z in cfg["zdroje"]:
        if not z.get("aktivni", True):
            continue
        zid = z["id"]
        typy_zdroju[zid] = z.get("typ", "primarni")
        zz = dict(z, urls=[rozbal(u, dnes) for u in z["urls"]], _horizont=(horizont - dnes).days,
                  _mista=mista_cache.setdefault(zid, {}))
        if zid not in zdravi:
            nove_zdroje.add(zid)
        stav = zdravi.get(zid, {})
        try:
            surove = nacti(zid).ziskej(stahni, zz, dnes)
            chyba = None
        except requests.HTTPError as e:
            kod = e.response.status_code if e.response is not None else "?"
            surove, chyba = [], f"web vrací chybu {kod}" + (" (stránka zmizela nebo se přesunula)" if kod == 404 else "")
        except (requests.ConnectionError, requests.Timeout):
            surove, chyba = [], "web je nedostupný (neodpovídá)"
        except Exception as e:  # noqa: BLE001
            surove, chyba = [], f"web se asi změnil, skript ho neumí přečíst ({type(e).__name__})"
            traceback.print_exc()
        budouci = [a for a in surove if (a.get("konec_datum") or a["datum"]) >= dnes.isoformat()]
        minule_pocet = stav.get("pocet")
        varovani = None
        if chyba is None and not budouci and surove:
            chyba = "zdroj ukazuje jen proběhlé akce"
        if chyba is None and not surove:
            chyba = "zdroj nevrátil žádné akce (změnil se web?)"
        if chyba is None and sum(1 for a in budouci if not a["nazev"]) > len(budouci) / 2:
            chyba = "akce bez názvů – web se asi změnil"
        if chyba is None and minule_pocet and minule_pocet >= 5 and len(budouci) < PAD_ZDROJE * minule_pocet:
            varovani = f"jen {len(budouci)} akcí místo obvyklých {minule_pocet}"
        if chyba:
            stav["chyb_v_rade"] = stav.get("chyb_v_rade", 0) + 1
            stav.setdefault("nefunguje_od", dnes.isoformat())
            stav.update(ok=False, chyba=chyba, varovani=None, posledni_pokus=ted.isoformat(timespec="minutes"))
            od = dt.date.fromisoformat(stav["nefunguje_od"]).strftime("%-d. %-m.")
            problemy.append(f"- **{z['nazev']}**: {chyba} (nefunguje od {od}) – {stav['url'] if stav.get('url') else zz['urls'][0]}")
        else:
            if varovani:
                # podezřelý pokles: akce bereme, ale nic ze zdroje nepovažujeme za zrušené
                problemy.append(f"- **{z['nazev']}**: {varovani} – možná se změnil web")
            else:
                ok_zdroje.add(zid)
            stav.pop("nefunguje_od", None)
            stav.update(ok=True, chyba=None, varovani=varovani, chyb_v_rade=0,
                        pocet=len(budouci) if not varovani else minule_pocet,
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
            a["typ"] = urci_typ(a, pr)
            a.pop("mimo_prahu", None)
            a["id"] = ident(a)
            vybrane.append(a)
        podle_zdroje[zid] = vybrane

    sloucene, rozpory = slouc(podle_zdroje, typy_zdroju)
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
    uloz_json(DATA / "akce.json", {"meta": meta, "akce": akce})
    uloz_json(DATA / "zdravi.json", zdravi)
    uloz_json(DATA / "mista.json", mista_cache)
    (DATA / "problemy.md").write_text("\n".join(problemy) + ("\n" if problemy else ""), encoding="utf-8")

    print(json.dumps(meta["statistika"], ensure_ascii=False, indent=1))
    print("Problémy:\n" + ("\n".join(problemy) or "žádné"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
