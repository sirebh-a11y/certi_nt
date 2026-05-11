import unittest

from app.modules.quarta_taglio.schemas import QuartaTaglioEsolverDdtRowResponse
from app.modules.quarta_taglio.service import _esolver_status_for_rows


class QuartaTaglioEsolverTest(unittest.TestCase):
    def test_esolver_rows_are_valid_even_when_cod_f3_differs_from_quarta(self):
        rows = [
            QuartaTaglioEsolverDdtRowResponse(
                cod_f3="039013960",
                orp="OL2026000334",
                ddt="1107-21/04/2026",
                qta_um_mag=97,
                cod_f3_matches_quarta=False,
            )
        ]

        returned_rows, status, message = _esolver_status_for_rows(rows, cod_art_keys={"039013900"})

        self.assertEqual(returned_rows, rows)
        self.assertEqual(status, "ok")
        self.assertEqual(message, "Dati eSolver/DDT collegati")


if __name__ == "__main__":
    unittest.main()
