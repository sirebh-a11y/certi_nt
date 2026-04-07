from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth.router import router as auth_router
from app.core.config import settings
from app.core.departments.router import router as departments_router
from app.core.logs.router import router as logs_router
from app.core.users.router import router as users_router
from app.modules.suppliers.router import router as suppliers_router
from app.startup.bootstrap import initialize_application


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_application()
    yield


app = FastAPI(title="CERTI_nt Core API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(departments_router, prefix="/api/departments", tags=["departments"])
app.include_router(logs_router, prefix="/api/logs", tags=["logs"])
app.include_router(suppliers_router, prefix="/api/suppliers", tags=["suppliers"])


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
