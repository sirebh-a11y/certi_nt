from types import SimpleNamespace

from app.modules.acquisition.material_form import (
    assess_material_form,
    classify_material_description,
)
from app.modules.acquisition.service import (
    _parse_openai_json_payload_for_aww_row_groups,
    _parse_openai_json_payload_for_grupa_kety_row_groups,
    _parse_openai_json_payload_for_leichtmetall_row_groups,
    _parse_openai_json_payload_for_zalco_row_groups,
)
from app.modules.standards.matching import (
    normalize_standard_product_type,
    rank_standard_candidates,
)


def _row(*descriptions: tuple[str, str], alloy: str = "6082", diameter: str = "40"):
    payload = {key: value for key, value in descriptions}
    evidence = SimpleNamespace(
        id=1,
        tipo_evidenza="ai_payload",
        metodo_estrazione="chatgpt",
        testo_grezzo=__import__("json").dumps(payload),
    )
    return SimpleNamespace(
        id=1,
        cdq="TEST",
        colata="HEAT",
        lega_base=alloy,
        lega_designazione=alloy,
        variante_lega=None,
        diametro=diameter,
        values=[],
        evidences=[evidence],
        ddt_document=None,
        certificate_document=None,
    )


def _standard(
    standard_id: int,
    *,
    product_type: str | None,
    alloy: str = "6082",
    variant: str | None = None,
):
    return SimpleNamespace(
        id=standard_id,
        code=f"STD-{standard_id}",
        lega_base=alloy,
        lega_designazione=alloy,
        variante_lega=variant,
        norma="EN TEST",
        trattamento_termico=None,
        tipo_prodotto=product_type,
        misura_tipo="diametro",
        chemistry_limits=[object()],
        property_limits=[object()],
    )


def test_material_form_recognizes_billet_without_using_casted_logs():
    assert classify_material_description("Billets casted, homogenized and turned") == "BILLETTE"
    assert classify_material_description("Casted logs, homogenized") is None


def test_material_form_recognizes_german_bar_and_arconic_item_description():
    assert assess_material_form(_row(("product_raw", "Rundstange 35,00"))).code == "BARRE"
    assert assess_material_form(_row(("item_description_raw", 'ROUND BAR EXTR. FORGE "A"'))).code == "BARRE"


def test_finished_bar_is_stronger_than_reference_to_source_billet():
    assessment = assess_material_form(
        _row(("product_description_raw", "EXTRUDED ROUND BAR PRODUCED FROM ALUMINIUM BILLET"))
    )
    assert assessment.code == "BARRE"


def test_cast_roundbars_explicitly_defined_as_billets_are_billets():
    assessment = assess_material_form(
        _row(
            (
                "product_description_raw",
                "Aluminium roundbars (billets) in alloy 2024, cast, homogenized and scalped.",
            )
        )
    )
    assert assessment.code == "BILLETTE"


def test_historical_ocr_fallback_recognizes_roundbars_billets_but_ignores_ut_notes():
    row = _row()
    row.certificate_document = SimpleNamespace(
        evidences=[],
        pages=[
            SimpleNamespace(
                ocr_text=(
                    "Aluminium roundbars (billets) in alloy 2024, cast, homogenized and scalped.\n"
                    "Ultrasonic inspection ends of bars\n"
                    "No. of Billets"
                ),
                testo_estratto=None,
            )
        ],
    )
    assert assess_material_form(row).code == "BILLETTE"

    notes_only = _row()
    notes_only.certificate_document = SimpleNamespace(
        evidences=[],
        pages=[
            SimpleNamespace(
                ocr_text="Ultrasonic inspection on billets\n100% inspection ends of bars\nNo. of Billets",
                testo_estratto=None,
            )
        ],
    )
    assert assess_material_form(notes_only).code == "DA_VERIFICARE"


def test_generic_extruded_and_conflicting_forms_remain_visible_to_user():
    assert assess_material_form(_row(("product_description_raw", "Extruded aluminium"))).code == "ESTRUSO_GENERICO"
    conflict = _row(
        ("product_description_raw", "Billets casted, homogenized and turned"),
        ("item_description_raw", "ROUND BAR"),
    )
    assert assess_material_form(conflict).code == "DATI_DISCORDANTI"


def test_notes_and_ultrasonic_text_do_not_classify_material():
    row = _row(("notes_raw", "100% ultrasonic inspection ends of bars"))
    assert assess_material_form(row).code == "DA_VERIFICARE"


def test_standard_product_type_normalizes_billet_singular_and_plural():
    assert normalize_standard_product_type("BILLETTA") == "BILLETTE"
    assert normalize_standard_product_type("BILLETTE") == "BILLETTE"


def test_standard_ranking_prefers_matching_material_form():
    row = _row(("product_description_raw", "billets"))
    ranked = rank_standard_candidates(
        [
            _standard(1, product_type="BARRE"),
            _standard(2, product_type="BILLETTA"),
            _standard(3, product_type=None),
        ],
        rows=[row],
    )
    assert ranked[0].standard.id == 2
    assert "forma materiale billette" in ranked[0].reasons


def test_unknown_form_keeps_manual_candidates_and_does_not_prefer_unread_variant():
    row = _row(("product_description_raw", "Casted logs"))
    ranked = rank_standard_candidates(
        [
            _standard(1, product_type="BARRE"),
            _standard(2, product_type="BILLETTE", variant="SPECIAL"),
        ],
        rows=[row],
    )
    assert {candidate.standard.id for candidate in ranked} == {1, 2}
    assert ranked[0].standard.id == 1
    assert any("forma materiale da confermare" in warning for warning in ranked[0].warnings)


def test_mixed_material_forms_are_reported_in_candidate_coverage():
    rows = [
        _row(("product_description_raw", "ROUND BAR")),
        _row(("product_description_raw", "Billets casted")),
    ]
    rows[1].id = 2
    ranked = rank_standard_candidates(
        [_standard(1, product_type="BARRE"), _standard(2, product_type="BILLETTE")],
        rows=rows,
    )
    assert ranked[0].compatible_material_rows == 1
    assert ranked[0].total_material_rows == 2
    assert any("1 righe su 2" in warning for warning in ranked[0].warnings)


def test_supplier_ddt_parsers_preserve_ai_product_description():
    _, kety_rows = _parse_openai_json_payload_for_grupa_kety_row_groups(
        '{"ddt_number_raw":"1","rows":[{"product_description_raw":"Extruded bar"}]}'
    )
    _, leicht_rows = _parse_openai_json_payload_for_leichtmetall_row_groups(
        '{"ddt_number_raw":"1","rows":[{"product_description_raw":"Billets casted"}]}'
    )
    _, zalco_rows = _parse_openai_json_payload_for_zalco_row_groups(
        '{"ddt_number_raw":"1","rows":[{"product_description_raw":"billets"}]}'
    )
    _, aww_rows = _parse_openai_json_payload_for_aww_row_groups(
        '{"ddt_number_raw":"1","rows":[{"product_raw":"Rundstange 35,00"}]}'
    )
    assert kety_rows[0]["product_description_raw"] == "Extruded bar"
    assert leicht_rows[0]["product_description_raw"] == "Billets casted"
    assert zalco_rows[0]["product_description_raw"] == "billets"
    assert aww_rows[0]["product_raw"] == "Rundstange 35,00"
