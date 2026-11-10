"""Presence of the existing customer-requirements badge, never certification state."""
import re

from app.modules.customer_requirements.models import CustomerRequirement


def active_families(db) -> set[str]:
    codes = db.query(CustomerRequirement.cod_f3).filter(CustomerRequirement.active.is_(True)).all()
    # Same ASCII-digit normalization and leading-zero preservation as the JS
    # resolver. For presence, exact priority and family fallback have the same
    # boolean result; ambiguity remains the dialog's responsibility.
    result = set()
    for (code,) in codes:
        digits = re.sub(r'[^0-9]', '', code or '')
        if len(digits) > 2:
            result.add(digits[:-2])
    return result


def has_requirements(articles, families: set[str]) -> bool:
    for article in articles:
        code = str(article.cod_f3 or '').strip()
        # Article lists must not contain joined display summaries or material
        # codes. Match the frontend OL resolver, not just a customer's name.
        if re.fullmatch(r'[0-9]{3,}', code) and code[:-2] in families:
            return True
    return False
