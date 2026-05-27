from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.suppliers.models import Supplier


class SupplierInstallationCode(Base):
    __tablename__ = "fornitori_codici_installazione"
    __table_args__ = (UniqueConstraint("codice", name="uq_fornitori_codici_installazione_codice"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codice: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    fornitore_id: Mapped[int | None] = mapped_column(ForeignKey("fornitori.id"), nullable=True, index=True)
    esolver_cod_clifor: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    esolver_ragione_sociale: Mapped[str | None] = mapped_column(String(255), nullable=True)
    etichetta_manuale: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    supplier = relationship(Supplier)
