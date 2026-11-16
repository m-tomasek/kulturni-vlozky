"""Společné pomůcky pro scrapery."""
import datetime as dt
import re
import unicodedata

MESICE = {
    "leden": 1, "ledna": 1, "led": 1,
    "unor": 2, "unora": 2, "uno": 2,
    "brezen": 3, "brezna": 3, "bre": 3,
    "duben": 4, "dubna": 4, "dub": 4,
    "kveten": 5, "kvetna": 5, "kve": 5,
    "cerven": 6, "cervna": 6, "cvn": 6,
    "cervenec": 7, "cervence": 7, "cvc": 7,
    "srpen": 8, "srpna": 8, "srp": 8,
    "zari": 9, "zar": 9,
    "rijen": 10, "rijna": 10, "rij": 10,
    "listopad": 11, "listopadu": 11, "lis": 11,
    "prosinec": 12, "prosince": 12, "pro": 12,
}


def bez_diakritiky(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def norm(s):
    """Normalizovaný název pro porovnávání."""
    s = bez_diakritiky(s or "").lower()
    s = re.sub(r"\b(premiera|derniera|vyprodano|zruseno|reprize)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def cisty(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def odvod_rok(den, mesic, dnes=None):
    """Rok k datu bez roku: datum nejblíž dnešku (programy ukazují i pár týdnů zpět)."""
    dnes = dnes or dt.date.today()
    kandidati = []
    for rok in (dnes.year - 1, dnes.year, dnes.year + 1):
        try:
            kandidati.append(dt.date(rok, mesic, den))
        except ValueError:
            pass
    # budoucnost má přednost: minulost bereme jen do 120 dní zpět
    return min(kandidati, key=lambda d: abs((d - dnes).days) if d >= dnes - dt.timedelta(days=120) else 10**6)


def zacatek_pred(den, mesic, konec):
    """Začátek rozsahu bez roku: poslední datum den.mesic., které není po konci rozsahu."""
    for rok in (konec.year, konec.year - 1):
        try:
            d = dt.date(rok, mesic, den)
        except ValueError:
            continue
        if d <= konec:
            return d
    return konec


def cas(s):
    """'19:30' / '19.30' / '19.00' -> 'HH:MM' nebo None."""
    m = re.search(r"\b(\d{1,2})[:.](\d{2})\b", s or "")
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return f"{h:02d}:{mi:02d}"


def akce(**kw):
    """Jednotný záznam akce. Povinné: nazev, datum (date)."""
    a = {
        "nazev": cisty(kw["nazev"]),
        "datum": kw["datum"].isoformat(),
        "cas": kw.get("cas"),
        "konec_datum": kw["konec_datum"].isoformat() if kw.get("konec_datum") else None,
        "konec_cas": kw.get("konec_cas"),
        "misto": cisty(kw.get("misto")) or None,
        "url": kw.get("url"),
        "vstupenky": kw.get("vstupenky"),
        "stav": kw.get("stav", "neznamo"),
        "cena": cisty(kw.get("cena")) or None,
        "typ": kw.get("typ"),
        "popis": cisty(kw.get("popis"))[:300] or None,
        "znacky": cisty(kw.get("znacky")) or None,
        "mimo_prahu": bool(kw.get("mimo_prahu", False)),
    }
    return a
