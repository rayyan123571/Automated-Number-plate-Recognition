from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.camera import Camera
from app.schemas.camera_schema import CameraCreate, CameraResponse

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.post("/add", response_model=CameraResponse)
def add_camera(payload: CameraCreate, db: Session = Depends(get_db)):
    camera = Camera(
        camera_name=payload.camera_name,
        location=payload.location,
        ip_address=payload.ip_address,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.get("/list", response_model=List[CameraResponse])
def list_cameras(db: Session = Depends(get_db)):
    return db.query(Camera).order_by(Camera.created_at.desc()).all()


@router.delete("/{camera_id}")
def delete_camera(camera_id: int, db: Session = Depends(get_db)):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found.")
    db.delete(camera)
    db.commit()
    return {"message": "Camera deleted."}
