import unittest
from datetime import datetime, timezone

from app.core.departments.models import Department  # noqa: F401
from app.modules.quarta_taglio.models import QuartaTaglioEsolverLink, QuartaTaglioFinalCertificate, QuartaTaglioRow
from app.modules.quarta_taglio.schemas import (
    QuartaTaglioCodF3CandidateResponse,
    QuartaTaglioCertifiableUnitResponse,
    QuartaTaglioDetailResponse,
    QuartaTaglioEsolverDdtRowResponse,
)
from app.modules.quarta_taglio.service import (
    _certificate_header_flow,
    _certification_progress_for_group,
    _codice_f3_from_esolver_or_quarta,
    _detail_for_certiol_candidate,
    _esolver_status_for_rows,
    _serialize_ol_group,
)


class QuartaTaglioEsolverTest(unittest.TestCase):
    def _quarta_row(self, *, cod_odp: str = "OL1", cod_art: str = "605000700") -> QuartaTaglioRow:
        now = datetime.now(timezone.utc)
        return QuartaTaglioRow(
            id=1,
            codice_registro="REG1",
            data_registro=now,
            cod_odp=cod_odp,
            cod_art=cod_art,
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

    def _certificate(
        self,
        *,
        cod_odp: str = "OL1",
        certificate_number: str = "7000_00_00/26",
        cod_f3: str = "605000730",
        ddt: str | None = None,
        unit_key: str | None = None,
        status: str = "draft",
        storage_key_pdf: str | None = None,
    ) -> QuartaTaglioFinalCertificate:
        return QuartaTaglioFinalCertificate(
            cod_odp=cod_odp,
            draft_number=certificate_number,
            certificate_number=certificate_number,
            cod_f3=cod_f3,
            ddt=ddt,
            unit_key=unit_key,
            status=status,
            storage_key_docx="cert.docx",
            storage_key_pdf=storage_key_pdf,
        )

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

    def test_certification_progress_reports_closed_ddts_but_open_raw_without_ddt(self):
        ready_key = "OL1|605000730|1464-28/05/2026|H-PO|34-15/01/2026"
        progress = _certification_progress_for_group(
            group_rows=[self._quarta_row()],
            certiol_rows=[],
            esolver_link=QuartaTaglioEsolverLink(
                cod_odp="OL1",
                rows=[
                    {
                        "cod_f3": "605000730",
                        "orp": "OL1",
                        "ddt": "1464-28/05/2026",
                        "odv_cli": "H-PO",
                        "odv_f3": "34-15/01/2026",
                        "qta_um_mag": 204,
                    }
                ],
            ),
            certificates=[
                self._certificate(cod_f3="605000700", ddt=None, status="draft"),
                self._certificate(
                    certificate_number="7000_00_30/26",
                    cod_f3="605000730",
                    ddt="1464-28/05/2026",
                    unit_key=ready_key,
                    status="pdf_final",
                    storage_key_pdf="cert.pdf",
                ),
            ],
        )

        self.assertEqual(progress.status, "partial")
        self.assertEqual(progress.message, "PDF chiuso per i DDT disponibili; restano Word/raw senza DDT.")

    def test_certification_progress_counts_closed_and_open_ddts(self):
        closed_key = "OL1|605000730|1204-29/04/2026|H-PO1|1032-16/12/2025"
        open_key = "OL1|605000730|1464-28/05/2026|H-PO2|34-15/01/2026"
        progress = _certification_progress_for_group(
            group_rows=[self._quarta_row()],
            certiol_rows=[],
            esolver_link=QuartaTaglioEsolverLink(
                cod_odp="OL1",
                rows=[
                    {
                        "cod_f3": "605000730",
                        "orp": "OL1",
                        "ddt": "1204-29/04/2026",
                        "odv_cli": "H-PO1",
                        "odv_f3": "1032-16/12/2025",
                        "qta_um_mag": 120,
                    },
                    {
                        "cod_f3": "605000730",
                        "orp": "OL1",
                        "ddt": "1464-28/05/2026",
                        "odv_cli": "H-PO2",
                        "odv_f3": "34-15/01/2026",
                        "qta_um_mag": 204,
                    },
                ],
            ),
            certificates=[
                self._certificate(
                    certificate_number="7000_00_30/26",
                    cod_f3="605000730",
                    ddt="1204-29/04/2026",
                    unit_key=closed_key,
                    status="pdf_final",
                    storage_key_pdf="cert.pdf",
                ),
                self._certificate(
                    certificate_number="7000_00_30/26",
                    cod_f3="605000730",
                    ddt="1464-28/05/2026",
                    unit_key=open_key,
                    status="draft",
                ),
            ],
        )

        self.assertEqual(progress.status, "partial")
        self.assertEqual(progress.message, "PDF chiuso per 1 di 2 DDT; resta da generare il PDF per altri DDT.")

    def test_certification_progress_reports_word_waiting_for_ddt(self):
        progress = _certification_progress_for_group(
            group_rows=[self._quarta_row()],
            certiol_rows=[],
            esolver_link=None,
            certificates=[self._certificate(cod_f3="605000700", ddt=None, status="draft")],
        )

        self.assertEqual(progress.status, "partial")
        self.assertEqual(progress.message, "Word preparato in anticipo; in attesa DDT.")

    def test_certification_progress_completed_when_all_ready_ddts_have_pdf(self):
        ready_key = "OL1|605000730|1464-28/05/2026|H-PO|34-15/01/2026"
        progress = _certification_progress_for_group(
            group_rows=[self._quarta_row()],
            certiol_rows=[],
            esolver_link=QuartaTaglioEsolverLink(
                cod_odp="OL1",
                rows=[
                    {
                        "cod_f3": "605000730",
                        "orp": "OL1",
                        "ddt": "1464-28/05/2026",
                        "odv_cli": "H-PO",
                        "odv_f3": "34-15/01/2026",
                        "qta_um_mag": 204,
                    }
                ],
            ),
            certificates=[
                self._certificate(
                    certificate_number="7000_00_30/26",
                    cod_f3="605000730",
                    ddt="1464-28/05/2026",
                    unit_key=ready_key,
                    status="pdf_final",
                    storage_key_pdf="cert.pdf",
                )
            ],
        )

        self.assertEqual(progress.status, "completed")
        self.assertEqual(progress.message, "Tutti i DDT certificati hanno PDF chiuso.")


if __name__ == "__main__":
    unittest.main()
