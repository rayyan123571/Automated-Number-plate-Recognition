from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models.authorized_vehicle import AuthorizedVehicle
from app.models.unauthorized_log import UnauthorizedLog
from app.models.detection import Detection
from app.models.camera import Camera
from app.schemas.vehicle_schema import VehicleCheckResponse, VehicleCreate, VehicleResponse
from app.services.vehicle_service import add_authorized_vehicle, find_vehicle_by_plate

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.post("/add", response_model=VehicleResponse)
def add_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)):
    """Add a new authorized vehicle."""
    try:
        vehicle = add_authorized_vehicle(
            db,
            plate_number=payload.plate_number,
            owner_name=payload.owner_name,
            vehicle_type=payload.vehicle_type,
            department=payload.department,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Plate number '{payload.plate_number.upper().strip()}' already exists.",
        )
    return vehicle


@router.get("/list", response_model=List[VehicleResponse])
def list_vehicles(db: Session = Depends(get_db)):
    """Return all authorized vehicles."""
    return db.query(AuthorizedVehicle).order_by(AuthorizedVehicle.created_at.desc()).all()


@router.get("/check/{plate_number}", response_model=VehicleCheckResponse)
def check_vehicle(plate_number: str, db: Session = Depends(get_db)):
    """Check whether a plate number is authorized."""
    normalized = plate_number.upper().strip()
    vehicle = find_vehicle_by_plate(db, normalized)
    return VehicleCheckResponse(
        plate=normalized,
        status="AUTHORIZED" if vehicle else "UNAUTHORIZED",
    )


@router.delete("/{vehicle_id}")
def delete_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    """Delete an authorized vehicle by ID."""
    vehicle = db.query(AuthorizedVehicle).filter(AuthorizedVehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    db.delete(vehicle)
    db.commit()
    return {"message": f"Vehicle {vehicle.plate_number} deleted."}


@router.get("/stats/summary")
def dashboard_stats(db: Session = Depends(get_db)):
    """Return summary statistics for the security dashboard."""
    total_detections = db.query(func.count(Detection.id)).scalar() or 0
    authorized_count = db.query(func.count(AuthorizedVehicle.id)).scalar() or 0
    unauthorized_count = db.query(func.count(UnauthorizedLog.id)).scalar() or 0
    camera_count = db.query(func.count(Camera.id)).scalar() or 0
    return {
        "total_detections": total_detections,
        "authorized_vehicles": authorized_count,
        "unauthorized_alerts": unauthorized_count,
        "active_cameras": camera_count,
    }
