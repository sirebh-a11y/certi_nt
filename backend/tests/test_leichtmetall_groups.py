import json
from dataclasses import replace

import pytest

from app.modules.acquisition.leichtmetall_groups import (
    DdtMember, cast_identity, coverage, kg, recover_cached_identity,
)


@pytest.mark.parametrize("text,expected", [
    ("95131", ("95131",)), ("95131.33", ("95131", "95133")),
    ("95131.33`.35", ("95131", "95133", "95135")),
    ("95131.95133.95135", ("95131", "95133", "95135")),
    ("00131.33", ("00131", "00133")), ("95131 . 33 . 35", ("95131", "95133", "95135")),
    ("95131-33", ()), ("95131/33", ()), ("95131,33", ()),
    ("95131.31", ()), ("95131.333", ()), ("10204", ()),
])
def test_identity(text, expected):
    assert cast_identity(text).members == expected


def group():
    return (DdtMember(1, "95131", "3962", "7175", "150", "332.2+3", True),
            DdtMember(2, "95133", "1085", "7175", "150", "332.2+3", True))


def cert(**kwargs):
    return dict(cdq="95131.33", colata="95131.33", peso="5.047", lega="7175",
                diametro="150", ordine="332.2+3", **kwargs)


def test_real_group_and_three_members_not_range():
    assert coverage(members=group(), target_id=2, certificate=cert()).valid
    members = group() + (replace(group()[0], row_id=3, batch="95135", weight="500"),)
    c = {**cert(), "cdq":"95131.33.35", "colata":"95131.33.35", "peso":"5547"}
    assert coverage(members=members, target_id=3, certificate=c).valid
    assert not coverage(members=members[:2], target_id=1, certificate=c).valid


@pytest.mark.parametrize("change", [
    {"peso":"5088"}, {"lega":"7075"}, {"diametro":"144"},
    {"ordine":"332.4"}, {"cdq":"95131.35"}, {"peso":"5 t"},
])
def test_contradictions_are_not_missing(change):
    assert not coverage(members=group(), target_id=1, certificate={**cert(), **change}).valid


def test_missing_duplicate_partial_and_foreign_lots_do_not_pass():
    for members in (group()[:1], group() + (group()[0],),
                    (replace(group()[0], complete=False), group()[1]),
                    (replace(group()[0], weight=None), group()[1])):
        assert not coverage(members=members, target_id=1, certificate=cert()).valid
    assert not coverage(members=group(), target_id=99, certificate=cert()).valid
    # Other lots on the same truck must NOT inflate this certificate's total.
    assert coverage(members=group() + (replace(group()[0], row_id=3, batch="99999"),),
                    target_id=1, certificate=cert()).valid


def test_missing_total_requires_complete_unique_order():
    assert coverage(members=group(), target_id=1, certificate={**cert(), "peso":None}).valid
    assert not coverage(members=group(), target_id=1,
                        certificate={**cert(), "peso":None, "ordine":None}).valid


def test_cache_repair_is_pure_targeted_and_preserves_technical_values():
    p = dict(match_values={"numero_certificato_certificato":"95131", "colata_certificato":"95131"},
             chemistry={"Si":1}, debug_raw_output=json.dumps({"core":{"charge_cast_no":"95131.33"}}))
    new = recover_cached_identity(p, "leichtmetall")
    assert new["match_values"]["colata_certificato"] == "95131.33"
    assert new["chemistry"] == p["chemistry"]
    assert p["match_values"]["colata_certificato"] == "95131"
    assert recover_cached_identity(p, "metalba") is p
    p["match_values"]["colata_certificato"] = "MANUAL"
    assert recover_cached_identity(p, "leichtmetall") is p


@pytest.mark.parametrize("text,expected", [("5.047",5047), ("5,047 KG",5047),
    ("3962",3962), ("1,5",1.5), ("5t",None), ("-1",None)])
def test_weight_units(text, expected):
    assert kg(text) == expected


@pytest.mark.parametrize("identity", ["95131.33", "95131.33`.35", "95131.95133.95135", "95131-33",
    "95131·33", "95131+33", "95131;33", "95131 und 95133", "95131.33333333"])
def test_local_parser_and_ai_sanitizer_never_take_first_member(identity):
    from app.modules.document_reader.matching import _extract_leichtmetall_charge_cast_no
    from app.modules.acquisition import service as s
    expected = cast_identity(identity).text
    assert _extract_leichtmetall_charge_cast_no(["Charge/ Cast No: " + identity]) == expected
    result = s._sanitize_leichtmetall_vision_certificate_fields({"charge_cast_no":identity}, "page1")
    assert result["colata_certificato"]["value"] == expected
    assert result["numero_certificato_certificato"]["value"] == expected


def test_real_second_delivery_95131_32():
    members = (DdtMember(10,"95131","2550","7175","144","325.1+2",True),
               DdtMember(11,"95132","2811","7175","144","325.1+2",True))
    result = coverage(members=members,target_id=11,certificate={**cert(), "cdq":"95131.32",
        "colata":"95131.32","peso":"5361","diametro":"144","ordine":"325.1+2"})
    assert result.valid


def test_same_cast_other_diameter_or_order_is_not_merged_into_group():
    extra = (replace(group()[0], row_id=3, diameter="144", weight="999"),
             replace(group()[1], row_id=4, order="OTHER", weight="888"))
    result = coverage(members=group()+extra, target_id=2, certificate=cert())
    assert result.valid and result.row_ids == (1,2)
    assert not coverage(members=group()+extra, target_id=3, certificate=cert()).valid


def test_no_individual_cast_claim_can_cover_a_group_or_total_twice():
    assert not coverage(members=group(), target_id=1, certificate={**cert(),
        "cdq":"95131", "colata":"95131"}).valid


def test_po_structure_not_just_concatenated_digits():
    assert coverage(members=group(),target_id=1,certificate={**cert(),"ordine":"332.2 + 3"}).valid
    assert coverage(members=group(),target_id=1,certificate={**cert(),"ordine":"332, 2 + 3"}).valid
    assert not coverage(members=group(),target_id=1,certificate={**cert(),"ordine":"332.23"}).valid
