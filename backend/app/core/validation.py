import re


EMAIL_PATTERN = re.compile(r"^[^@\s]+@(?:localhost|(?:[^.@\s]+\.)+[^.@\s]+)$")

EMAIL_ERROR_MESSAGE = "Inserisci un'email valida, ad esempio nome@azienda.it"


def normalize_and_validate_email(value: str) -> str:
    normalized = value.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError(EMAIL_ERROR_MESSAGE)
    return normalized
