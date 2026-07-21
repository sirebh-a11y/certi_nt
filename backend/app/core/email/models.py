from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EmailSettings(Base):
    __tablename__ = "email_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False)
    smtp_user: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    smtp_password_encrypted: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    smtp_tls: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mail_from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    mail_from_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mail_always_cc_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    acquisition_notification_admin_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
