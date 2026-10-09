from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Literal
from datetime import date
from typing import Optional

class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str
    password: str = Field(min_length=6)
    role: Literal["landowner", "grower"]

    @field_validator("phone")
    @classmethod
    def validate_kenyan_phone(cls, value):
        if not value.startswith("+254") or len(value) != 13 or not value[4:].isdigit():
            raise ValueError("Phone number must be in the format +254XXXXXXXXX")
        return value

class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: str
    role: str
    id_verified: bool
    document_status: str

    class Config:
        from_attributes = True


class ListingCreate(BaseModel):
    owner_id: int
    location_lat: float
    location_lng: float
    size_acres: float = Field(gt=0)
    photo_url: str

    water_availability: Optional[str] = None
    sunlight: Optional[str] = None
    soil_info: Optional[str] = None

    price_type: Literal["fixed", "negotiable", "harvest_share"]
    price_value: float = Field(gt=0)

    availability_start: date
    availability_end: date

    @field_validator("availability_end")
    @classmethod
    def end_after_start(cls, value, info):
        start = info.data.get("availability_start")
        if start and value <= start:
            raise ValueError("availability_end must be after availability_start")
        return value

class ListingResponse(BaseModel):
    id: int
    owner_id: int
    location_lat: float
    location_lng: float
    size_acres: float
    photo_url: str
    water_availability: Optional[str]
    sunlight: Optional[str]
    soil_info: Optional[str]
    price_type: str
    price_value: float
    availability_start: date
    availability_end: date
    status: str
    crop_suggestions: Optional[str]


class AdminLogin(BaseModel):
    username: str
    password: str

    class Config:
        from_attributes = True