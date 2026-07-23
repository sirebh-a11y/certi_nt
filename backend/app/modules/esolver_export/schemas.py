from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EsolverPdfCertificateExportItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id_certi: int = Field(alias="IdCerti")
    ol: str = Field(alias="OL")
    ddt: str = Field(alias="DDT")
    id_documento: str | None = Field(default=None, alias="IdDocumento")
    id_riga_doc: str | None = Field(default=None, alias="IdRigaDoc")
    rif_lotto_alfanum: str | None = Field(default=None, alias="RifLottoAlfanum")
    cod_f3: str = Field(alias="CodF3")
    numero_certificato: str = Field(alias="NumeroCertificato")
    data_certificato: datetime = Field(alias="DataCertificato")
    quantita: float | None = Field(default=None, alias="Quantita")
    pdf_url: str = Field(alias="PdfUrl")
    stato: str = Field(alias="Stato")
    updated_at: datetime = Field(alias="UpdatedAt")
    pdf_version: int = Field(alias="PdfVersion")
    closed_at: datetime = Field(alias="ClosedAt")


class EsolverPdfCertificateExportResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[EsolverPdfCertificateExportItem] = Field(alias="Items")
    total_items: int = Field(alias="TotalItems")
