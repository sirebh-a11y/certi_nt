import unittest
from datetime import datetime, timezone

from app.core.departments.models import Department  # noqa: F401
from app.modules.quarta_taglio.models import QuartaTaglioEsolverLink, QuartaTaglioRow
from app.modules.quarta_taglio.schemas import QuartaTaglioEsolverDdtRowResponse
from app.modules.quarta_taglio.service import _esolver_status_for_rows, _serialize_ol_group


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

    def test_list_group_exposes_esolver_cod_f3_separately_from_quarta_article(self):
        now = datetime.now(timezone.utc)
        row = QuartaTaglioRow(
            id=1,
            codice_registro="REG1",
            data_registro=now,
            cod_odp="OL2026000001",
            cod_art="QUARTA-LESS-PRECISE",
            des_art="Descrizione Quarta",
            cdq="CDQ1",
            colata="COL1",
            qta_totale=10,
            righe_materiale=1,
            lotti_count=1,
            cod_lotti=["LOT1"],
            saldo=True,
            status_color="green",
            status_message="OK",
            status_details=[],
            matching_row_ids=[7],
            seen_in_last_sync=True,
            first_seen_at=now,
            last_seen_at=now,
        )
        link = QuartaTaglioEsolverLink(
            cod_odp="OL2026000001",
            status="ok",
            message="Dati eSolver/DDT collegati",
            cod_f3="ESOLVER-F3",
            last_checked_at=now,
        )

        response = _serialize_ol_group([row], esolver_link=link)

        self.assertEqual(response.esolver_cod_f3, "ESOLVER-F3")
        self.assertEqual(response.cod_art, "QUARTA-LESS-PRECISE")


if __name__ == "__main__":
    unittest.main()
