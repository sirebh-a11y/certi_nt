from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class NoteTemplate(Base):
    __tablename__ = "note_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    note_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    note_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    row_links: Mapped[list["AcquisitionRowNoteTemplate"]] = relationship(
        "AcquisitionRowNoteTemplate",
        back_populates="note_template",
        cascade="all, delete-orphan",
    )


class AcquisitionRowNoteTemplate(Base):
    __tablename__ = "acquisition_row_note_templates"
    __table_args__ = (
        UniqueConstraint("acquisition_row_id", "note_template_id", name="uq_acquisition_row_note_template"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    acquisition_row_id: Mapped[int] = mapped_column(ForeignKey("datimaterialeincoming.id"), nullable=False, index=True)
    note_template_id: Mapped[int] = mapped_column(ForeignKey("note_templates.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    acquisition_row = relationship("AcquisitionRow", back_populates="custom_note_links")
    note_template = relationship("NoteTemplate", back_populates="row_links")
