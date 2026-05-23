from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Supplier(Base):
    __tablename__ = "fornitori"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ragione_sociale: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    partita_iva: Mapped[str | None] = mapped_column(String(64), nullable=True)
    codice_fiscale: Mapped[str | None] = mapped_column(String(64), nullable=True)
    indirizzo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cap: Mapped[str | None] = mapped_column(String(32), nullable=True)
    citta: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provincia: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nazione: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attivo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reader_template_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    aliases = relationship(
        "SupplierAlias",
        back_populates="supplier",
        cascade="all, delete-orphan",
        order_by="SupplierAlias.nome_alias",
    )
    esolver_link = relationship(
        "SupplierEsolverLink",
        back_populates="supplier",
        cascade="all, delete-orphan",
        uselist=False,
    )


class SupplierAlias(Base):
    __tablename__ = "fornitori_alias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fornitore_id: Mapped[int] = mapped_column(ForeignKey("fornitori.id"), nullable=False, index=True)
    nome_alias: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    fonte: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attivo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    supplier = relationship("Supplier", back_populates="aliases")


class SupplierEsolverLink(Base):
    __tablename__ = "fornitori_esolver_link"
    __table_args__ = (UniqueConstraint("cod_clifor", name="uq_fornitori_esolver_cod_clifor"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fornitore_id: Mapped[int] = mapped_column(ForeignKey("fornitori.id"), nullable=False, unique=True, index=True)
    cod_clifor: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ragione_sociale_esolver: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cod_alternativo2: Mapped[str | None] = mapped_column(String(64), nullable=True)
    partita_iva_esolver: Mapped[str | None] = mapped_column(String(64), nullable=True)
    codice_fiscale_esolver: Mapped[str | None] = mapped_column(String(64), nullable=True)
    indirizzo_esolver: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cap_esolver: Mapped[str | None] = mapped_column(String(32), nullable=True)
    citta_esolver: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provincia_esolver: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nazione_esolver: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_esolver: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefono_esolver: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stato_link: Mapped[str] = mapped_column(String(32), default="confermato", nullable=False, index=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    supplier = relationship("Supplier", back_populates="esolver_link")
