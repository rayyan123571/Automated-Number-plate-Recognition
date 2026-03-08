from typing import Optional

from sqlalchemy.orm import Session

from app.models.authorized_vehicle import AuthorizedVehicle


def add_authorized_vehicle(
    db: Session,
    plate_number: str,
    owner_name: str,
    vehicle_type: Optional[str] = None,
    department: Optional[str] = None,
) -> AuthorizedVehicle:
    """Insert a new authorized vehicle and return the created row."""
    vehicle = AuthorizedVehicle(
        plate_number=plate_number.upper().strip(),
        owner_name=owner_name,
        vehicle_type=vehicle_type,
        department=department,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def find_vehicle_by_plate(db: Session, plate_number: str) -> Optional[AuthorizedVehicle]:
    """Return the authorized vehicle for *plate_number*, or ``None``."""
    return (
        db.query(AuthorizedVehicle)
        .filter(AuthorizedVehicle.plate_number == plate_number.upper().strip())
        .first()
    )
