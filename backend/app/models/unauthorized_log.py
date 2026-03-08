from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.core.database import Base


class UnauthorizedLog(Base):
    """ORM model for the ``unauthorized_logs`` table."""

    __tablename__ = "unauthorized_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plate_number = Column(
        String(20), nullable=False, index=True,
        comment="Plate number that was not in authorized_vehicles",
    )
    detected_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    location = Column(
        String(200), nullable=True, default="Gate 1",
        comment="Camera / gate location identifier",
    )
