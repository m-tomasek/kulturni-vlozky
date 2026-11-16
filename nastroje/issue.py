"""Hlášení problémů se zdroji jako jedno GitLab issue (běží v CI po sběru).

- data/problemy.md není prázdný: do otevřeného issue „Problém se zdroji“ přidá komentář, jinak ho založí.
- je prázdný: otevřené issue s komentářem zavře.
Chyba API ukončí skript s kódem 1 (ať je vidět, že upozornění nefungují).
"""
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request

NAZEV = "Problém se zdroji"
API = f"{os.environ['CI_API_V4_URL']}/projects/{os.environ['CI_PROJECT_ID']}"
TOKEN = os.environ["PROJEKT_TOKEN"]


def volej(metoda, cesta, **data):
    telo = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(API + cesta, data=telo, method=metoda, headers={"PRIVATE-TOKEN": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 – adresa je z CI proměnných
        return json.loads(r.read() or "null")


def token_konci():
    """Řádek s upozorněním, když přístupový token brzy vyprší (pak by se přestala ukládat data)."""
    try:
        req = urllib.request.Request(f"{os.environ['CI_API_V4_URL']}/personal_access_tokens/self",
                                     headers={"PRIVATE-TOKEN": TOKEN})
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            konec = json.loads(r.read()).get("expires_at")
        if konec and (dt.date.fromisoformat(konec) - dt.date.today()).days <= 21:
            return (f"- **PROJEKT_TOKEN vyprší {dt.date.fromisoformat(konec).strftime('%-d. %-m. %Y')}** – pak se přestanou "
                    "ukládat data. Vytvoř nový (Settings → Access tokens, role Maintainer, api + write_repository) "
                    "a vlož ho do Settings → CI/CD → Variables.")
    except Exception as e:  # noqa: BLE001 – kontrola platnosti je jen doplněk
        print(f"platnost tokenu se nepodařilo zjistit: {e!r}", file=sys.stderr)
    return ""


def main():
    soubor = pathlib.Path(__file__).resolve().parent.parent / "data" / "problemy.md"
    text = soubor.read_text(encoding="utf-8").strip() if soubor.exists() else ""
    text = "\n".join(x for x in (text, token_konci()) if x)
    q = urllib.parse.urlencode({"state": "opened", "search": NAZEV, "in": "title", "per_page": 20})
    otevrena = [i for i in volej("GET", f"/issues?{q}") if i["title"].startswith(NAZEV)]
    if text:
        if otevrena:
            volej("POST", f"/issues/{otevrena[0]['iid']}/notes", body=text[:60000])
            print(f"problémy: komentář do issue #{otevrena[0]['iid']}")
        else:
            i = volej("POST", "/issues", title=NAZEV, description=text[:60000])
            print(f"problémy: založeno issue #{i['iid']}")
    else:
        for i in otevrena:
            volej("POST", f"/issues/{i['iid']}/notes", body="Všechny zdroje zase fungují.")
            volej("PUT", f"/issues/{i['iid']}", state_event="close")
            print(f"problémy: zavřeno issue #{i['iid']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"CHYBA: hlášení problémů přes GitLab API selhalo: {e!r}", file=sys.stderr)
        sys.exit(1)
