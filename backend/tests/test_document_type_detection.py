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

    def test_leichtmetall_delivery_note_with_split_ocr_packing_list_is_ddt(self):
        document = SimpleNamespace(
            nome_file_originale="202606100932-1.pdf",
            pages=[
                SimpleNamespace(
                    testo_estratto=(
                        "LEICHTMETALL\n"
                        "Packi n g List\n"
                        "Delivery Note 80009200\n"
                        "Transportnummer 6002608\n"
                        "Order Confirmation 2003420\n"
                        "Purchase Number 94\n"
                        "Quantity: 10,008 KG\n"
                        "Inspection Certificate 3.1 according to EN 10204\n"
                        "chem. Analyse gemaess EN 2486\n"
                    ),
                    ocr_text=None,
                )
            ],
        )

        self.assertEqual(_detect_document_type(document), "ddt")

    def test_leichtmetall_certificate_with_chemical_table_without_mechanical_properties_is_certificate(self):
        document = SimpleNamespace(
            nome_file_originale="CdQ_94731.32_6182_Ø163.pdf",
            pages=[
                SimpleNamespace(
                    testo_estratto=(
                        "Abnahmeprüfzeugnis / Inspection Certificate 3.1 (EN 10204*)\n"
                        "EGA Leichtmetall GmbH\n"
                        "Charge/ Cast No: 94731.32\n"
                        "Chemische Analyse/ Chemical Analysis:\n"
                        "Si % Fe % Cu % Mn % Mg % Cr % Zn % Ti %\n"
                        "Min. Max. Ist/act. 1,24 0,25 0,06 0,55 0,84\n"
                    ),
                    ocr_text=None,
                )
            ],
        )

        self.assertEqual(_detect_document_type(document), "certificato")

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
