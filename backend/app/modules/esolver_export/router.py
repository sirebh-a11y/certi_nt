import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import settings
from app.core.deps import DbSession
from app.modules.esolver_export.schemas import EsolverPdfCertificateExportResponse
from app.modules.esolver_export.service import list_esolver_pdf_certificates

router = APIRouter()
security = HTTPBasic()


def require_export_credentials(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    valid_user = secrets.compare_digest(credentials.username, settings.certi_export_username)
    valid_password = secrets.compare_digest(credentials.password, settings.certi_export_password)
    if not (valid_user and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali export non valide",
            headers={"WWW-Authenticate": "Basic"},
        )


@router.get("/certificati-pdf", response_model=EsolverPdfCertificateExportResponse)
def list_certificati_pdf_export_route(
    request: Request,
    db: DbSession,
    _: None = Depends(require_export_credentials),
) -> EsolverPdfCertificateExportResponse:
    public_base_url = settings.certi_public_base_url.strip() or str(request.base_url).rstrip("/")
    return list_esolver_pdf_certificates(db, public_base_url=public_base_url)
