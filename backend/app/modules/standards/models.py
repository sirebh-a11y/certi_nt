from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class NormativeStandard(Base):
    __tablename__ = "normative_standards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    lega_base: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    lega_designazione: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    variante_lega: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    norma: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    trattamento_termico: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tipo_prodotto: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    misura_tipo: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fonte_excel_foglio: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fonte_excel_blocco: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stato_validazione: Mapped[str] = mapped_column(String(32), default="attivo", nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chemistry_limits: Mapped[list["NormativeStandardChemistry"]] = relationship(
        "NormativeStandardChemistry",
        back_populates="standard",
        cascade="all, delete-orphan",
        order_by="NormativeStandardChemistry.elemento",
    )
    property_limits: Mapped[list["NormativeStandardProperty"]] = relationship(
        "NormativeStandardProperty",
        back_populates="standard",
        cascade="all, delete-orphan",
        order_by="NormativeStandardProperty.id",
    )


class NormativeStandardChemistry(Base):
    __tablename__ = "normative_standard_chemistry"
    __table_args__ = (UniqueConstraint("standard_id", "elemento", name="uq_standard_chemistry_element"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    standard_id: Mapped[int] = mapped_column(ForeignKey("normative_standards.id"), nullable=False, index=True)
    elemento: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    standard = relationship("NormativeStandard", back_populates="chemistry_limits")


class NormativeStandardProperty(Base):
    __tablename__ = "normative_standard_properties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    standard_id: Mapped[int] = mapped_column(ForeignKey("normative_standards.id"), nullable=False, index=True)
    proprieta: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    misura_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    misura_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    range_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    standard = relationship("NormativeStandard", back_populates="property_limits")
