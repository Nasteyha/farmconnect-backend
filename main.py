import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi.middleware.cors import CORSMiddleware
from crop_ai import generate_crop_suggestions, CropSuggestionError

from database import SessionLocal, engine
import models
import schemas
from security import hash_password, verify_password, create_access_token, decode_access_token

app = FastAPI()

# ---------- DOCUMENT UPLOAD SETTINGS ----------

UPLOAD_DIR = Path(__file__).parent / "uploads"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

# Allowed file types, and the first bytes every genuine file of that type starts with.
# We check these so a file can't pass just by being renamed to ".pdf".
FILE_SIGNATURES = {
    ".pdf": b"%PDF",
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- WHO IS ASKING? (token checks) ----------

# Reads the "Authorization: Bearer <token>" header. auto_error=False lets us
# send our own clear 401 message when the header is missing.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    # Look the user up again on every request, so a deleted user's old token stops working
    user = db.query(models.User).filter(models.User.id == int(payload["sub"])).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user


def require_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    return current_user


@app.get("/")
def read_root():
    return {"message": "FarmConnect backend is running"}


# ---------- USER ENDPOINTS ----------

@app.post("/users", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = models.User(
        name=user.name,
        email=user.email,
        phone=user.phone,
        hashed_password=hash_password(user.password),
        role=user.role,
    )
    db.add(db_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email or phone already registered")
    db.refresh(db_user)
    return db_user


@app.post("/login", response_model=schemas.LoginResponse)
def login(credentials: schemas.LoginRequest, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == credentials.email).first()
    # Same error for "no such email" and "wrong password", so an attacker
    # can't use the message to find out which emails are registered.
    if not db_user or not verify_password(credentials.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    # Same fields as before, plus the token. The current frontend ignores the
    # extra field, so it keeps working until we teach it to use the token.
    user_data = schemas.UserResponse.model_validate(db_user).model_dump()
    return schemas.LoginResponse(**user_data, access_token=create_access_token(db_user.id))


@app.get("/me", response_model=schemas.UserResponse)
def read_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.post("/me/document", response_model=schemas.UserResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == "admin":
        raise HTTPException(status_code=400, detail="Admins do not submit documents")
    if current_user.document_status == "approved":
        raise HTTPException(status_code=400, detail="Your document is already approved")

    # The server decides which document is needed from the user's role, the client does not choose
    doc_type = "land_document" if current_user.role == "landowner" else "national_id"

    # 1. Type check: by extension, then by the file's real first bytes
    extension = Path(file.filename or "").suffix.lower()
    if extension not in FILE_SIGNATURES:
        raise HTTPException(status_code=400, detail="Only PDF, PNG or JPG files are allowed")

    # 2. Size check: read one byte past the limit so we know if it is too big
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (maximum 5 MB)")
    if not data.startswith(FILE_SIGNATURES[extension]):
        raise HTTPException(status_code=400, detail="File content does not match its type")

    # 3. Save under a name WE choose. The uploaded name is never used on disk.
    UPLOAD_DIR.mkdir(exist_ok=True)
    stored_name = f"{current_user.id}_{uuid.uuid4().hex}{extension}"
    (UPLOAD_DIR / stored_name).write_bytes(data)

    # A re-submission replaces the old file
    if current_user.document_path:
        (UPLOAD_DIR / current_user.document_path).unlink(missing_ok=True)

    current_user.document_type = doc_type
    current_user.document_path = stored_name
    current_user.document_status = "pending"
    db.commit()
    db.refresh(current_user)
    return current_user


def require_self_or_admin(user_id: int, current_user: models.User):
    # You may only touch your own account, unless you are an admin
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="You can only access your own account")


@app.get("/users/{user_id}", response_model=schemas.UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_self_or_admin(user_id, current_user)
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@app.put("/users/{user_id}", response_model=schemas.UserResponse)
def update_user(
    user_id: int,
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_self_or_admin(user_id, current_user)
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db_user.name = user.name
    db_user.email = user.email
    db_user.phone = user.phone
    db_user.hashed_password = hash_password(user.password)
    db_user.role = user.role
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email or phone already registered")
    db.refresh(db_user)
    return db_user


@app.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_self_or_admin(user_id, current_user)
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db.query(models.Notification).filter(models.Notification.user_id == user_id).delete()
    db.delete(db_user)
    try:
        db.commit()
    except IntegrityError:
        # The user still owns listings, which point back to them
        db.rollback()
        raise HTTPException(status_code=400, detail="This user still has listings or booking requests")
    return {"message": "User deleted"}


# ---------- LISTING ENDPOINTS ----------

@app.post("/listings", response_model=schemas.ListingResponse)
def create_listing(
    listing: schemas.ListingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "landowner":
        raise HTTPException(status_code=403, detail="Only landowners can create listings")

    # The owner is whoever is logged in. The browser does not get to say.
    db_listing = models.Listing(**listing.model_dump(), owner_id=current_user.id)
    db.add(db_listing)
    db.commit()
    db.refresh(db_listing)

    try:
        db_listing.crop_suggestions = generate_crop_suggestions(db_listing)
        db.commit()
        db.refresh(db_listing)
    except CropSuggestionError:
        pass
    return db_listing


@app.get("/listings", response_model=list[schemas.ListingResponse])
def get_listings(
    owner_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Listing)
    if owner_id is not None:
        query = query.filter(models.Listing.owner_id == owner_id)
    if status is not None:
        query = query.filter(models.Listing.status == status)
    return query.order_by(models.Listing.id.desc()).all()


@app.get("/listings/{listing_id}", response_model=schemas.ListingDetailResponse)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    db_listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not db_listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    owner = db.query(models.User).filter(models.User.id == db_listing.owner_id).first()
    listing_data = schemas.ListingResponse.model_validate(db_listing).model_dump()
    return schemas.ListingDetailResponse(
        **listing_data,
        owner_name=owner.name,
        owner_document_status=owner.document_status,
    )

def get_own_available_listing(listing_id: int, db: Session, current_user: models.User):
    """Find a listing and make sure the logged-in user owns it and it can still be changed."""
    db_listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not db_listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if db_listing.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="This is not your listing")
    if db_listing.status != "available":
        raise HTTPException(status_code=400, detail="Only available listings can be changed")
    return db_listing


@app.put("/listings/{listing_id}", response_model=schemas.ListingResponse)
def update_listing(
    listing_id: int,
    listing: schemas.ListingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_listing = get_own_available_listing(listing_id, db, current_user)

    # owner_id is never in the request, so a listing can't be handed to another user
    for field, value in listing.model_dump().items():
        setattr(db_listing, field, value)

    db.commit()
    db.refresh(db_listing)
    return db_listing


@app.delete("/listings/{listing_id}")
def delete_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_listing = get_own_available_listing(listing_id, db, current_user)
    db.query(models.Booking).filter(models.Booking.listing_id == listing_id).delete()
    db.delete(db_listing)
    db.delete(db_listing)
    db.commit()
    return {"message": "Listing deleted"}

@app.post("/listings/{listing_id}/crop-assistant", response_model=schemas.CropAnswer)
def ask_crop_assistant(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not db_listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    try:
        return {"suggestions": generate_crop_suggestions(db_listing)}
    except CropSuggestionError as error:
        raise HTTPException(status_code=503, detail=str(error))
    

@app.post("/listings/{listing_id}/crop-suggestions", response_model=schemas.ListingResponse)
def refresh_crop_suggestions(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not db_listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if db_listing.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="This is not your listing")
    try:
        db_listing.crop_suggestions = generate_crop_suggestions(db_listing)
    except CropSuggestionError as error:
        raise HTTPException(status_code=503, detail=str(error))
    db.commit()
    db.refresh(db_listing)
    return db_listing

# ---------- NOTIFICATIONS ----------

def notify(db: Session, user_id: int, message: str, link: str = "/requests"):
    """Queue a notification for one user. No commit here: it is saved together with
    whatever action caused it, so either both happen or neither does."""
    db.add(models.Notification(user_id=user_id, message=message, link=link))


@app.get("/notifications", response_model=list[schemas.NotificationResponse])
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == current_user.id)
        .order_by(models.Notification.id.desc())
        .limit(20)
        .all()
    )


@app.put("/notifications/read")
def mark_notifications_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False,  # noqa: E712
    ).update({"is_read": True})
    db.commit()
    return {"message": "Marked as read"}

# ---------- BOOKING ENDPOINTS ----------

def booking_out(booking: models.Booking) -> schemas.BookingResponse:
    return schemas.BookingResponse(
        id=booking.id,
        listing_id=booking.listing_id,
        listing_title=booking.listing.title,
        grower_id=booking.grower_id,
        grower_name=booking.grower.name,
        start_date=booking.start_date,
        end_date=booking.end_date,
        message=booking.message,
        status=booking.status,
    )


@app.post("/bookings", response_model=schemas.BookingResponse)
def create_booking(
    data: schemas.BookingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "grower":
        raise HTTPException(status_code=403, detail="Only growers can request a plot")

    listing = db.query(models.Listing).filter(models.Listing.id == data.listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.status != "available":
        raise HTTPException(status_code=400, detail="This plot is not available")
    if data.start_date < listing.availability_start or data.end_date > listing.availability_end:
        raise HTTPException(status_code=400, detail="Requested dates are outside the availability window")

    already = db.query(models.Booking).filter(
        models.Booking.listing_id == listing.id,
        models.Booking.grower_id == current_user.id,
        models.Booking.status == "pending",
    ).first()
    if already:
        raise HTTPException(status_code=400, detail="You already have a pending request for this plot")

    booking = models.Booking(
        listing_id=listing.id,
        grower_id=current_user.id,   # from the token, never from the request body
        start_date=data.start_date,
        end_date=data.end_date,
        message=data.message,
    )
    db.add(booking)
    notify(db, listing.owner_id, f"{current_user.name} requested {listing.title}")
    db.commit()
    db.refresh(booking)
    return booking_out(booking)

@app.get("/bookings", response_model=list[schemas.BookingResponse])
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Booking)
    if current_user.role == "grower":
        query = query.filter(models.Booking.grower_id == current_user.id)
    elif current_user.role == "landowner":
        query = query.join(models.Listing).filter(models.Listing.owner_id == current_user.id)
    else:
        raise HTTPException(status_code=403, detail="Admins have no bookings")
    return [booking_out(b) for b in query.order_by(models.Booking.id.desc()).all()]


@app.put("/bookings/{booking_id}/decision", response_model=schemas.BookingResponse)
def decide_booking(
    booking_id: int,
    body: schemas.BookingDecision,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Request not found")

    listing = booking.listing
    if listing.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="This is not your listing")
    if booking.status != "pending":
        raise HTTPException(status_code=400, detail="This request has already been answered")

    if body.decision == "accepted":
        if listing.status != "available":
            raise HTTPException(status_code=400, detail="This plot is no longer available")
        booking.status = "accepted"
        listing.status = "reserved"
        notify(db, booking.grower_id, f"Your request for {listing.title} was accepted")
        # the plot is taken, so any other waiting requests for it cannot be granted
        others = db.query(models.Booking).filter(
            models.Booking.listing_id == listing.id,
            models.Booking.id != booking.id,
            models.Booking.status == "pending",
        ).all()
        for other in others:
            other.status = "declined"
            notify(db, other.grower_id, f"Your request for {listing.title} was declined: the plot went to another grower")
    else:
        booking.status = "declined"
        notify(db, booking.grower_id, f"Your request for {listing.title} was declined")

    db.commit()
    db.refresh(booking)
    return booking_out(booking)

# ---------- ADMIN ENDPOINTS ----------

@app.get("/admin/stats")
def admin_stats(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    landowners = db.query(models.User).filter(models.User.role == "landowner").count()
    growers = db.query(models.User).filter(models.User.role == "grower").count()
    return {"landowners": landowners, "growers": growers, "total": landowners + growers}


@app.get("/admin/users", response_model=list[schemas.UserResponse])
def admin_list_users(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    # Admin accounts are left out, matching the dashboard totals
    return (
        db.query(models.User)
        .filter(models.User.role != "admin")
        .order_by(models.User.id)
        .all()
    )


@app.get("/admin/users/{user_id}/document")
def admin_view_document(
    user_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.document_path:
        raise HTTPException(status_code=404, detail="No document submitted")
    path = UPLOAD_DIR / user.document_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Document file is missing")
    return FileResponse(path)


@app.put("/admin/users/{user_id}/document", response_model=schemas.UserResponse)
def admin_review_document(
    user_id: int,
    review: schemas.DocumentReview,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.document_status != "pending":
        raise HTTPException(status_code=400, detail="This user has no pending document")
    user.document_status = review.decision
    db.commit()
    db.refresh(user)
    return user