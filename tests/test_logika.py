"""Testy čisté logiky (bez sítě). Spouští se v CI před sběrem: python -m unittest discover -s tests"""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import run  # noqa: E402
from scrapers import dox, spolecne  # noqa: E402

D = dt.date(2026, 11, 16)


def a(zdroj, nazev, misto, cas="20:00", datum="2026-11-20", **kw):
    return dict({"zdroj": zdroj, "nazev": nazev, "misto": misto, "cas": cas, "datum": datum, "stav": "neznamo"}, **kw)


class Slouceni(unittest.TestCase):
    TYPY = {"jazzdock": "primarni", "kis": "primarni", "goout": "agregator"}

    def test_stejny_nazev_na_jinych_scenach_zustane(self):
        v, _ = run.slouc({"goout": [a("goout", "Vernisáž", "Galerie A"), a("goout", "Vernisáž", "Galerie B")]}, self.TYPY)
        self.assertEqual(len(v), 2)

    def test_agregator_se_neslouci_s_jinou_scenou(self):
        v, _ = run.slouc({"jazzdock": [a("jazzdock", "Jam Session", "Jazz Dock")],
                          "goout": [a("goout", "Jam Session", "Reduta Jazz Club"), a("goout", "Jam Session", "Jazz Dock")]},
                         self.TYPY)
        self.assertEqual(sorted(x["misto"] for x in v), ["Jazz Dock", "Reduta Jazz Club"])
        self.assertEqual(next(x for x in v if x["zdroj"] == "jazzdock")["dalsi_zdroje"], ["goout"])

    def test_shodny_dlouhy_nazev_se_slouci_i_pri_jinem_nazvu_mista(self):
        v, _ = run.slouc({"kis": [a("kis", "Večer deskových her pro dospělé", "KIŠ")],
                          "goout": [a("goout", "Večer deskových her pro dospělé", "Karlínské Spektrum")]}, self.TYPY)
        self.assertEqual(len(v), 1)

    def test_jiny_nazev_na_stejne_scene_ve_stejny_cas_je_tataz_akce(self):
        v, _ = run.slouc({"jazzdock": [a("jazzdock", "Krystof Trio", "Jazz Dock", "21:00")],
                          "goout": [a("goout", "Večer mladého jazzu", "Jazz Dock", "21:00"),
                                    a("goout", "Úplně jiná akce", "Jazz Dock", "18:00")]}, self.TYPY)
        self.assertEqual(sorted((x["zdroj"], x["cas"]) for x in v), [("goout", "18:00"), ("jazzdock", "21:00")])

    def test_prekryv_s_agregatorem(self):
        zdroje = {"jazzdock": [a("jazzdock", "Koncert A", "Jazz Dock", "19:00"), a("jazzdock", "Koncert B", "Jazz Dock", "22:00"),
                               a("jazzdock", "Daleko", "Jazz Dock", datum="2027-03-01")],
                  "goout": [a("goout", "Koncert A", "Jazz Dock", "19:00"), a("goout", "Workshop", "Jazz Dock", "10:00"),
                            a("goout", "Jinde", "Reduta Jazz Club", "19:00")]}
        v, _ = run.slouc(zdroje, self.TYPY)
        self.assertEqual(run.pokryti_agregatorem(v, zdroje, self.TYPY, "2026-12-06"),
                         {"jazzdock": {"z": 2, "shoda": 1, "navic": 1}})

    def test_jiny_cas_neni_duplicita(self):
        v, _ = run.slouc({"goout": [a("goout", "Film X", "Bio Oko", "17:00"), a("goout", "Film X", "Bio Oko", "20:30")]}, self.TYPY)
        self.assertEqual(len(v), 2)


class Porovnani(unittest.TestCase):
    def nova(self, **kw):
        x = a("x", "Akce", "Scéna", **kw)
        x["id"] = run.ident(x)
        return x

    def test_nova_akce(self):
        v, s = run.porovnej([self.nova()], [], {"x"}, D)
        self.assertEqual((s["nove"], v[0]["poprve_videno"]), (1, D.isoformat()))

    def test_prvni_sber_noveho_zdroje_neni_novinka(self):
        v, _ = run.porovnej([self.nova()], [], {"x"}, D, nove_zdroje={"x"}, zalozeno="2026-10-01")
        self.assertEqual(v[0]["poprve_videno"], "2026-10-01")

    def test_zmizela_akce_se_nejdriv_oznaci_a_pak_odstrani(self):
        minule = [dict(self.nova(), poprve_videno="2026-11-01")]
        for beh in range(1, run.ZMIZELA_ZRUSENO_PO):
            minule, s = run.porovnej([], minule, {"x"}, D)
            self.assertEqual((len(minule), minule[0]["chybi_behu"]), (1, beh))
        minule, s = run.porovnej([], minule, {"x"}, D)
        self.assertEqual((minule, s["odstranene"]), ([], 1))

    def test_nenacteny_zdroj_nic_nerusi(self):
        minule = [dict(self.nova(), poprve_videno="2026-11-01")]
        v, _ = run.porovnej([], minule, set(), D)
        self.assertNotIn("chybi_behu", v[0])


class Data(unittest.TestCase):
    def test_odvod_rok(self):
        self.assertEqual(spolecne.odvod_rok(5, 1, dt.date(2026, 12, 20)), dt.date(2027, 1, 5))
        self.assertEqual(spolecne.odvod_rok(20, 12, dt.date(2027, 1, 5)), dt.date(2026, 12, 20))
        self.assertEqual(spolecne.odvod_rok(20, 11, D), dt.date(2026, 11, 20))

    def test_zacatek_dlouheho_rozsahu(self):
        konec = spolecne.odvod_rok(30, 11, D)
        self.assertEqual((spolecne.zacatek_pred(1, 6, konec), konec), (dt.date(2026, 6, 1), dt.date(2026, 11, 30)))
        self.assertEqual(spolecne.zacatek_pred(20, 12, dt.date(2027, 1, 10)), dt.date(2026, 12, 20))

    def test_dox_rozsah(self):
        self.assertEqual(dox.rozsah("4. 9. 2026 – 24. 1. 2027"), (dt.date(2026, 9, 4), dt.date(2027, 1, 24)))
        self.assertEqual(dox.rozsah("28. 12. – 3. 1. 2027"), (dt.date(2026, 12, 28), dt.date(2027, 1, 3)))
        self.assertEqual(dox.rozsah("18. 11. 2026, 17:30"), (dt.date(2026, 11, 18), None))

    def test_cas(self):
        self.assertEqual(spolecne.cas("začátek v 19.30 hod"), "19:30")
        self.assertIsNone(spolecne.cas("bez času"))


class Odolnost(unittest.TestCase):
    def test_jedna_spatna_adresa_neshodi_zdroj(self):
        import requests

        def stahni(url):
            if url == "b":
                raise requests.ConnectionError("x")
            return "obsah " + url

        m = run.mekky_stahovac(stahni, ["a", "b", "c"])
        self.assertEqual([m("a"), m("b"), m("c")], ["obsah a", "", "obsah c"])
        self.assertEqual((m.uspechy, len(m.chyby)), (2, 1))
        with self.assertRaises(requests.ConnectionError):
            run.mekky_stahovac(stahni, ["b"])("b")  # jediná adresa: chyba je chyba zdroje
        with self.assertRaises(requests.ConnectionError):
            run.mekky_stahovac(lambda u: stahni("b"), ["a", "c"])("detail")  # vedlejší adresa (detail akce)

    def test_ulozeni_akci_po_radcich(self):
        import json
        import tempfile
        akce = [a("x", 'Název s "uvozovkami"', "Scéna"), a("x", "Druhá", "Scéna")]
        with tempfile.TemporaryDirectory() as d:
            c = pathlib.Path(d) / "akce.json"
            run.uloz_akce(c, {"zalozeno": "2026-11-01"}, akce)
            self.assertEqual(json.loads(c.read_text(encoding="utf-8")), {"meta": {"zalozeno": "2026-11-01"}, "akce": akce})
            self.assertEqual(len(c.read_text(encoding="utf-8").splitlines()), 5)

    def test_posun_okna_agregatoru_neni_novinka(self):
        x = a("goout", "Akce", "Scéna", _okraj=True)
        x["id"] = run.ident(x)
        v, _ = run.porovnej([x], [], {"goout"}, D, zalozeno="2026-10-01")
        self.assertEqual(v[0]["poprve_videno"], "2026-10-01")


class CelyBeh(unittest.TestCase):
    """Celý běh run.main() nanečisto: bez sítě, v dočasné složce, se třemi vymyšlenými zdroji."""

    def beh(self, slozka, pokusy):
        import json
        import types
        from unittest import mock

        import requests

        def chyba500():
            r = requests.Response()
            r.status_code = 500
            return requests.HTTPError(response=r)

        def modul(zid):
            def ziskej(stahni, zdroj, dnes):
                pokusy[zid] = pokusy.get(zid, 0) + 1
                if zid == "mrtvy" or (zid == "kolisavy" and pokusy[zid] == 1):
                    raise chyba500()
                return [spolecne.akce(nazev=f"Akce {zid} {i}", datum=dnes + dt.timedelta(days=i + 1), cas="19:00",
                                      misto=zid, url="https://x.cz/") for i in range(3)]
            return types.SimpleNamespace(ziskej=ziskej)

        with mock.patch.object(run, "KOREN", slozka), mock.patch.object(run, "DATA", slozka / "data"), \
                mock.patch.object(run, "nacti", modul), mock.patch.object(run, "vytvor_stahovac", lambda: None), \
                mock.patch("builtins.print"):
            run.main()
        return (json.loads((slozka / "data" / "akce.json").read_text(encoding="utf-8")),
                json.loads((slozka / "data" / "zdravi.json").read_text(encoding="utf-8")),
                (slozka / "data" / "problemy.md").read_text(encoding="utf-8"))

    def test_vypadky(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            slozka = pathlib.Path(d)
            (slozka / "zdroje.yml").write_text("zdroje:\n" + "".join(
                f"  - {{id: {z}, nazev: {z}, urls: ['https://{z}.cz/']}}\n" for z in ("dobry", "kolisavy", "mrtvy")), encoding="utf-8")
            (slozka / "pravidla.yml").write_text((run.KOREN / "pravidla.yml").read_text(encoding="utf-8"), encoding="utf-8")
            pokusy = {}
            akce, zdravi, problemy = self.beh(slozka, pokusy)
            # kolísavý zdroj dostal druhý pokus a prošel; mrtvý se první den nehlásí
            self.assertEqual(pokusy, {"dobry": 1, "kolisavy": 2, "mrtvy": 2})
            self.assertEqual(sorted({a["zdroj"] for a in akce["akce"]}), ["dobry", "kolisavy"])
            self.assertTrue(zdravi["kolisavy"]["ok"])
            self.assertEqual((zdravi["mrtvy"]["ok"], zdravi["mrtvy"]["hlasit"], problemy.strip()), (False, False, ""))
            # druhý den po sobě už se mrtvý zdroj hlásí
            akce, zdravi, problemy = self.beh(slozka, {})
            self.assertTrue(zdravi["mrtvy"]["hlasit"])
            self.assertIn("mrtvy", problemy)
            self.assertEqual(len(akce["akce"]), 6)


class Rozdeleni(unittest.TestCase):
    def test_tydny_a_prubezne(self):
        from nastroje import rozdel
        akce = [a("x", "Dnes", "S", datum="2026-11-16"), a("x", "Příští týden", "S", datum="2026-11-24"),
                a("x", "Výstava", "S", datum="2026-11-01", konec_datum="2026-12-31"),
                a("x", "Festival", "S", datum="2026-11-20", konec_datum="2026-11-22"),
                a("x", "Proběhlo", "S", datum="2026-11-10")]
        p, t = rozdel.rozdel(akce, D)
        self.assertEqual(sorted(x["nazev"] for x in p), ["Festival", "Výstava"])
        self.assertEqual({k: [x["nazev"] for x in v] for k, v in t.items()}, {"2026-47": ["Dnes"], "2026-48": ["Příští týden"]})


if __name__ == "__main__":
    unittest.main()
