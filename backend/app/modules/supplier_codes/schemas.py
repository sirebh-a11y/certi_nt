import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CODE_PATTERN = re.compile(r"^[A-Za-z]{2,8}$")


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class SupplierInstallationCodePayload(BaseModel):
    codice: str = Field(min_length=2, max_length=8)
    fornitore_id: int | None = None
    esolver_cod_clifor: str | None = Field(default=None, max_length=64)
    esolver_ragione_sociale: str | None = Field(default=None, max_length=255)
    etichetta_manuale: str | None = Field(default=None, max_length=255)

    @field_validator("codice")
    @classmethod
    def validate_codice(cls, value: str) -> str:
        cleaned = value.strip()
        if not CODE_PATTERN.fullmatch(cleaned):
            raise ValueError("Il codice deve contenere solo lettere, da 2 a 8 caratteri, rispettando maiuscole e minuscole")
        return cleaned

    @field_validator("esolver_cod_clifor", "esolver_ragione_sociale", "etichetta_manuale")
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_target(self) -> "SupplierInstallationCodePayload":
        if self.fornitore_id is None and self.esolver_cod_clifor is None and self.etichetta_manuale is None:
            raise ValueError("Scegli un fornitore locale, un fornitore eSolver o inserisci un'etichetta manuale")
        return self


class SupplierInstallationCodeCreateRequest(SupplierInstallationCodePayload):
    pass


class SupplierInstallationCodeUpdateRequest(SupplierInstallationCodePayload):
    pass


class SupplierInstallationCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codice: str
    fornitore_id: int | None
    ragione_sociale_fornitore: str | None
    esolver_cod_clifor: str | None
    esolver_ragione_sociale: str | None
    etichetta_manuale: str | None
    nome_visualizzato: str
    tipo_collegamento: str


class SupplierInstallationCodeListResponse(BaseModel):
    items: list[SupplierInstallationCodeResponse]
