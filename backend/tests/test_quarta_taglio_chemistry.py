import unittest
from types import SimpleNamespace

from app.modules.quarta_taglio.service import _aggregate_block_values, _chemistry_fields_for_detail, _check_against_limits


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


def _property_value(field: str, value: str) -> SimpleNamespace:
    return SimpleNamespace(
        blocco="proprieta",
        campo=field,
        valore_finale=value,
        valore_standardizzato=value,
        valore_grezzo=value,
    )


def _property_limit(
    field: str,
    misura_min: float | None,
    misura_max: float | None,
    min_value: float | None,
    max_value: float | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        proprieta=field,
        misura_min=misura_min,
        misura_max=misura_max,
        min_value=min_value,
        max_value=max_value,
    )


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

    def test_chemistry_standard_range_is_inclusive_between_min_and_max(self):
        standard = SimpleNamespace(
            chemistry_limits=[_limit("Si", 0.7, 1.3)],
            property_limits=[],
        )

        for raw_value in ("0.7", "1.0", "1.3"):
            with self.subTest(raw_value=raw_value):
                app_rows = [
                    SimpleNamespace(
                        id=1,
                        cdq="CDQ-1",
                        values=[_value("Si", raw_value)],
                    )
                ]
                values = _aggregate_block_values(
                    fields=["Si"],
                    block="chimica",
                    app_rows=app_rows,
                    material_weights={"CDQ-1": 10.0},
                    standard=standard,
                )

                self.assertEqual(values[0].status, "ok")
                self.assertEqual(values[0].method, "single")

    def test_weighted_average_is_used_only_with_multiple_certificates(self):
        standard = SimpleNamespace(
            chemistry_limits=[_limit("Si", 0.7, 1.3)],
            property_limits=[],
        )
        app_rows = [
            SimpleNamespace(
                id=1,
                cdq="CDQ-1",
                values=[_value("Si", "0.8")],
            ),
            SimpleNamespace(
                id=2,
                cdq="CDQ-2",
                values=[_value("Si", "1.2")],
            ),
        ]

        values = _aggregate_block_values(
            fields=["Si"],
            block="chimica",
            app_rows=app_rows,
            material_weights={"CDQ-1": 1.0, "CDQ-2": 3.0},
            standard=standard,
        )

        self.assertEqual(values[0].method, "weighted")
        self.assertEqual(values[0].value, 1.1)

    def test_chemistry_standard_range_rejects_values_outside_min_and_max(self):
        standard = SimpleNamespace(
            chemistry_limits=[_limit("Si", 0.7, 1.3)],
            property_limits=[],
        )

        for raw_value in ("0.69", "1.31"):
            with self.subTest(raw_value=raw_value):
                app_rows = [
                    SimpleNamespace(
                        id=1,
                        cdq="CDQ-1",
                        values=[_value("Si", raw_value)],
                    )
                ]
                values = _aggregate_block_values(
                    fields=["Si"],
                    block="chimica",
                    app_rows=app_rows,
                    material_weights={"CDQ-1": 10.0},
                    standard=standard,
                )

                self.assertEqual(values[0].status, "out_of_range")

    def test_chemistry_limit_check_tolerates_float_noise_on_boundary(self):
        status, message = _check_against_limits(
            value=0.39999999999999997,
            limit_min=0.4,
            limit_max=1.0,
            missing_rows=[],
        )

        self.assertEqual(status, "ok")
        self.assertIsNone(message)

    def test_properties_are_not_checked_until_standard_is_confirmed(self):
        standard = SimpleNamespace(
            chemistry_limits=[],
            property_limits=[_property_limit("Rm", 20.0, 150.0, 310.0)],
        )
        app_rows = [
            SimpleNamespace(id=1, cdq="CDQ-1", diametro="98", values=[_property_value("Rm", "365")]),
        ]

        values = _aggregate_block_values(
            fields=["Rm"],
            block="proprieta",
            app_rows=app_rows,
            material_weights={"CDQ-1": 10.0},
            standard=standard,
            standard_confirmed=False,
        )

        self.assertEqual(values[0].status, "not_checked")
        self.assertIsNone(values[0].standard_min)

    def test_properties_check_each_cdq_when_diameters_use_multiple_ranges(self):
        standard = SimpleNamespace(
            chemistry_limits=[],
            property_limits=[
                _property_limit("Rm", 20.0, 150.0, 310.0),
                _property_limit("Rm", 150.0, 200.0, 340.0),
            ],
        )
        app_rows = [
            SimpleNamespace(id=1, cdq="CDQ-1", diametro="98", values=[_property_value("Rm", "365")]),
            SimpleNamespace(id=2, cdq="CDQ-2", diametro="190", values=[_property_value("Rm", "350")]),
        ]

        values = _aggregate_block_values(
            fields=["Rm"],
            block="proprieta",
            app_rows=app_rows,
            material_weights={"CDQ-1": 1.0, "CDQ-2": 1.0},
            standard=standard,
        )

        self.assertEqual(values[0].status, "ok")
        self.assertEqual(values[0].standard_label, "range multipli")
        self.assertIn("CDQ-1 Ø98: OK", values[0].message)
        self.assertIn("CDQ-2 Ø190: OK", values[0].message)

    def test_properties_fail_if_one_cdq_is_out_of_its_diameter_range(self):
        standard = SimpleNamespace(
            chemistry_limits=[],
            property_limits=[
                _property_limit("Rm", 20.0, 150.0, 310.0),
                _property_limit("Rm", 150.0, 200.0, 340.0),
            ],
        )
        app_rows = [
            SimpleNamespace(id=1, cdq="CDQ-1", diametro="98", values=[_property_value("Rm", "365")]),
            SimpleNamespace(id=2, cdq="CDQ-2", diametro="190", values=[_property_value("Rm", "320")]),
        ]

        values = _aggregate_block_values(
            fields=["Rm"],
            block="proprieta",
            app_rows=app_rows,
            material_weights={"CDQ-1": 1.0, "CDQ-2": 1.0},
            standard=standard,
        )

        self.assertEqual(values[0].status, "out_of_range")
        self.assertIn("CDQ-2 Ø190", values[0].message)
        self.assertIn("sotto minimo 340", values[0].message)


if __name__ == "__main__":
    unittest.main()
