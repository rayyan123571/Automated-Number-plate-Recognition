from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.unauthorized_log import UnauthorizedLog
from app.schemas.camera_schema import UnauthorizedLogResponse

router = APIRouter(prefix="/unauthorized", tags=["Unauthorized Logs"])


@router.get("/logs", response_model=List[UnauthorizedLogResponse])
def list_unauthorized_logs(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return (
        db.query(UnauthorizedLog)
        .order_by(UnauthorizedLog.detected_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/count")
def unauthorized_count(db: Session = Depends(get_db)):
    from sqlalchemy import func
    total = db.query(func.count(UnauthorizedLog.id)).scalar() or 0
    return {"count": total}
