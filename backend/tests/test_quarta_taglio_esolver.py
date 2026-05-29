import unittest
from datetime import datetime, timezone

from app.core.departments.models import Department  # noqa: F401
from app.modules.quarta_taglio.models import QuartaTaglioEsolverLink, QuartaTaglioRow
from app.modules.quarta_taglio.schemas import (
    QuartaTaglioCodF3CandidateResponse,
    QuartaTaglioCertifiableUnitResponse,
    QuartaTaglioDetailResponse,
    QuartaTaglioEsolverDdtRowResponse,
)
from app.modules.quarta_taglio.service import (
    _certificate_header_flow,
    _codice_f3_from_esolver_or_quarta,
    _detail_for_certiol_candidate,
    _esolver_status_for_rows,
    _serialize_ol_group,
)


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

    def test_list_group_keeps_esolver_cod_f3_empty_when_esolver_cod_f3_is_missing(self):
        now = datetime.now(timezone.utc)
        row = QuartaTaglioRow(
            id=1,
            codice_registro="REG1",
            data_registro=now,
            cod_odp="OL2026000001",
            cod_art="QUARTA-F3",
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
            cod_f3=None,
            rows=[],
            last_checked_at=now,
        )

        response = _serialize_ol_group([row], esolver_link=link)

        self.assertIsNone(response.esolver_cod_f3)
        self.assertEqual(response.cod_art, "QUARTA-F3")

    def test_detail_codice_f3_falls_back_to_quarta_cod_art_when_esolver_cod_f3_is_missing(self):
        now = datetime.now(timezone.utc)
        row = QuartaTaglioRow(
            id=1,
            codice_registro="REG1",
            data_registro=now,
            cod_odp="OL2026000001",
            cod_art="QUARTA-F3",
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

        result = _codice_f3_from_esolver_or_quarta(esolver_header_rows=[], quarta_rows=[row])

        self.assertEqual(result["value"], "QUARTA-F3")
        self.assertEqual(result["origin"], "quarta_fallback")

    def test_header_flow_treats_new_codification_raw_variants_as_raw_column(self):
        unit = QuartaTaglioCertifiableUnitResponse(
            unit_key="OL-1137000400",
            cod_odp="OL2025001353",
            cod_f3="1137000400",
            ddt="1365-19/05/2026",
            quantita=199,
            is_primary=True,
        )

        result = _certificate_header_flow(
            current_unit=unit,
            certifiable_units=[unit],
            quarta_rows=[],
            raw_description="WS-PRIMER DR. FORG. GUN BODY 630470A0",
            raw_cod_f3_override="1137000401",
            finished_description_override="WS-PRIMER DR. FORG. GUN BODY 630470A0",
        )

        self.assertEqual(result["raw_cod_f3"], "1137000400")
        self.assertEqual(result["raw_ddt"], "1365-19/05/2026")
        self.assertEqual(result["raw_quantita"], "199")
        self.assertIsNone(result["finished_cod_f3"])
        self.assertIsNone(result["finished_ddt"])

    def test_certiol_candidate_raw_variant_updates_raw_fields_not_finished_fields(self):
        detail = QuartaTaglioDetailResponse(
            cod_odp="OL2025001353",
            ready=True,
            status_color="green",
            status_message="ok",
            header={
                "codice_f3_raw": "1137000401",
                "descrizione_raw": "RAW 401",
                "codice_f3_finished": "",
                "descrizione_finished": "",
            },
            materials=[],
            missing_items=[],
            standard_candidates=[],
            selected_standard=None,
            chemistry=[],
            properties=[],
            notes=[],
            esolver_rows=[],
            certifiable_units=[],
        )
        candidate = QuartaTaglioCodF3CandidateResponse(
            cod_f3_odp="1137000401",
            cod_f3="1137000400",
            des_f3="RAW 400",
            relation="candidate",
        )
        unit = QuartaTaglioCertifiableUnitResponse(
            unit_key="OL2025001353-1137000400",
            cod_odp="OL2025001353",
            cod_f3="1137000400",
            is_primary=True,
        )

        result = _detail_for_certiol_candidate(detail=detail, candidate=candidate, unit=unit)

        self.assertEqual(result.header["codice_f3_raw"], "1137000400")
        self.assertEqual(result.header["descrizione_raw"], "RAW 400")
        self.assertEqual(result.header["codice_f3_finished"], "")
        self.assertEqual(result.header["descrizione_finished"], "")


if __name__ == "__main__":
    unittest.main()
