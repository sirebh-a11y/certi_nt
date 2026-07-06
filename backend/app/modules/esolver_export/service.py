from sqlalchemy.orm import Session

from app.modules.esolver_export.schemas import EsolverPdfCertificateExportItem, EsolverPdfCertificateExportResponse
from app.modules.quarta_taglio.models import QuartaTaglioFinalCertificate


def list_esolver_pdf_certificates(db: Session, *, public_base_url: str) -> EsolverPdfCertificateExportResponse:
    base_url = public_base_url.rstrip("/")
    certificates = (
        db.query(QuartaTaglioFinalCertificate)
        .filter(
            QuartaTaglioFinalCertificate.status == "pdf_final",
            QuartaTaglioFinalCertificate.storage_key_pdf.isnot(None),
            QuartaTaglioFinalCertificate.download_token.isnot(None),
            QuartaTaglioFinalCertificate.cod_f3.isnot(None),
            QuartaTaglioFinalCertificate.ddt.isnot(None),
            QuartaTaglioFinalCertificate.cert_date.isnot(None),
        )
        .order_by(QuartaTaglioFinalCertificate.updated_at.desc(), QuartaTaglioFinalCertificate.id.desc())
        .all()
    )

    items = [
        EsolverPdfCertificateExportItem(
            id_certi=certificate.id,
            ol=certificate.cod_odp,
            ddt=certificate.ddt or "",
            id_documento=certificate.esolver_id_documento,
            id_riga_doc=certificate.esolver_id_riga_doc,
            rif_lotto_alfanum=certificate.esolver_rif_lotto_alfanum,
            cod_f3=certificate.cod_f3 or "",
            numero_certificato=certificate.certificate_number or certificate.draft_number,
            data_certificato=certificate.cert_date,
            quantita=certificate.quantita,
            pdf_url=(
                f"{base_url}/api/quarta-taglio/certificates/{certificate.id}/pdf-file"
                f"?download_token={certificate.download_token}"
            ),
            stato="PDF_CHIUSO",
            updated_at=certificate.updated_at,
        )
        for certificate in certificates
        if certificate.cert_date is not None and certificate.download_token
    ]
    return EsolverPdfCertificateExportResponse(items=items, total_items=len(items))


def esolver_pdf_export_fields() -> list[str]:
    return [
        "OL",
        "DDT",
        "IdDocumento",
        "IdRigaDoc",
        "RifLottoAlfanum",
        "CodF3",
        "NumeroCertificato",
        "DataCertificato",
        "Quantita",
        "PdfUrl",
        "Stato",
        "UpdatedAt",
    ]
