import unittest
from types import SimpleNamespace
from xml.etree import ElementTree

from app.modules.supplier_kpi.service import (
    MAX_EXCEL_COLUMN_WIDTH,
    _sheet_xml,
    _supplier_detail_rows,
)


SPREADSHEET_NAMESPACE = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


class SupplierKpiXlsxFormatTest(unittest.TestCase):
    def test_mechanical_properties_have_requested_order_and_values(self):
        supplier = SimpleNamespace(id=1, ragione_sociale="Fornitore Test")
        row = SimpleNamespace(
            id=10,
            fornitore_id=supplier.id,
            supplier=supplier,
            fornitore_raw=None,
            qualita_data_ricezione=None,
            qualita_data_accettazione=None,
            qualita_data_richiesta=None,
            qualita_tipo_controllo=None,
            qualita_valutazione=None,
            qualita_note=None,
            lega_base=None,
            lega_designazione=None,
            diametro=None,
            cdq=None,
            colata=None,
            ddt=None,
            peso=None,
            ordine=None,
            values=[
                SimpleNamespace(blocco="proprieta", campo="HB", valore_finale="101", valore_standardizzato=None, valore_grezzo=None),
                SimpleNamespace(blocco="proprieta", campo="Rp0.2", valore_finale="202", valore_standardizzato=None, valore_grezzo=None),
                SimpleNamespace(blocco="proprieta", campo="Rm", valore_finale="303", valore_standardizzato=None, valore_grezzo=None),
                SimpleNamespace(blocco="proprieta", campo="A%", valore_finale="14", valore_standardizzato=None, valore_grezzo=None),
                SimpleNamespace(blocco="proprieta", campo="Rp0.2/Rm", valore_finale="0,67", valore_standardizzato=None, valore_grezzo=None),
                SimpleNamespace(blocco="proprieta", campo="IACS%", valore_finale="45", valore_standardizzato=None, valore_grezzo=None),
            ],
        )

        table = _supplier_detail_rows(
            [row],
            period_label="2026",
            supplier_label=supplier.ragione_sociale,
        )

        self.assertEqual(table[4][-6:], ["HB", "Rp0,2", "Rm", "A", "Rp0,2/Rm", "IACS%"])
        self.assertEqual(table[5][-6:], ["101", "202", "303", "14", "0,67", "45"])

    def test_sheet_xml_sets_custom_widths_for_every_populated_column(self):
        root = ElementTree.fromstring(
            _sheet_xml(
                [
                    ["Codice", "Descrizione"],
                    ["1", "Fornitore con una descrizione abbastanza lunga"],
                ]
            )
        )

        columns = root.findall("x:cols/x:col", SPREADSHEET_NAMESPACE)

        self.assertEqual(len(columns), 2)
        self.assertTrue(all(column.attrib["customWidth"] == "1" for column in columns))
        self.assertGreater(float(columns[1].attrib["width"]), float(columns[0].attrib["width"]))

    def test_long_cells_are_capped_wrapped_and_given_more_row_height(self):
        root = ElementTree.fromstring(
            _sheet_xml(
                [
                    ["Note"],
                    ["Testo molto lungo " * 30],
                ]
            )
        )

        column = root.find("x:cols/x:col", SPREADSHEET_NAMESPACE)
        long_cell = root.find("x:sheetData/x:row[@r='2']/x:c", SPREADSHEET_NAMESPACE)
        long_row = root.find("x:sheetData/x:row[@r='2']", SPREADSHEET_NAMESPACE)

        self.assertIsNotNone(column)
        self.assertEqual(float(column.attrib["width"]), MAX_EXCEL_COLUMN_WIDTH)
        self.assertIsNotNone(long_cell)
        self.assertEqual(long_cell.attrib["s"], "1")
        self.assertIsNotNone(long_row)
        self.assertEqual(long_row.attrib["customHeight"], "1")
        self.assertGreater(float(long_row.attrib["ht"]), 15)


if __name__ == "__main__":
    unittest.main()
