from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.integrations.models import ExternalConnection
from app.core.security.crypto import decrypt_secret
from app.modules.clients.schemas import EsolverClientListResponse, EsolverClientResponse


def list_esolver_clients(db: Session, search: str | None = None, limit: int = 100, offset: int = 0) -> EsolverClientListResponse:
    rows, total, safe_limit, safe_offset = _fetch_esolver_client_rows(db, search=search, limit=limit, offset=offset)
    return EsolverClientListResponse(
        items=[EsolverClientResponse(**row) for row in rows],
        total=total,
        limit=safe_limit,
        offset=safe_offset,
    )


def _fetch_esolver_client_rows(
    db: Session,
    *,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, str | None]], int, int, int]:
    safe_limit = max(1, min(limit, 20000))
    safe_offset = max(0, offset)
    connection = db.query(ExternalConnection).filter(ExternalConnection.code == "esolver").one_or_none()
    if connection is None or not connection.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connessione eSolver non configurata o disabilitata")
    if not connection.password_encrypted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password eSolver non configurata")

    try:
        import pymssql
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Driver SQL Server pymssql non installato") from exc

    schema_name = _sql_identifier(connection.schema_name or "dbo")
    object_settings = connection.object_settings or {}
    view_name = _sql_identifier(str(object_settings.get("anagrafiche_view") or "CertiCliForF3"))
    if schema_name is None or view_name is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome vista eSolver non valido")

    where = ["TipoAnagrafica = 1"]
    params: list[Any] = []
    if search:
        like = f"%{search.strip()}%"
        where.append("(RagSoc1 LIKE %s OR RagSoc2 LIKE %s OR CodCliFor LIKE %s OR PartitaIva LIKE %s OR CodAlternativo2 LIKE %s)")
        params.extend([like, like, like, like, like])

    where_sql = " AND ".join(where)
    count_query = f"SELECT COUNT(*) AS TotalRows FROM [{schema_name}].[{view_name}] WHERE {where_sql}"
    query = (
        f"SELECT CodCliFor, RagSoc1, RagSoc2, Indirizzo, Indirizzo2, Localita, "
        f"Localita2, Provincia, Cap, CodStato, IndirEmail, NumTel, NumTel2, CodFiscale, PartitaIva, CodAlternativo2 "
        f"FROM [{schema_name}].[{view_name}] "
        f"WHERE {where_sql} "
        f"ORDER BY RagSoc1 ASC, CodCliFor ASC "
        f"OFFSET %s ROWS FETCH NEXT %s ROWS ONLY"
    )
    password = decrypt_secret(connection.password_encrypted)
    with pymssql.connect(
        server=connection.server_host,
        port=connection.port,
        user=connection.username,
        password=password,
        database=connection.database_name,
        login_timeout=connection.connection_timeout,
        timeout=connection.query_timeout,
        as_dict=True,
    ) as sql_connection:
        with sql_connection.cursor() as cursor:
            cursor.execute(count_query, tuple(params))
            total_row = cursor.fetchone() or {}
            total = int(total_row.get("TotalRows") or 0)
            cursor.execute(query, tuple([*params, safe_offset, safe_limit]))
            return [_serialize_esolver_client_row(row) for row in cursor.fetchall()], total, safe_limit, safe_offset


def _serialize_esolver_client_row(row: dict[str, Any]) -> dict[str, str | None]:
    name_parts = [_clean_value(row.get("RagSoc1")), _clean_value(row.get("RagSoc2"))]
    address_parts = [_clean_value(row.get("Indirizzo")), _clean_value(row.get("Indirizzo2"))]
    city_parts = [_clean_value(row.get("Localita")), _clean_value(row.get("Localita2"))]
    return {
        "cod_clifor": str(row.get("CodCliFor") or "").strip(),
        "ragione_sociale": " ".join(part for part in name_parts if part),
        "partita_iva": _clean_value(row.get("PartitaIva")),
        "codice_fiscale": _clean_value(row.get("CodFiscale")),
        "indirizzo": " ".join(part for part in address_parts if part) or None,
        "cap": _clean_value(row.get("Cap")),
        "citta": " ".join(part for part in city_parts if part) or None,
        "provincia": _clean_value(row.get("Provincia")),
        "nazione": _clean_value(row.get("CodStato")),
        "email": _clean_value(row.get("IndirEmail")),
        "telefono": _clean_value(row.get("NumTel")) or _clean_value(row.get("NumTel2")),
        "cod_alternativo2": _clean_value(row.get("CodAlternativo2")),
    }


def _sql_identifier(value: str | None) -> str | None:
    cleaned = _clean_value(value)
    if cleaned is None:
        return None
    if not cleaned.replace("_", "").isalnum():
        return None
    return cleaned


def _clean_value(value: object | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
