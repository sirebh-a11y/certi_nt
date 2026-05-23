from pydantic import BaseModel


class EsolverClientResponse(BaseModel):
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


class EsolverClientListResponse(BaseModel):
    items: list[EsolverClientResponse]

