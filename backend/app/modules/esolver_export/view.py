from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


ESOLVER_EXPORT_SCHEMA = "esolver_export"
ESOLVER_EXPORT_VIEW = "certi_certificati_pdf"
ESOLVER_EXPORT_QUALIFIED_VIEW = f"{ESOLVER_EXPORT_SCHEMA}.{ESOLVER_EXPORT_VIEW}"


def ensure_esolver_export_view(engine: Engine, *, public_base_url: str) -> None:
    """Create the canonical read-only PostgreSQL view consumed by eSolver."""
    if engine.dialect.name != "postgresql":
        return

    inspector = inspect(engine)
    required_tables = {
        "quarta_taglio_final_certificates",
        "quarta_taglio_certificate_pdf_versions",
    }
    if not all(inspector.has_table(table_name) for table_name in required_tables):
        return

    base_url = public_base_url.strip().rstrip("/")
    with engine.begin() as connection:
        quoted_base_url = connection.execute(
            text("SELECT quote_literal(:base_url)"),
            {"base_url": base_url},
        ).scalar_one()
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {ESOLVER_EXPORT_SCHEMA}"))
        connection.execute(
            text(
                f"""
                CREATE OR REPLACE VIEW {ESOLVER_EXPORT_QUALIFIED_VIEW} AS
                SELECT
                    certificate.id AS "IdCerti",
                    certificate.cod_odp AS "OL",
                    certificate.ddt AS "DDT",
                    certificate.esolver_id_documento AS "IdDocumento",
                    certificate.esolver_id_riga_doc AS "IdRigaDoc",
                    certificate.esolver_rif_lotto_alfanum AS "RifLottoAlfanum",
                    certificate.cod_f3 AS "CodF3",
                    certificate.certificate_number AS "NumeroCertificato",
                    certificate.cert_date AS "DataCertificato",
                    certificate.quantita AS "Quantita",
                    {quoted_base_url}
                        || '/api/quarta-taglio/certificates/'
                        || certificate.id::text
                        || '/pdf-file?download_token='
                        || certificate.download_token AS "PdfUrl",
                    'PDF_CHIUSO'::text AS "Stato",
                    certificate.updated_at AS "UpdatedAt",
                    active_version.version AS "PdfVersion",
                    certificate.closed_at AS "ClosedAt"
                FROM quarta_taglio_final_certificates AS certificate
                JOIN LATERAL (
                    SELECT pdf_version.version
                    FROM quarta_taglio_certificate_pdf_versions AS pdf_version
                    WHERE pdf_version.certificate_id = certificate.id
                      AND pdf_version.status = 'active'
                      AND btrim(pdf_version.storage_key_pdf) <> ''
                    ORDER BY pdf_version.version DESC, pdf_version.id DESC
                    LIMIT 1
                ) AS active_version ON TRUE
                WHERE certificate.status = 'pdf_final'
                  AND certificate.storage_key_pdf IS NOT NULL
                  AND btrim(certificate.storage_key_pdf) <> ''
                  AND certificate.download_token IS NOT NULL
                  AND btrim(certificate.download_token) <> ''
                  AND certificate.cod_f3 IS NOT NULL
                  AND btrim(certificate.cod_f3) <> ''
                  AND certificate.ddt IS NOT NULL
                  AND btrim(certificate.ddt) <> ''
                  AND certificate.certificate_number IS NOT NULL
                  AND btrim(certificate.certificate_number) <> ''
                  AND certificate.cert_date IS NOT NULL
                  AND certificate.closed_at IS NOT NULL
                  AND certificate.esolver_id_documento IS NOT NULL
                  AND btrim(certificate.esolver_id_documento) <> ''
                  AND certificate.esolver_id_riga_doc IS NOT NULL
                  AND btrim(certificate.esolver_id_riga_doc) <> ''
                """
            )
        )
