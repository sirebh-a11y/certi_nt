import unittest
from types import SimpleNamespace

from app.modules.quarta_taglio.service import _aggregate_block_values, _chemistry_fields_for_detail


def _value(field: str, value: str) -> SimpleNamespace:
    return SimpleNamespace(
        blocco="chimica",
        campo=field,
        valore_finale=value,
        valore_standardizzato=value,
        valore_grezzo=value,
    )


def _limit(field: str, min_value: float | None = None, max_value: float | None = None) -> SimpleNamespace:
    return SimpleNamespace(elemento=field, min_value=min_value, max_value=max_value)


class QuartaTaglioChemistryTest(unittest.TestCase):
    def test_standard_drives_chemistry_and_flags_extra_supplier_elements(self):
        standard = SimpleNamespace(
            chemistry_limits=[
                _limit("Si", 0.2, 1.0),
                _limit("Mg", 0.4, 1.2),
            ],
            property_limits=[],
        )
        app_rows = [
            SimpleNamespace(
                id=1,
                cdq="CDQ-1",
                values=[
                    _value("Si", "0.62"),
                    _value("Pb", "0.03"),
                ],
            )
        ]

        fields = _chemistry_fields_for_detail(standard=standard, app_rows=app_rows)
        values = _aggregate_block_values(
            fields=fields,
            block="chimica",
            app_rows=app_rows,
            material_weights={"CDQ-1": 10.0},
            standard=standard,
        )
        by_field = {item.field: item for item in values}

        self.assertEqual(fields, ["Si", "Mg", "Pb"])
        self.assertEqual(by_field["Si"].status, "ok")
        self.assertEqual(by_field["Mg"].status, "missing_from_supplier")
        self.assertEqual(by_field["Pb"].status, "not_in_standard")

    def test_without_standard_recovered_chemistry_is_not_checked(self):
        app_rows = [
            SimpleNamespace(
                id=1,
                cdq="CDQ-1",
                values=[_value("Si", "0.62")],
            )
        ]

        fields = _chemistry_fields_for_detail(standard=None, app_rows=app_rows)
        values = _aggregate_block_values(
            fields=fields,
            block="chimica",
            app_rows=app_rows,
            material_weights={"CDQ-1": 10.0},
            standard=None,
        )

        self.assertEqual(fields, ["Si"])
        self.assertEqual(values[0].status, "not_checked")


if __name__ == "__main__":
    unittest.main()
