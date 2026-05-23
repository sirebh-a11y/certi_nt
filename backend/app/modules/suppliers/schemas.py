from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validation import normalize_and_validate_email


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class SupplierAliasBase(BaseModel):
    nome_alias: str = Field(min_length=1, max_length=255)
    fonte: str | None = Field(default=None, max_length=100)
    attivo: bool = True

    @field_validator("nome_alias")
    @classmethod
    def validate_alias(cls, value: str) -> str:
        return value.strip()

    @field_validator("fonte")
    @classmethod
    def normalize_fonte(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class SupplierAliasCreateRequest(SupplierAliasBase):
    pass


class SupplierAliasUpdateRequest(SupplierAliasBase):
    pass


class SupplierAliasResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome_alias: str
    fonte: str | None
    attivo: bool


class SupplierEsolverLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cod_clifor: str
    ragione_sociale_esolver: str | None
    cod_alternativo2: str | None
    partita_iva_esolver: str | None
    codice_fiscale_esolver: str | None
    indirizzo_esolver: str | None
    cap_esolver: str | None
    citta_esolver: str | None
    provincia_esolver: str | None
    nazione_esolver: str | None
    email_esolver: str | None
    telefono_esolver: str | None
    stato_link: str
    last_sync_at: datetime | None = None


class SupplierBase(BaseModel):
    ragione_sociale: str = Field(min_length=1, max_length=255)
    partita_iva: str | None = Field(default=None, max_length=64)
    codice_fiscale: str | None = Field(default=None, max_length=64)
    indirizzo: str | None = Field(default=None, max_length=255)
    cap: str | None = Field(default=None, max_length=32)
    citta: str | None = Field(default=None, max_length=128)
    provincia: str | None = Field(default=None, max_length=64)
    nazione: str | None = Field(default=None, max_length=128)
    email: str | None = None
    telefono: str | None = Field(default=None, max_length=128)
    reader_template_key: str | None = Field(default=None, max_length=64)
    attivo: bool = True
    note: str | None = None

    @field_validator(
        "partita_iva",
        "codice_fiscale",
        "indirizzo",
        "cap",
        "citta",
        "provincia",
        "nazione",
        "telefono",
        "reader_template_key",
        "note",
    )
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_and_validate_email(value)

    @field_validator("ragione_sociale")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return value.strip()


class SupplierUpdateRequest(SupplierBase):
    pass


class SupplierActiveRequest(BaseModel):
    attivo: bool


class SupplierListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ragione_sociale: str
    citta: str | None
    nazione: str | None
    email: str | None
    telefono: str | None
    reader_template_key: str | None
    attivo: bool
    alias_count: int
    esolver_cod_clifor: str | None = None
    esolver_name: str | None = None
    esolver_status: str | None = None


class SupplierListResponse(BaseModel):
    items: list[SupplierListItemResponse]


class SupplierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ragione_sociale: str
    partita_iva: str | None
    codice_fiscale: str | None
    indirizzo: str | None
    cap: str | None
    citta: str | None
    provincia: str | None
    nazione: str | None
    email: str | None
    telefono: str | None
    reader_template_key: str | None
    attivo: bool
    note: str | None
    aliases: list[SupplierAliasResponse]
    esolver_link: SupplierEsolverLinkResponse | None = None


class SupplierActionResponse(BaseModel):
    message: str


class EsolverSupplierResponse(BaseModel):
    cod_clifor: str
    ragione_sociale: str
    partita_iva: str | None = None
    codice_fiscale: str | None = None
    indirizzo: str | None = None
    cap: str | None = None
    citta: str | None = None
    provincia: str | None = None
    nazione: str | None = None
    email: str | None = None
    telefono: str | None = None
    cod_alternativo2: str | None = None
    in_app: bool = False
    app_supplier_id: int | None = None


class EsolverSupplierListResponse(BaseModel):
    items: list[EsolverSupplierResponse]


class SupplierImportFromEsolverRequest(BaseModel):
    cod_clifor: str = Field(min_length=1, max_length=64)


class SupplierEsolverSyncResponse(BaseModel):
    updated: int
    unchanged: int
    missing: list[str] = Field(default_factory=list)
