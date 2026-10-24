"""
Fill the users table with fictional demo users until it has TARGET_USERS
landowners and growers in total. Safe to run more than once: it only creates
what is missing and never deletes or changes existing users.

Run from the backend folder (venv active):  python seed_users.py
"""
import getpass

from database import SessionLocal
import models
from security import hash_password

# Landowners + growers wanted in total (admin accounts are not counted,
# because the admin dashboard total does not count them either).
TARGET_USERS = 50

# Fictional name parts. Names are made by mixing these two lists.
FIRST_NAMES = [
    "Wanjiru", "Otieno", "Achieng", "Kamau", "Njeri", "Odhiambo",
    "Chebet", "Kiprop", "Amina", "Hassan", "Faith", "Brian",
    "Mercy", "Kevin", "Naomi", "Dennis", "Halima", "Peter",
    "Grace", "Samuel", "Ayan", "Joseph", "Esther", "Abdi",
]
LAST_NAMES = [
    "Mwangi", "Omondi", "Wafula", "Kariuki", "Njoroge", "Atieno",
    "Kimani", "Cheruiyot", "Mohamed", "Ali", "Mutua", "Wambui",
    "Kiptoo", "Nyambura", "Ouma", "Barasa", "Jeptoo", "Maina",
    "Abdullahi", "Gitau", "Akinyi", "Karanja", "Muriuki", "Warsame",
]


def make_candidate(i):
    """Build demo user number i. The same i always gives the same user."""
    first = FIRST_NAMES[i % len(FIRST_NAMES)]
    last = LAST_NAMES[(i * 5) % len(LAST_NAMES)]
    return {
        "name": f"{first} {last}",
        # example.com is reserved for examples, so these emails can never be real
        "email": f"{first}.{last}{i:02d}@gmail.com".lower(),
        # fictional numbers in the format the app requires: +254 and 9 digits
        "phone": f"+254700{100000 + i}",
        # alternate roles so there are about as many landowners as growers
        "role": "landowner" if i % 2 == 1 else "grower",
    }


db = SessionLocal()

current = db.query(models.User).filter(models.User.role != "admin").count()
needed = TARGET_USERS - current
if needed <= 0:
    print(f"The users table already has {current} landowners and growers. Nothing was changed.")
    db.close()
    raise SystemExit

print(f"Found {current} landowners and growers. Will add {needed} demo users.")

# getpass hides what you type, so the password is never shown or saved in a file
password = getpass.getpass("Choose one password for all demo users (8 to 72 characters): ")
confirm = getpass.getpass("Type it again: ")
if password != confirm:
    print("The two passwords did not match. Nothing was changed.")
    db.close()
    raise SystemExit
if not 8 <= len(password.encode("utf-8")) <= 72:
    print("Password must be 8 to 72 characters. Nothing was changed.")
    db.close()
    raise SystemExit

# Remember what already exists so a re-run never creates duplicates
existing_emails = {email for (email,) in db.query(models.User.email)}
existing_phones = {phone for (phone,) in db.query(models.User.phone)}

created = 0
i = 1
while created < needed and i <= 1000:
    candidate = make_candidate(i)
    i += 1
    if candidate["email"] in existing_emails or candidate["phone"] in existing_phones:
        continue  # this demo user is already in the database, try the next one
    db.add(models.User(
        name=candidate["name"],
        email=candidate["email"],
        phone=candidate["phone"],
        hashed_password=hash_password(password),
        role=candidate["role"],
    ))
    created += 1

db.commit()
print(f"Done. Added {created} demo users.")
db.close()