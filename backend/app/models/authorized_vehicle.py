from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.core.database import Base


class AuthorizedVehicle(Base):
    """ORM model for the ``authorized_vehicles`` table."""

    __tablename__ = "authorized_vehicles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plate_number = Column(
        String(20), unique=True, nullable=False, index=True,
        comment="Unique plate number (e.g., LEA1234)",
    )
    owner_name = Column(String(100), nullable=False)
    vehicle_type = Column(String(50), nullable=True)
    department = Column(String(100), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
