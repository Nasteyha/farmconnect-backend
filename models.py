from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Date, Text
from sqlalchemy.sql import func
from database import Base
from sqlalchemy.orm import relationship

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
    document_type = Column(String, nullable=True)   # "national_id" or "land_document"
    document_path = Column(String, nullable=True)   # file name inside the uploads/ folder
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

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    grower_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    message = Column(Text, nullable=True)

    status = Column(String, default="pending")   # pending / accepted / declined
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    listing = relationship("Listing")
    grower = relationship("User")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # who should see it
    message = Column(String, nullable=False)
    link = Column(String, nullable=True)        # where "View" should go, e.g. "/requests"
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())