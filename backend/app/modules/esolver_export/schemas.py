from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EsolverPdfCertificateExportItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id_certi: int = Field(alias="IdCerti")
    ol: str = Field(alias="OL")
    ddt: str = Field(alias="DDT")
    cod_f3: str = Field(alias="CodF3")
    numero_certificato: str = Field(alias="NumeroCertificato")
    data_certificato: datetime = Field(alias="DataCertificato")
    pdf_url: str = Field(alias="PdfUrl")
    stato: str = Field(alias="Stato")
    updated_at: datetime = Field(alias="UpdatedAt")


class EsolverPdfCertificateExportResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[EsolverPdfCertificateExportItem] = Field(alias="Items")
    total_items: int = Field(alias="TotalItems")
