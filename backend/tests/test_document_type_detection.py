import unittest
from types import SimpleNamespace

from app.modules.acquisition.service import _detect_document_type


class DocumentTypeDetectionTest(unittest.TestCase):
    def test_leichtmetall_delivery_note_with_certificate_requirement_is_ddt(self):
        document = SimpleNamespace(
            nome_file_originale="80008535.pdf",
            pages=[
                SimpleNamespace(
                    testo_estratto=(
                        "LEICHTMETALL\n"
                        "Packing List\n"
                        "Forgialluminio 3 S.R.L. Delivery Note 80008535\n"
                        "Inspection Certificate 3.1 according to EN 10204\n"
                        "Quantity: 17,225 KG\n"
                    ),
                    ocr_text=None,
                )
            ],
        )

        self.assertEqual(_detect_document_type(document), "ddt")

    def test_leichtmetall_inspection_certificate_remains_certificate(self):
        document = SimpleNamespace(
            nome_file_originale="CdQ_94752_6082_Ø228.pdf",
            pages=[
                SimpleNamespace(
                    testo_estratto=(
                        "Abnahmeprüfzeugnis / Inspection Certificate 3.1 (EN 10204*)\n"
                        "Leichtmetall Aluminium Giesserei Hannover GmbH\n"
                        "Chemische Analyse / Chemical Analysis\n"
                        "Mechanical Properties\n"
                    ),
                    ocr_text=None,
                )
            ],
        )

        self.assertEqual(_detect_document_type(document), "certificato")


if __name__ == "__main__":
    unittest.main()
