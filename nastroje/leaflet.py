"""Stáhne knihovnu Leaflet (mapa) z npm, ověří otisk a rozbalí ji do public/vendor/leaflet.

Web si ji pak bere z vlastní adresy, ne z cizího CDN. Otisk je ten, který npm uvádí pro leaflet@1.9.4.
"""
import base64
import hashlib
import io
import pathlib
import sys
import tarfile
import urllib.request

URL = "https://registry.npmjs.org/leaflet/-/leaflet-1.9.4.tgz"
SHA512 = "nxS1ynzJOmOlHp+iL3FyWqK89GtNL8U8rvlMOsQdTTssxZwCXh8N2NB3GDQOL+YR3XnWyZAxwQixURb+FA74PA=="
CIL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "public/vendor/leaflet")
CHCI = ("leaflet.js", "leaflet.css")


def main():
    with urllib.request.urlopen(URL, timeout=60) as r:  # noqa: S310 – pevná https adresa
        data = r.read()
    otisk = base64.b64encode(hashlib.sha512(data).digest()).decode()
    if otisk != SHA512:
        sys.exit(f"CHYBA: Leaflet má jiný otisk, než čekáme ({otisk}) – nenasazuji.")
    (CIL / "images").mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for m in tar.getmembers():
            if not m.isfile() or not m.name.startswith("package/dist/"):
                continue
            jmeno = m.name[len("package/dist/"):]
            if jmeno in CHCI or (jmeno.startswith("images/") and "/" not in jmeno[7:] and jmeno.endswith(".png")):
                (CIL / jmeno).write_bytes(tar.extractfile(m).read())
    print("Leaflet:", sorted(p.name for p in CIL.rglob("*") if p.is_file()))


if __name__ == "__main__":
    main()
