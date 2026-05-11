from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class QuartaTaglioSyncRun(Base):
    __tablename__ = "quarta_taglio_sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_ol: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cdq_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    triggered_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QuartaTaglioRow(Base):
    __tablename__ = "quarta_taglio_rows"
    __table_args__ = (
        UniqueConstraint("cod_odp", "cod_art", "cdq", "colata", name="uq_quarta_taglio_business_row"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    latest_run_id: Mapped[int | None] = mapped_column(ForeignKey("quarta_taglio_sync_runs.id"), nullable=True, index=True)
    codice_registro: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    data_registro: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    cod_odp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    cod_art: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    des_art: Mapped[str | None] = mapped_column(Text, nullable=True)
    cdq: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    colata: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    qta_totale: Mapped[float | None] = mapped_column(Float, nullable=True)
    righe_materiale: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lotti_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cod_lotti: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    saldo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status_color: Mapped[str] = mapped_column(String(16), default="red", nullable=False, index=True)
    status_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status_details: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    matching_row_ids: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    seen_in_last_sync: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    latest_run = relationship("QuartaTaglioSyncRun")


class QuartaTaglioStandardSelection(Base):
    __tablename__ = "quarta_taglio_standard_selections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cod_odp: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    standard_id: Mapped[int] = mapped_column(ForeignKey("normative_standards.id"), nullable=False, index=True)
    selected_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    standard = relationship("NormativeStandard")


class QuartaTaglioEsolverLink(Base):
    __tablename__ = "quarta_taglio_esolver_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cod_odp: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="missing", nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cod_f3: Mapped[str | None] = mapped_column(Text, nullable=True)
    cliente: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordine_cliente: Mapped[str | None] = mapped_column(Text, nullable=True)
    conferma_ordine: Mapped[str | None] = mapped_column(Text, nullable=True)
    ddt: Mapped[str | None] = mapped_column(Text, nullable=True)
    qta_totale: Mapped[float | None] = mapped_column(Float, nullable=True)
    rows: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class QuartaTaglioArticleOverride(Base):
    __tablename__ = "quarta_taglio_article_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cod_odp: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    descrizione: Mapped[str | None] = mapped_column(Text, nullable=True)
    disegno: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class QuartaTaglioFinalCertificate(Base):
    __tablename__ = "quarta_taglio_final_certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cod_odp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)
    certificate_number: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    draft_number: Mapped[str] = mapped_column(String(128), nullable=False)
    cdq_signature: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    cdq_values: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    storage_key_docx: Mapped[str | None] = mapped_column(String(512), nullable=True)
    storage_key_pdf: Mapped[str | None] = mapped_column(String(512), nullable=True)
    download_token: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    certified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    quality_manager_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
