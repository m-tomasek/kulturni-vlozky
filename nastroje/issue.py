"""Hlášení problémů se zdroji jako jedno GitLab issue (běží v CI po sběru).

- data/problemy.md není prázdný: do otevřeného issue „Problém se zdroji“ přidá komentář, jinak ho založí.
- je prázdný: otevřené issue s komentářem zavře.
Chyba API ukončí skript s kódem 1 (ať je vidět, že upozornění nefungují).
"""
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


def main():
    soubor = pathlib.Path(__file__).resolve().parent.parent / "data" / "problemy.md"
    text = soubor.read_text(encoding="utf-8").strip() if soubor.exists() else ""
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
