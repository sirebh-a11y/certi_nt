from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExternalConnection(Base):
    __tablename__ = "external_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    server_host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=1433, nullable=False)
    database_name: Mapped[str] = mapped_column(String(128), nullable=False)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    password_encrypted: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    driver_name: Mapped[str] = mapped_column(String(128), default="ODBC Driver 18 for SQL Server", nullable=False)
    encrypt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trust_server_certificate: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    connection_timeout: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    query_timeout: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    schema_name: Mapped[str] = mapped_column(String(128), default="dbo", nullable=False)
    object_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    last_test_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IntegrationBackgroundJob(Base):
    __tablename__ = "integration_background_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    operation: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    actor_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    revision: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    # Only queued/running jobs retain this unique key. Request keys persist to
    # replay an acknowledged operation after a lost HTTP response, never twice.
    active_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    request_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    request_data: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued", index=True)
    response_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    worker_token: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntegrationBackgroundReceipt(Base):
    __tablename__ = "integration_background_receipts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("integration_background_jobs.id"), nullable=False, index=True)


class EsolverExportPublicationSettings(Base):
    __tablename__ = "esolver_export_publication_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    external_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    database_name: Mapped[str] = mapped_column(String(128), default="certi_nt", nullable=False)
    schema_name: Mapped[str] = mapped_column(String(128), default="esolver_export", nullable=False)
    view_name: Mapped[str] = mapped_column(String(128), default="certi_certificati_pdf", nullable=False)
    reader_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    allowed_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ssl_mode: Mapped[str] = mapped_column(String(64), default="DA_FORNIRE_IT", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    last_view_test_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_view_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_view_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_permissions_test_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_permissions_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_permissions_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_validation_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    external_validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_validation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
