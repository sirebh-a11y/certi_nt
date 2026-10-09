from types import SimpleNamespace as NS
import pytest
from app.modules.standards.matching import rank_standard_candidates
from test_material_form_standard_matching import _row, _standard


def standard(basis, **changes):
    std = _standard(1 if basis == "A" else 2, product_type="BARRE", alloy="7003")
    std.elongation_basis = basis
    std.trattamento_termico = "T6"
    std.property_limits = [NS(proprieta="A%", misura_min=lo, misura_max=hi,
                              min_value=10 if basis == "A" else 8, max_value=None)
                           for lo, hi in ((None, 50), (50, 150))]
    for k, v in changes.items():
        setattr(std, k, v)
    return std


def row(value, *, diameter="40", alloy="7003", evidence=None, form="EXTRUDED ROUND BAR"):
    item = _row(("product_raw", form), alloy=alloy, diameter=diameter)
    item.values = [NS(blocco="proprieta", campo="A%", valore_finale=value,
                      valore_standardizzato=None, valore_grezzo=value,
                      primary_evidence=NS(testo_grezzo=evidence, metodo_estrazione="ocr"))]
    return item


def ranked(rows, **kwargs):
    return rank_standard_candidates([standard("A"), standard("A50mm")], rows=rows, **kwargs)


@pytest.mark.parametrize("value,expected", [("9", "A50mm"), ("8", "A50mm"), ("9,99", "A50mm"),
    ("10", "A"), ("12", "A"), ("7.99", "A"), ("0", "A"), (None, "A"), ("<9", "A"), ("9-10", "A")])
def test_numeric_hint_not_silent_confirmation(value, expected):
    result = ranked([row(value)])
    assert result[0].standard.elongation_basis == expected
    if expected == "A50mm":
        assert result[0].confidence != "alta"
        assert any("Verifica il tipo di prova" in w for w in result[0].warnings)


@pytest.mark.parametrize("diameter,expected", [("50", "A50mm"), ("50.01", "A50mm"), ("150", "A50mm"),
    ("150.01", "A"), (None, "A"), ("0", "A"), ("40 mm", "A")])
def test_dimension_boundaries(diameter, expected):
    assert ranked([row("9", diameter=diameter)])[0].standard.elongation_basis == expected


def test_source_method_has_priority_over_numeric_hint():
    assert ranked([row("9", evidence="A (%) 9")])[0].standard.elongation_basis == "A"
    assert ranked([row("12", evidence="A50mm (%) 12")])[0].standard.elongation_basis == "A50mm"
    assert ranked([row("9", evidence='{"A%": 9}')])[0].standard.elongation_basis == "A50mm"


def test_mixed_sources_and_missing_or_failed_row_do_not_promote_a50():
    for others in (row("7"), row(None), row("9", evidence="A (%) 9")):
        assert ranked([row("9"), others])[0].standard.elongation_basis == "A"
    assert ranked([row("9", evidence="A50mm (%) 9"), row("11", evidence="A (%) 11")])[0].standard.elongation_basis == "A"
    assert ranked([row("9"), row("11")])[0].standard.elongation_basis == "A50mm"


def test_other_alloy_form_temper_and_conflicting_limits_not_promoted():
    assert not ranked([row("9", alloy="7055")])
    assert ranked([row("9", form="Billets cast and homogenized")])[0].standard.elongation_basis == "A"
    assert ranked([row("9", alloy="7003 T62")])[0].standard.elongation_basis == "A"
    a, a50 = standard("A"), standard("A50mm")
    a50.property_limits.append(a50.property_limits[0])
    assert rank_standard_candidates([a, a50], rows=[row("9")])[0].standard is a


def test_proposed_unsaved_values_are_used_for_incoming_preview():
    item = row("12")
    assert ranked([item], elongation_overrides={item.id: "9"})[0].standard.elongation_basis == "A50mm"
    assert item.values[0].valore_finale == "12"
    item.values = []
    assert ranked([item], elongation_overrides={item.id: "9"})[0].standard.elongation_basis == "A50mm"


def test_conflicting_evidence_and_specific_variant_cannot_gain_numeric_hint():
    item = row("9", evidence="A (%) 9")
    item.values[0].campo = "A50mm"
    assert ranked([item])[0].standard.elongation_basis == "A"
    item = row("9")
    item.variante_lega = "Specifica cliente particolare"
    assert ranked([item])[0].standard.elongation_basis == "A"


def test_legacy_standards_are_not_relabelled_or_modified():
    legacy = standard("A", elongation_basis=None)
    legacy.property_limits[0].min_value = 8
    originals = [standard("A"), standard("A50mm"), legacy]
    results = rank_standard_candidates(originals, rows=[row("9")])
    assert results[0].standard.elongation_basis == "A50mm"
    assert legacy.elongation_basis is None
    assert legacy.property_limits[0].min_value == 8
