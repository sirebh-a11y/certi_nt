"""Interpret Metalba's explicit material specification without changing source identity."""
import re


DERIVED_METHOD = "metalba_lst03"


def lst03_material_quote(text: str | None) -> str | None:
    """Only an affirmative material requirement, never a loose LST substring."""
    normalized = re.sub(r"\s+", " ", text or "").strip()
    # Other material specifications require review. LST00 may coexist with LST03.
    if any(code not in {"00", "03"} for code in re.findall(r"\bLST\s*[-.]?\s*(\d+)", normalized, re.I)):
        return None
    pattern = (
        r"\bMATERIALE\s+SECONDO\s+(?:LA\s+)?SPECIFICA\s+"
        r"LST\s*[-.]?\s*03(?:\s*[-.]?\s*A)?"
        r"(?![A-Z0-9]|\s*[-./]\s*[A-Z0-9]|\s+[A-Z]\b)\b"
    )
    for segment in normalized.split("|"):
        if re.search(r"\b(?:NON|NOT|DEROGA|ECCEZIONE|ESCLUS\w*)\b", segment, re.I):
            continue
        match = re.search(pattern, segment, re.I)
        if match:
            return match.group(0)
    return None


def eligible_alloy(value: str | None) -> bool:
    # F attached to 6082 is present on the real Metalba documents; L is a
    # different variant and must never be swallowed by a family comparison.
    return bool(re.fullmatch(r"6082(?:F|H)?(?:\s+(?:F|T\d+))?", (value or "").strip(), re.I))


def interpreted_alloy(value: str) -> str:
    temper = re.search(r"\s+(F|T\d+)\s*$", value, re.I)
    return "6082H" + (f" {temper.group(1).upper()}" if temper else "")


def same_interpreted_display(left: str | None, right: str | None) -> bool:
    original, submitted = ((v or "").strip().upper() for v in (left, right))
    return bool(re.fullmatch(r"6082H(?:\s+(?:F|T\d+))?", original)
                and submitted in {original, "6082H"})
