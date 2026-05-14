from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.ai.router import router as ai_router
from app.core.auth.router import router as auth_router
from app.core.config import settings
from app.core.departments.router import router as departments_router
from app.core.integrations.router import router as integrations_router
from app.core.logs.router import router as logs_router
from app.core.users.router import router as users_router
from app.modules.acquisition.router import router as acquisition_router
from app.modules.notes.router import router as notes_router
from app.modules.quarta_taglio.router import router as quarta_taglio_router
from app.modules.quarta_taglio.scheduler import quarta_taglio_periodic_sync_loop
from app.modules.standards.router import router as standards_router
from app.modules.supplier_kpi.router import router as supplier_kpi_router
from app.modules.suppliers.router import router as suppliers_router
from app.startup.bootstrap import initialize_application


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_application()
    sync_task = asyncio.create_task(quarta_taglio_periodic_sync_loop())
    try:
        yield
    finally:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="CERTI_nt Core API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(ai_router, prefix="/api/ai", tags=["ai"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(departments_router, prefix="/api/departments", tags=["departments"])
app.include_router(integrations_router, prefix="/api/integrations", tags=["integrations"])
app.include_router(notes_router, prefix="/api/notes", tags=["notes"])
app.include_router(standards_router, prefix="/api/standards", tags=["standards"])
app.include_router(logs_router, prefix="/api/logs", tags=["logs"])
app.include_router(suppliers_router, prefix="/api/suppliers", tags=["suppliers"])
app.include_router(supplier_kpi_router, prefix="/api/supplier-kpi", tags=["supplier-kpi"])
app.include_router(acquisition_router, prefix="/api/acquisition", tags=["acquisition"])
app.include_router(quarta_taglio_router, prefix="/api/quarta-taglio", tags=["quarta-taglio"])


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
