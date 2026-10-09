import getpass
from sqlalchemy.exc import IntegrityError
from database import SessionLocal
import models
from security import hash_password

ADMIN_EMAIL = "admin@farmconnect.com"
ADMIN_NAME = "FarmConnect Admin"
ADMIN_PHONE = "+254700000000"

db = SessionLocal()

existing = db.query(models.User).filter(models.User.email == ADMIN_EMAIL).first()
if existing:
    print(f"{ADMIN_EMAIL} already exists (id={existing.id}, role={existing.role}). Nothing was changed.")
    db.close()
    raise SystemExit

# getpass hides what you type, so the password never appears on screen or in a file
password = getpass.getpass("Choose an admin password (8 to 72 characters): ")
confirm = getpass.getpass("Type it again: ")

if password != confirm:
    print("The two passwords did not match. Nothing was changed.")
    db.close()
    raise SystemExit
if not 8 <= len(password.encode("utf-8")) <= 72:
    print("Password must be 8 to 72 characters. Nothing was changed.")
    db.close()
    raise SystemExit

admin = models.User(
    name=ADMIN_NAME,
    email=ADMIN_EMAIL,
    phone=ADMIN_PHONE,
    hashed_password=hash_password(password),
    role="admin",
)
db.add(admin)
try:
    db.commit()
except IntegrityError:
    db.rollback()
    print("That phone number is already used by another user. Change ADMIN_PHONE in the script and rerun.")
    db.close()
    raise SystemExit

print(f"Admin created: {ADMIN_EMAIL}")
db.close()