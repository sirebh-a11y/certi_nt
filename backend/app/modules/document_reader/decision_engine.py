from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


DecisionState = Literal["rosso", "giallo", "verde", "accettato"]


@dataclass(frozen=True)
class ReaderDecisionRule:
    state: DecisionState
    description: str


@dataclass(frozen=True)
class ReaderFieldDecision:
    field_name: str
    state: DecisionState
    reason: str
    notes: tuple[str, ...] = field(default_factory=tuple)


def build_default_decision_rules() -> tuple[ReaderDecisionRule, ...]:
    return (
        ReaderDecisionRule(
            state="rosso",
            description="Lettura locale e double check non convergono, oppure il dato manca o non e robusto.",
        ),
        ReaderDecisionRule(
            state="giallo",
            description="Esiste una base utile ma resta una differenza, una debolezza o un solo lettore affidabile.",
        ),
        ReaderDecisionRule(
            state="verde",
            description="Lettura locale e double check convergono sullo stesso dato tecnico.",
        ),
        ReaderDecisionRule(
            state="accettato",
            description="Dato o riga verde confermati esplicitamente dall'utente quality.",
        ),
    )


def compare_reader_values(
    field_name: str,
    local_value: str | None,
    openai_value: str | None,
    *,
    user_confirmed: bool = False,
) -> ReaderFieldDecision:
    local_clean = _normalize_value(local_value)
    openai_clean = _normalize_value(openai_value)

    if user_confirmed and (local_clean or openai_clean):
        return ReaderFieldDecision(
            field_name=field_name,
            state="accettato",
            reason="Valore confermato dall'utente dopo verifica.",
        )

    if local_clean and openai_clean and local_clean == openai_clean:
        return ReaderFieldDecision(
            field_name=field_name,
            state="verde",
            reason="Lettura locale e double check convergono.",
        )

    if local_clean and openai_clean and local_clean != openai_clean:
        return ReaderFieldDecision(
            field_name=field_name,
            state="rosso",
            reason="Lettura locale e double check divergono.",
            notes=(f"locale={local_clean}", f"openai={openai_clean}"),
        )

    if local_clean or openai_clean:
        source = "locale" if local_clean else "openai"
        return ReaderFieldDecision(
            field_name=field_name,
            state="giallo",
            reason=f"Valore disponibile solo dal lettore {source}.",
        )

    return ReaderFieldDecision(
        field_name=field_name,
        state="rosso",
        reason="Valore assente in entrambe le letture.",
    )


def _normalize_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned.casefold() if cleaned else None
