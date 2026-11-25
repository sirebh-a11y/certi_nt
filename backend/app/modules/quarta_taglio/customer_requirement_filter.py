"""Presence of the existing customer-requirements badge, never certification state."""
import re

from app.modules.customer_requirements.models import CustomerRequirement


def _family_key(code: str | None) -> str | None:
    digits = re.sub(r'[^0-9]', '', code or '')
    return digits[:-2] if len(digits) > 2 else None


def active_families(db) -> set[str]:
    codes = db.query(CustomerRequirement.cod_f3).filter(CustomerRequirement.active.is_(True)).all()
    # Same ASCII-digit normalization and leading-zero preservation as the JS
    # resolver. For presence, exact priority and family fallback have the same
    # boolean result; ambiguity remains the dialog's responsibility.
    return {family for (code,) in codes if (family := _family_key(code)) is not None}


def ddt_requirement_presence(item, families: set[str]) -> bool | None:
    # Match the DDT badge on this row's single F3. No identification is not a
    # confirmation that there are no requirements.
    if not (item.cod_odp or '').strip():
        return None
    family = _family_key(item.cod_f3)
    return family in families if family is not None else None


def has_requirements(articles, families: set[str]) -> bool:
    for article in articles:
        code = str(article.cod_f3 or '').strip()
        # Article lists must not contain joined display summaries or material
        # codes. Match the frontend OL resolver, not just a customer's name.
        if re.fullmatch(r'[0-9]{3,}', code) and code[:-2] in families:
            return True
    return False
