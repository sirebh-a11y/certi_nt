from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func
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
    query_timeout: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    schema_name: Mapped[str] = mapped_column(String(128), default="dbo", nullable=False)
    object_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    last_test_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


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
