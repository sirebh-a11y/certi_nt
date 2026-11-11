"""Small authenticated polls; response data is never shared between users."""
import hashlib
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.deps import CurrentUser, DbSession
from app.core.integrations.background import _TOKEN, _actor_snapshot, manager, ticket
from app.core.integrations.models import IntegrationBackgroundJob as Job
from app.core.security.crypto import decrypt_secret

router = APIRouter()


def owned_job(db, job_id, actor):
    if not _TOKEN.fullmatch(job_id):
        raise HTTPException(404, "Operazione non trovata")
    job = db.get(Job, job_id)
    if job is None or job.actor_id != actor.id:
        raise HTTPException(404, "Operazione non trovata")
    if _actor_snapshot(actor) != job.actor_snapshot:
        raise HTTPException(403, "Permessi modificati: aggiorna e riprova.")
    return job


@router.get("/{job_id}")
def read_job(job_id: str, current_user: CurrentUser, db: DbSession):
    job = owned_job(db, job_id, current_user)
    response = ticket(job)
    if job.status in {"succeeded", "failed", "interrupted"}:
        data = json.loads(decrypt_secret(job.response_data)) if job.response_data else {}
        response["response_status"] = job.response_status
        if job.status != "succeeded":
            response["detail"] = data.get("detail", "Operazione non riuscita")
        elif data.get("kind") == "file":
            response["file_url"] = "/integration-jobs/" + job.id + "/file"
        else:
            response["result"] = data.get("value")
    return response


@router.get("/{job_id}/file")
def read_job_file(job_id: str, current_user: CurrentUser, db: DbSession):
    job = owned_job(db, job_id, current_user)
    if job.status != "succeeded" or not job.response_data:
        raise HTTPException(409, "File non ancora pronto")
    data = json.loads(decrypt_secret(job.response_data))
    if data.get("kind") != "file":
        raise HTTPException(404, "File non disponibile")
    path = manager()._path(data["key"])
    if not path.is_file():
        raise HTTPException(404, "File non disponibile")
    with path.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != data["sha256"]:
            raise HTTPException(409, "File non più integro: aggiorna e riprova.")
    return FileResponse(path, filename=data["filename"], media_type=data["media_type"])
