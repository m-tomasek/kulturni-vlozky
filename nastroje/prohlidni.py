"""Zhuštěný přehled stažených stránek (raw/*.html) pro psaní scraperů.

Pro každou stránku vypíše: JSON-LD události, data frameworků (Next/Nuxt),
nejčastější opakované bloky s datem (cesta tříd + ukázka HTML) a odkazy
na program. Výsledek: raw/_prehled_<název>.txt
"""
import collections
import json
import pathlib
import re
import sys

from bs4 import BeautifulSoup

RAW = pathlib.Path(__file__).resolve().parent.parent / "raw"
DATUM = re.compile(r"\b\d{1,2}\.\s?\d{1,2}\.|\b\d{1,2}\.\s?(led|úno|bře|dub|kvě|čer|črv|srp|zář|říj|lis|pro)|\b\d{4}-\d{2}-\d{2}|"
                   r"\b(po|út|st|čt|pá|so|ne)\b\.?\s*\d{1,2}\.", re.IGNORECASE)


def cesta(el, hloubka=3):
    casti = []
    while el is not None and el.name not in (None, "[document]", "html", "body") and len(casti) < hloubka:
        tr = ".".join(el.get("class", [])[:2])
        casti.append(el.name + ("." + tr if tr else ""))
        el = el.parent
    return " < ".join(casti)


def prehled(soubor):
    html = soubor.read_text(encoding="utf-8", errors="replace")
    s = BeautifulSoup(html, "lxml")
    out = [f"# {soubor.name}  ({len(html)} B)", f"title: {s.title.get_text(strip=True) if s.title else ''}"]

    ld = []
    for sc in s.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(sc.string or "")
        except Exception:  # noqa: BLE001
            continue
        for x in d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []:
            if isinstance(x, dict):
                ld.append(x)
    typy = collections.Counter(str(x.get("@type")) for x in ld)
    out.append(f"json-ld: {dict(typy)}")
    for x in [x for x in ld if "Event" in str(x.get("@type"))][:3]:
        x = {k: v for k, v in x.items() if k not in ("description", "image")}
        out.append("  " + json.dumps(x, ensure_ascii=False)[:900])

    for sc in s.find_all("script"):
        t = sc.string or ""
        if sc.get("id") in ("__NEXT_DATA__", "__NUXT_DATA__") or "window.__NUXT__" in t or "__INITIAL_STATE__" in t:
            out.append(f"framework-data: id={sc.get('id')} délka={len(t)} začátek={t[:300]!r}")
    skripty = [sc.get("src") for sc in s.find_all("script") if sc.get("src")]
    out.append("skripty: " + ", ".join(skripty[:8]))

    # bloky s datem
    for sc in s(["script", "style", "noscript"]):
        sc.decompose()
    pocty, ukazky = collections.Counter(), {}
    for txt in s.find_all(string=DATUM):
        el = txt.parent
        # vystoupat k bloku, který obsahuje i odkaz nebo nadpis
        blok = el
        for _ in range(6):
            if blok.parent is None or blok.parent.name in ("body", "html"):
                break
            if blok.find("a") and len(blok.get_text(" ", strip=True)) > 25:
                break
            blok = blok.parent
        k = cesta(blok)
        pocty[k] += 1
        ukazky.setdefault(k, []).append(blok)
    out.append("bloky s datem (cesta: počet):")
    for k, n in pocty.most_common(6):
        out.append(f"  [{n}] {k}")
    for k, _ in pocty.most_common(3):
        for b in ukazky[k][:2]:
            h = re.sub(r"\s+", " ", str(b))
            h = re.sub(r'(src|srcset|style|data-[\w-]+)="[^"]{40,}"', r'\1="…"', h)
            out.append("  ---- " + h[:1500])

    if pocty:
        out.append("texty bloků (nejčastější cesta):")
        for b in ukazky[pocty.most_common(1)[0][0]][:14]:
            out.append("  · " + re.sub(r"\s+", " ", b.get_text(" ", strip=True))[:220])

    odkazy = []
    for a in s.find_all("a", href=True):
        h = a["href"]
        if re.search(r"program|akce|kalendar|event|udalost|vystav|porad", h, re.IGNORECASE) and h not in odkazy:
            odkazy.append(h)
    out.append("odkazy na program: " + " ".join(odkazy[:25]))
    if len(odkazy) < 5:
        vse = []
        for a in s.find_all("a", href=True):
            if a["href"] not in vse:
                vse.append(a["href"])
        out.append("všechny odkazy: " + " ".join(vse[:70]))
    return "\n".join(out) + "\n"


def prehled_js(soubor):
    t = soubor.read_text(encoding="utf-8", errors="replace")
    najdi = sorted(set(re.findall(r"[\"'`]((?:/api|https?://[\w.]*planetum[\w.]*)/[\w\-/{}$.?=&]*)[\"'`]", t)))
    return f"# {soubor.name} ({len(t)} B)\napi cesty: " + " ".join(najdi[:120]) + "\n"


def okoli():
    """nastroje/okoli.txt: řádky "soubor|hledaný text" -> výřezy kolem prvních výskytů."""
    sez = pathlib.Path(__file__).resolve().parent / "okoli.txt"
    if not sez.exists():
        return
    out = []
    for r in sez.read_text(encoding="utf-8").splitlines():
        if "|" not in r or r.startswith("#"):
            continue
        soubor, hledat = r.split("|", 1)
        f = RAW / soubor
        if not f.exists():
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        i, n = 0, 0
        while n < 3:
            i = t.find(hledat, i)
            if i < 0:
                break
            out.append(f"===== {soubor} | {hledat} @ {i}\n" + re.sub(r"\s+", " ", t[max(0, i - 700):i + 1800]))
            i += len(hledat) + 1800
            n += 1
    (RAW / "_okoli.txt").write_text("\n".join(out) + "\n", encoding="utf-8")


def main():
    okoli()
    for f in sorted(RAW.glob("*.js")):
        (RAW / f"_prehled_{f.stem}.txt").write_text(prehled_js(f), encoding="utf-8")
    for f in sorted(RAW.glob("*.html")):
        try:
            txt = prehled(f)
        except Exception as e:  # noqa: BLE001
            txt = f"# {f.name}: chyba {e}\n"
        (RAW / f"_prehled_{f.stem}.txt").write_text(txt, encoding="utf-8")
        print(txt[:200])


if __name__ == "__main__":
    sys.exit(main())
