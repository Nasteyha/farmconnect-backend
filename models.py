from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Date, Text
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    id_verified = Column(Boolean, default=False)
    document_status = Column(String, default="not submitted")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String, nullable=False)
    location_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    location_lat = Column(Float, nullable=False)
    location_lng = Column(Float, nullable=False)
    size_acres = Column(Float, nullable=False)
    photo_url = Column(String, nullable=False)

    water_availability = Column(String, nullable=True)
    sunlight = Column(String, nullable=True)
    soil_info = Column(String, nullable=True)

    # fixed / negotiable: KSh per month. harvest_share: percentage of harvest.
    price_type = Column(String, nullable=False)
    price_value = Column(Float, nullable=False)

    availability_start = Column(Date, nullable=False)
    availability_end = Column(Date, nullable=False)

    status = Column(String, default="available")
    crop_suggestions = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())