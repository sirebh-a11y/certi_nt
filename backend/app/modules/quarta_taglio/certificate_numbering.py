"""Certificate numbering policy; assigned numbers and F3 identities stay intact."""
import re


def f3_digits(value: str | None) -> str:
    return re.sub(r"\D", "", str(value or "").strip())


def workmanship_suffix(value: str | None) -> str:
    digits = f3_digits(value)
    if len(digits) == 7:
        return "00"
    return digits[-2:].zfill(2) if digits else "00"


def comparable_base(base: str, cod_f3: str | None) -> str:
    """Equate only the known old seven-digit suffix and its new 00 spelling.

    Callers still scope by exact OL/F3 and material. No arbitrary number repair,
    legacy hash change or equivalence between different workmanships is allowed.
    """
    digits = f3_digits(cod_f3)
    match = re.fullmatch(r"(\d+_\d+)_(\d+)(/\d{2})", base)
    # Older formats may pad that same suffix with an extra leading zero.
    if len(digits) == 7 and match and int(match[2]) in {int(digits[-2:]), 0}:
        return f"{match[1]}_00{match[3]}"
    return base


def new_shipment_base(base: str, cod_f3: str | None) -> str:
    result = comparable_base(base, cod_f3)
    match = re.fullmatch(r"\d+_\d+_(\d+)/\d{2}", result)
    if len(f3_digits(cod_f3)) == 7 and (not match or match[1] != "00"):
        raise ValueError("unexpected_seven_digit_number_base")
    return result
