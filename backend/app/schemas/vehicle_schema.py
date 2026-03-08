from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class VehicleCreate(BaseModel):
    plate_number: str = Field(..., max_length=20, description="Unique plate number")
    owner_name: str = Field(..., max_length=100)
    vehicle_type: Optional[str] = Field(None, max_length=50)
    department: Optional[str] = Field(None, max_length=100)


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plate_number: str
    owner_name: str
    vehicle_type: Optional[str] = None
    department: Optional[str] = None
    created_at: datetime


class VehicleCheckResponse(BaseModel):
    plate: str
    status: str  # "AUTHORIZED" or "UNAUTHORIZED"
