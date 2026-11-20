"""Strength formatting is confined to generated certificate documents."""
from pathlib import Path

import pytest
from docx import Document

from app.core.users.models import User
from app.modules.acquisition.models import AcquisitionRow, ReadValue
from app.modules.quarta_taglio.certificate_docx import (
    _property_spec_value,
    build_forgialluminio_draft_docx,
)
from app.modules.quarta_taglio.schemas import QuartaTaglioAggregateValueResponse as Value
from app.modules.quarta_taglio.service import _aggregate_block_values, _build_standard_conformity
from app.modules.standards.models import NormativeStandard, NormativeStandardProperty
import test_quarta_taglio_docx_content_controls as docx_fixture


@pytest.mark.parametrize("field", ["Rp0.2", "Rm"])
@pytest.mark.parametrize(("value", "minimum", "expected"), [
    (378.3, 378, "378"),
    (378.5, 378, "379"),
    (378.7, 378, "379"),
    (378, 378, "378"),
    (377.3, 378, "377"),
    (377.7, 378, "377,7"),
    (378.3, 378.25, "378,3"),
    (378.51, 378.75, "378,51"),
    (400.7, None, "401"),
    (None, 378, "-"),
])
def test_strength_rounding_uses_the_actual_minimum(field, value, minimum, expected):
    item = Value(field=field, value=value, standard_min=minimum, method="single", status="ok")
    assert _property_spec_value(item, field=field) == expected


def _mechanical_aggregate(*measurements: tuple[int, str, str], limits: list[NormativeStandardProperty]):
    rows = [
        AcquisitionRow(id=i, cdq=f"TEST-{i}", diametro=diameter, values=[
            ReadValue(blocco="proprieta", campo="Rm", valore_finale=value),
        ])
        for i, diameter, value in measurements
    ]
    return _aggregate_block_values(
        fields=["Rm"], block="proprieta", app_rows=rows, material_weights={},
        standard=NormativeStandard(property_limits=limits),
    )[0]


def test_print_guard_uses_precision_before_api_rounding_and_does_not_change_conformity():
    item = _mechanical_aggregate(
        (1, "30", "377,99999"),
        limits=[NormativeStandardProperty(proprieta="Rm", misura_max=50, min_value=378)],
    )
    before = item.model_dump()
    assert before["value"] == 378 and before["status"] == "out_of_range"
    assert "_unrounded_value" not in before
    assert _property_spec_value(item, field="Rm") == "377,99999"
    outcome, issues = _build_standard_conformity(chemistry=[], properties=[item], selected_standard_confirmed=True)
    assert outcome == "non_conforme" and len(issues) == 1
    assert item.model_dump() == before


def test_no_rounding_without_a_single_minimum_for_different_diameters():
    item = _mechanical_aggregate(
        (1, "30", "377,7"), (2, "70", "415,2"),
        limits=[
            NormativeStandardProperty(proprieta="Rm", misura_max=50, min_value=378),
            NormativeStandardProperty(proprieta="Rm", misura_min=50, min_value=400),
        ],
    )
    assert item.standard_min is None and item.standard_label == "range multipli"
    assert item.status == "out_of_range"
    assert _property_spec_value(item, field="Rm") == "377,7"


def build_sample(path: Path, *, exception: bool):
    detail = docx_fixture.QuartaTaglioDocxContentControlTests._minimal_detail()
    detail.header = {"lega": "6082", "colata": "LOTTO-TEST", "cliente": "CLIENTE DI PROVA"}
    detail.properties = [
        Value(field=field, value=value, standard_min=minimum, method="single", status=status)
        for field, value, minimum, status in [
            ("Rp0.2", 378.3, 378.25 if exception else 378, "ok"),
            ("Rm", 377.7 if exception else 378.5, 378, "out_of_range" if exception else "ok"),
            ("Rp0.2 / Rm", 0.85, None, "ok"),
            ("A%", 9.5, 8, "ok"),
            ("HB", 110.8, 100, "ok"),
        ]
    ]
    detail.chemistry = [Value(field="Si", value=0.123, method="single", status="ok")]
    actor = User(name="Operatore di prova", email="test@example.invalid", role="admin")
    build_forgialluminio_draft_docx(
        detail=detail, output_path=path, draft_number="7013_00_00/26", certified_by=actor, quality_manager=actor,
    )


@pytest.mark.parametrize("exception", [False, True])
def test_real_certificate_word_keeps_other_cells_and_prints_strengths(tmp_path, exception):
    path = tmp_path / "sample.docx"
    build_sample(path, exception=exception)
    document = Document(path)
    table = next(t for t in document.tables if any(c.text == "Rm\n(N/mm²)" for c in t.rows[0].cells))
    headers, minima, measurements = ([c.text for c in row.cells] for row in table.rows)
    rp = headers.index("Rp 0,20\n(N/mm²)")
    rm = headers.index("Rm\n(N/mm²)")
    assert (minima[rp], minima[rm]) == ("378,25" if exception else "378", "378")
    assert (measurements[rp], measurements[rm]) == (("378,3", "377,7") if exception else ("378", "379"))
    assert measurements[headers.index("Rp/Rm")] == "0,85"
    assert measurements[headers.index("A(%)")] == "9,5"
    assert measurements[headers.index("HB")] == "110,8"
    assert any(c.text == "0,123" for t in document.tables for row in t.rows for c in row.cells)
