from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class CameraCreate(BaseModel):
    camera_name: str = Field(..., max_length=100)
    location: str = Field(..., max_length=200)
    ip_address: Optional[str] = Field(None, max_length=45)


class CameraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_name: str
    location: str
    ip_address: Optional[str] = None
    created_at: datetime


class UnauthorizedLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plate_number: str
    detected_at: datetime
    location: Optional[str] = None
