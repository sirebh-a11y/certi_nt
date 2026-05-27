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
            cod_f3=certificate.cod_f3 or "",
            numero_certificato=certificate.certificate_number or certificate.draft_number,
            data_certificato=certificate.cert_date,
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
        "CodF3",
        "NumeroCertificato",
        "DataCertificato",
        "PdfUrl",
        "Stato",
        "UpdatedAt",
    ]
