from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CustomerRequirement(Base):
    __tablename__ = "customer_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cod_f3: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    cliente: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    requires_chemical_analysis: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_mechanical_mp: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_mechanical_forged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_hardness_hb: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_lot_traceability_text: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_lot_traceability_photo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_dimensional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_electrical_conductivity_forged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_marking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_macro_micro: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_ndt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    specific_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_sheet: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
