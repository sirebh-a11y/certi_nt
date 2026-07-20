import unittest

from app.modules.acquisition.models import AcquisitionRow
from app.modules.supplier_kpi.service import _supplier_detail_sheets
from app.modules.suppliers.models import Supplier


class SupplierKpiControlTypeExportTest(unittest.TestCase):
    def test_every_supplier_detail_sheet_contains_control_type(self):
        direct_supplier = Supplier(id=1, ragione_sociale="Fornitore Diretta")
        inverse_supplier = Supplier(id=2, ragione_sociale="Fornitore Inversa")
        rows = [
            AcquisitionRow(
                id=11,
                fornitore_id=direct_supplier.id,
                supplier=direct_supplier,
                qualita_tipo_controllo="diretta",
                qualita_valutazione="accettato",
            ),
            AcquisitionRow(
                id=12,
                fornitore_id=inverse_supplier.id,
                supplier=inverse_supplier,
                qualita_tipo_controllo="inversa",
                qualita_valutazione="respinto",
            ),
        ]

        sheets = _supplier_detail_sheets(
            rows,
            period_label="2026",
            supplier_label="Tutti i fornitori",
        )

        self.assertEqual(len(sheets), 2)
        exported_types = set()
        for _sheet_name, table in sheets:
            headers = table[4]
            control_type_index = headers.index("Tipo controllo")
            self.assertEqual(headers[control_type_index - 1], "Data richiesta")
            self.assertEqual(headers[control_type_index + 1], "Valutazione")
            exported_types.add(table[5][control_type_index])
        self.assertEqual(exported_types, {"Diretta", "Inversa"})

    def test_historical_row_exports_blank_control_type(self):
        supplier = Supplier(id=3, ragione_sociale="Fornitore Storico")
        row = AcquisitionRow(
            id=13,
            fornitore_id=supplier.id,
            supplier=supplier,
            qualita_tipo_controllo=None,
            qualita_valutazione="accettato",
        )

        [(_sheet_name, table)] = _supplier_detail_sheets(
            [row],
            period_label="2026",
            supplier_label="Tutti i fornitori",
        )
        control_type_index = table[4].index("Tipo controllo")

        self.assertEqual(table[5][control_type_index], "")


if __name__ == "__main__":
    unittest.main()
