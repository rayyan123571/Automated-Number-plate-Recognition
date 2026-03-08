from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.core.database import Base


class Camera(Base):
    """ORM model for the ``cameras`` table."""

    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_name = Column(String(100), nullable=False)
    location = Column(String(200), nullable=False)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
