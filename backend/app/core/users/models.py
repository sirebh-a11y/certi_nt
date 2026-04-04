from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    openai_api_key_encrypted: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    force_password_change: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    department = relationship("Department", back_populates="users")
