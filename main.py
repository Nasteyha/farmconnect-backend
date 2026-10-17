from typing import Optional

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi.middleware.cors import CORSMiddleware

from database import SessionLocal, engine
import models
import schemas
from security import hash_password, verify_password

app = FastAPI()

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


@app.post("/login", response_model=schemas.UserResponse)
def login(credentials: schemas.LoginRequest, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == credentials.email).first()
    # Same error for "no such email" and "wrong password", so an attacker
    # can't use the message to find out which emails are registered.
    if not db_user or not verify_password(credentials.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return db_user


@app.get("/users/{user_id}", response_model=schemas.UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@app.put("/users/{user_id}", response_model=schemas.UserResponse)
def update_user(user_id: int, user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db_user.name = user.name
    db_user.email = user.email
    db_user.phone = user.phone
    db_user.hashed_password = hash_password(user.password)
    db_user.role = user.role
    db.commit()
    db.refresh(db_user)
    return db_user


@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(db_user)
    db.commit()
    return {"message": "User deleted"}


# ---------- LISTING ENDPOINTS ----------

@app.post("/listings", response_model=schemas.ListingResponse)
def create_listing(listing: schemas.ListingCreate, db: Session = Depends(get_db)):
    owner = db.query(models.User).filter(models.User.id == listing.owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    if owner.role != "landowner":
        raise HTTPException(status_code=400, detail="Only landowners can create listings")

    db_listing = models.Listing(**listing.model_dump())
    db.add(db_listing)
    db.commit()
    db.refresh(db_listing)
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


@app.get("/listings/{listing_id}", response_model=schemas.ListingResponse)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    db_listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not db_listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return db_listing


@app.put("/listings/{listing_id}", response_model=schemas.ListingResponse)
def update_listing(listing_id: int, listing: schemas.ListingCreate, db: Session = Depends(get_db)):
    db_listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not db_listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # owner_id is deliberately NOT updated: a listing can't be handed to another user
    changes = listing.model_dump(exclude={"owner_id"})
    for field, value in changes.items():
        setattr(db_listing, field, value)

    db.commit()
    db.refresh(db_listing)
    return db_listing


@app.delete("/listings/{listing_id}")
def delete_listing(listing_id: int, db: Session = Depends(get_db)):
    db_listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not db_listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if db_listing.status != "available":
        raise HTTPException(status_code=400, detail="Only available listings can be deleted")
    db.delete(db_listing)
    db.commit()
    return {"message": "Listing deleted"}


# ---------- ADMIN ENDPOINTS ----------

@app.get("/admin/stats")
def admin_stats(db: Session = Depends(get_db)):
    landowners = db.query(models.User).filter(models.User.role == "landowner").count()
    growers = db.query(models.User).filter(models.User.role == "grower").count()
    return {"landowners": landowners, "growers": growers, "total": landowners + growers}