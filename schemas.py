from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from typing import Literal, Optional
from datetime import date, datetime


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str
    password: str = Field(min_length=6, max_length=72)
    role: Literal["landowner", "grower"]

    @field_validator("phone")
    @classmethod
    def validate_kenyan_phone(cls, value):
        if not value.startswith("+254") or len(value) != 13 or not value[4:].isdigit():
            raise ValueError("Phone number must be in the format +254XXXXXXXXX")
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    phone: str
    role: str
    id_verified: bool
    document_status: str
    document_type: Optional[str] = None


class DocumentReview(BaseModel):
    decision: Literal["approved", "rejected"]


class LoginResponse(UserResponse):
    access_token: str
    token_type: str = "bearer"


class ListingCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    location_name: str = Field(min_length=2, max_length=120)
    description: Optional[str] = None

    location_lat: float = Field(ge=-90, le=90)
    location_lng: float = Field(ge=-180, le=180)
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

    @model_validator(mode="after")
    def harvest_share_is_a_percentage(self):
        if self.price_type == "harvest_share" and self.price_value > 100:
            raise ValueError("For harvest_share, price_value is a percentage and cannot exceed 100")
        return self


class ListingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int

    title: str
    location_name: str
    description: Optional[str]

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


class ListingDetailResponse(ListingResponse):
    owner_name: str
    owner_document_status: str


class BookingCreate(BaseModel):
    listing_id: int
    start_date: date
    end_date: date
    message: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class BookingDecision(BaseModel):
    decision: Literal["accepted", "declined"]


class BookingResponse(BaseModel):
    id: int
    listing_id: int
    listing_title: str
    grower_id: int
    grower_name: str
    start_date: date
    end_date: date
    message: Optional[str]
    status: str

class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message: str
    link: Optional[str]
    is_read: bool
    created_at: datetime

class CropAnswer(BaseModel):
    suggestions: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str