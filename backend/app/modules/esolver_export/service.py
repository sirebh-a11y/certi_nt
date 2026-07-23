from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.esolver_export.schemas import EsolverPdfCertificateExportItem, EsolverPdfCertificateExportResponse
from app.modules.esolver_export.view import ESOLVER_EXPORT_QUALIFIED_VIEW
from app.modules.quarta_taglio.models import QuartaTaglioCertificatePdfVersion, QuartaTaglioFinalCertificate


def list_esolver_pdf_certificates(db: Session, *, public_base_url: str) -> EsolverPdfCertificateExportResponse:
    if db.get_bind().dialect.name == "postgresql":
        return _list_esolver_pdf_certificates_from_view(db)
    return _list_esolver_pdf_certificates_from_models(db, public_base_url=public_base_url)


def _list_esolver_pdf_certificates_from_view(db: Session) -> EsolverPdfCertificateExportResponse:
    rows = db.execute(
        text(
            f"""
            SELECT *
            FROM {ESOLVER_EXPORT_QUALIFIED_VIEW}
            ORDER BY "UpdatedAt" DESC, "IdCerti" DESC
            """
        )
    ).mappings().all()
    items = [EsolverPdfCertificateExportItem.model_validate(dict(row)) for row in rows]
    return EsolverPdfCertificateExportResponse(items=items, total_items=len(items))


def _list_esolver_pdf_certificates_from_models(
    db: Session,
    *,
    public_base_url: str,
) -> EsolverPdfCertificateExportResponse:
    base_url = public_base_url.rstrip("/")
    rows = (
        db.query(QuartaTaglioFinalCertificate, QuartaTaglioCertificatePdfVersion)
        .join(
            QuartaTaglioCertificatePdfVersion,
            QuartaTaglioCertificatePdfVersion.certificate_id == QuartaTaglioFinalCertificate.id,
        )
        .filter(
            QuartaTaglioFinalCertificate.status == "pdf_final",
            QuartaTaglioFinalCertificate.storage_key_pdf.isnot(None),
            QuartaTaglioFinalCertificate.download_token.isnot(None),
            QuartaTaglioFinalCertificate.cod_f3.isnot(None),
            QuartaTaglioFinalCertificate.ddt.isnot(None),
            QuartaTaglioFinalCertificate.certificate_number.isnot(None),
            QuartaTaglioFinalCertificate.cert_date.isnot(None),
            QuartaTaglioFinalCertificate.closed_at.isnot(None),
            QuartaTaglioFinalCertificate.esolver_id_documento.isnot(None),
            QuartaTaglioFinalCertificate.esolver_id_riga_doc.isnot(None),
            QuartaTaglioCertificatePdfVersion.status == "active",
        )
        .order_by(
            QuartaTaglioFinalCertificate.updated_at.desc(),
            QuartaTaglioFinalCertificate.id.desc(),
            QuartaTaglioCertificatePdfVersion.version.desc(),
        )
        .all()
    )

    items: list[EsolverPdfCertificateExportItem] = []
    seen_certificate_ids: set[int] = set()
    for certificate, pdf_version in rows:
        if certificate.id in seen_certificate_ids:
            continue
        values_are_valid = all(
            (
                certificate.storage_key_pdf and certificate.storage_key_pdf.strip(),
                certificate.download_token and certificate.download_token.strip(),
                certificate.cod_f3 and certificate.cod_f3.strip(),
                certificate.ddt and certificate.ddt.strip(),
                certificate.certificate_number and certificate.certificate_number.strip(),
                certificate.esolver_id_documento and certificate.esolver_id_documento.strip(),
                certificate.esolver_id_riga_doc and certificate.esolver_id_riga_doc.strip(),
                pdf_version.storage_key_pdf and pdf_version.storage_key_pdf.strip(),
            )
        )
        if not values_are_valid or certificate.cert_date is None or certificate.closed_at is None:
            continue
        seen_certificate_ids.add(certificate.id)
        items.append(
            EsolverPdfCertificateExportItem(
                id_certi=certificate.id,
                ol=certificate.cod_odp,
                ddt=certificate.ddt or "",
                id_documento=certificate.esolver_id_documento,
                id_riga_doc=certificate.esolver_id_riga_doc,
                rif_lotto_alfanum=certificate.esolver_rif_lotto_alfanum,
                cod_f3=certificate.cod_f3 or "",
                numero_certificato=certificate.certificate_number or "",
                data_certificato=certificate.cert_date,
                quantita=certificate.quantita,
                pdf_url=(
                    f"{base_url}/api/quarta-taglio/certificates/{certificate.id}/pdf-file"
                    f"?download_token={certificate.download_token}"
                ),
                stato="PDF_CHIUSO",
                updated_at=certificate.updated_at,
                pdf_version=pdf_version.version,
                closed_at=certificate.closed_at,
            )
        )
    return EsolverPdfCertificateExportResponse(items=items, total_items=len(items))


def esolver_pdf_export_fields() -> list[str]:
    return [
        "IdCerti",
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
        "PdfVersion",
        "ClosedAt",
    ]
