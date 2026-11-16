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


if __name__ == "__main__":
    unittest.main()
