from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
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
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    aliases = relationship(
        "SupplierAlias",
        back_populates="supplier",
        cascade="all, delete-orphan",
        order_by="SupplierAlias.nome_alias",
    )


class SupplierAlias(Base):
    __tablename__ = "fornitori_alias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fornitore_id: Mapped[int] = mapped_column(ForeignKey("fornitori.id"), nullable=False, index=True)
    nome_alias: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    fonte: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attivo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    supplier = relationship("Supplier", back_populates="aliases")
