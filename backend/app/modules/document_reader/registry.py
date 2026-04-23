from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SupplierReaderTemplate:
    supplier_key: str
    display_name: str
    ddt_template_id: str
    certificate_template_id: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    openai_double_check_blocks: tuple[str, ...] = field(default_factory=tuple)
    strong_match_fields: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


TEMPLATE_REGISTRY: tuple[SupplierReaderTemplate, ...] = (
    SupplierReaderTemplate(
        supplier_key="aluminium_bozen",
        display_name="Aluminium Bozen S.r.l.",
        ddt_template_id="aluminium_bozen_delivery_note_packing_list_v1",
        certificate_template_id="aluminium_bozen_certificate_v1",
        aliases=("aluminium bz", "aluminium bozen", "bozen"),
        openai_double_check_blocks=("ddt_core", "match", "chemistry", "properties", "notes"),
        strong_match_fields=("cert_no", "article", "profile_code", "alloy", "cast", "customer_order"),
        notes=("Packing list centrale per cert no e cast.",),
    ),
    SupplierReaderTemplate(
        supplier_key="leichtmetall",
        display_name="Leichtmetall Aluminium Giesserei Hannover GmbH",
        ddt_template_id="leichtmetall_delivery_note_scan_v1",
        certificate_template_id="leichtmetall_certificate_v1",
        aliases=("leichtmetall", "hannover"),
        openai_double_check_blocks=("ddt_core", "match", "chemistry", "notes"),
        strong_match_fields=("po_no", "charge_cast_no", "alloy", "diameter", "weight"),
        notes=("Chimica forte su riga Ist/act.; proprieta non sempre osservate come tabella misurata.",),
    ),
    SupplierReaderTemplate(
        supplier_key="impol",
        display_name="Impol",
        ddt_template_id="impol_packing_list_multirow_v1",
        certificate_template_id="impol_certificate_multirow_v1",
        aliases=("impol",),
        openai_double_check_blocks=("match", "chemistry", "properties", "notes"),
        strong_match_fields=("customer_order_no", "alloy", "diameter", "charge", "weight"),
        notes=("Packing list identifica il DDT; il match riga si chiude su ordine, lega, diametro, charge e peso netto.",),
    ),
    SupplierReaderTemplate(
        supplier_key="arconic_hannover",
        display_name="Arconic Hannover",
        ddt_template_id="arconic_hannover_delivery_note_v1",
        certificate_template_id="arconic_hannover_certificate_v1",
        aliases=("arconic", "alcoa hannover", "hannover"),
        openai_double_check_blocks=("ddt_core", "match", "chemistry", "properties", "notes"),
        strong_match_fields=("delivery_note", "sales_order", "customer_po", "customer_item", "cast_job"),
        notes=("Un DDT puo mappare a piu certificati su righe diverse.",),
    ),
    SupplierReaderTemplate(
        supplier_key="neuman",
        display_name="Neuman",
        ddt_template_id="neuman_delivery_note_lot_based_v1",
        certificate_template_id="neuman_inspection_certificate_round_bars_v1",
        aliases=("neuman", "neumann"),
        openai_double_check_blocks=("ddt_core", "match", "chemistry", "properties", "notes"),
        strong_match_fields=("lot", "customer_material", "alloy", "diameter", "weight"),
        notes=(
            "Match forte su lotto, materiale cliente, lega, diametro e peso.",
            "Delivery Note identifica il DDT ma non chiude da solo il match.",
        ),
    ),
    SupplierReaderTemplate(
        supplier_key="metalba",
        display_name="Metalba Aluminium S.p.A.",
        ddt_template_id="metalba_ddt_round_bar_v1",
        certificate_template_id="metalba_test_certificate_v1",
        aliases=("metalba",),
        openai_double_check_blocks=("ddt_core", "match", "chemistry", "properties", "notes"),
        strong_match_fields=("vs_rif", "alloy", "diameter", "weight"),
        notes=("Il ponte forte e stampato: Vs. Rif. ↔ Ordine Cliente. Rif. Ord. / Commessa restano campi di supporto.",),
    ),
    SupplierReaderTemplate(
        supplier_key="zalco",
        display_name="Zeeland Aluminium Company",
        ddt_template_id="zalco_tally_sheet_v1",
        certificate_template_id="zalco_certificate_v1",
        aliases=("zalco", "zeeland"),
        openai_double_check_blocks=("ddt_core", "match", "chemistry", "notes"),
        strong_match_fields=("tally_no", "cast", "symbol", "code_art", "diameter"),
        notes=("Prima capire qual e la pagina utile: tally/packing list.",),
    ),
    SupplierReaderTemplate(
        supplier_key="grupa_kety",
        display_name="Grupa Kety",
        ddt_template_id="grupa_kety_packing_list_v1",
        certificate_template_id="grupa_kety_certificate_v1",
        aliases=("grupa kety", "kety"),
        openai_double_check_blocks=("match", "chemistry", "properties", "notes"),
        strong_match_fields=("delivery_note", "lot", "order", "heat", "alloy"),
        notes=("Piu certificati possibili sullo stesso DDT tramite lotto.",),
    ),
    SupplierReaderTemplate(
        supplier_key="aww",
        display_name="Aluminium-Werke Wutoschingen AG & Co. KG",
        ddt_template_id="aww_delivery_note_extruded_bars_v1",
        certificate_template_id="aww_inspection_certificate_extruded_bars_v1",
        aliases=("aww", "wutoschingen", "wutöschingen", "aluminium-werke"),
        openai_double_check_blocks=("match", "chemistry", "properties", "notes"),
        strong_match_fields=("your_part_number", "part_number", "order_confirmation_root"),
        notes=("Alcuni match contemporanei forti, altre famiglie ancora solo coerenti per template.",),
    ),
)


def resolve_supplier_template(*candidate_names: str | None) -> SupplierReaderTemplate | None:
    normalized_candidates = [normalize_supplier_name(name) for name in candidate_names if normalize_supplier_name(name)]
    for candidate in normalized_candidates:
        for template in TEMPLATE_REGISTRY:
            pool = (template.display_name, template.supplier_key, *template.aliases)
            if any(normalize_supplier_name(entry) in candidate or candidate in normalize_supplier_name(entry) for entry in pool):
                return template
    return None


def normalize_supplier_name(value: str | None) -> str:
    if value is None:
        return ""
    normalized = value.casefold()
    replacements = {
        "à": "a",
        "á": "a",
        "â": "a",
        "ä": "a",
        "å": "a",
        "ç": "c",
        "è": "e",
        "é": "e",
        "ê": "e",
        "ë": "e",
        "ì": "i",
        "í": "i",
        "î": "i",
        "ï": "i",
        "ñ": "n",
        "ò": "o",
        "ó": "o",
        "ô": "o",
        "ö": "o",
        "ù": "u",
        "ú": "u",
        "û": "u",
        "ü": "u",
        "ß": "ss",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return " ".join(normalized.replace("-", " ").replace("/", " ").split())
