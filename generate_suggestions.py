"""
Add crop suggestions to existing listings that do not have any yet
(for example the sample listings made by seed_listings.py).

  python generate_suggestions.py           every listing without suggestions
  python generate_suggestions.py 5         only the listing with id 5 (good for a first test)

Needs GROQ_API_KEY in the .env file and an internet connection.
Run from the backend folder (venv active).
"""
import sys

from database import SessionLocal
import models
from crop_ai import generate_crop_suggestions, CropSuggestionError

db = SessionLocal()
query = db.query(models.Listing).filter(models.Listing.crop_suggestions.is_(None))
if len(sys.argv) > 1:
    query = db.query(models.Listing).filter(models.Listing.id == int(sys.argv[1]))

listings = query.order_by(models.Listing.id).all()
print(f"{len(listings)} listing(s) to do.")

done = 0
for listing in listings:
    try:
        listing.crop_suggestions = generate_crop_suggestions(listing)
        db.commit()
        done += 1
        print(f"  #{listing.id} {listing.title}: done")
    except CropSuggestionError as error:
        print(f"  #{listing.id} {listing.title}: skipped ({error})")
        if "not set up" in str(error):
            break  # no key: every other listing would fail the same way

db.close()
print(f"Finished. {done} of {len(listings)} done.")