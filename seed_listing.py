"""
Fill the listings table with 20 fictional sample listings around Nairobi.

  python seed_listings.py           add any sample listing that is missing (never changes existing ones)
  python seed_listings.py --reset   delete the existing SAMPLE listings first (it asks you to confirm),
                                    then add them again. Use this after the sample data has been updated.

Only listings with a sample title are ever deleted, never your own listings.
The sample listings are shared between the demo landowners made by seed_users.py
(their phone numbers start with +254700), so run seed_users.py first.

Run from the backend folder (venv active).
"""
import sys
from datetime import date

from sqlalchemy.exc import IntegrityError

from database import SessionLocal
import models
import schemas


# Free-to-use photos from Unsplash (https://unsplash.com/license). Unsplash is built to be linked
# directly: the picture stays on their servers and we only store the link.
def unsplash(photo_id):
    return f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=800&q=70"


PHOTOS = {
    "raised_bed":      unsplash("photo-1591857177580-dc82b9ac4e1e"),  # lettuce in a raised bed
    "veg_rows":        unsplash("photo-1529313780224-1a12b68bed16"),  # rows of leafy vegetables in a garden
    "garden_green":    unsplash("photo-1631981798865-e0216d05b443"),  # a garden full of green plants
    "garden_lush":     unsplash("photo-1641056709258-fbe799d88cdc"),  # another green garden
    "plant_field":     unsplash("photo-1702995878564-17fef6fa4e57"),  # lush field of plants
    "greenhouse":      unsplash("photo-1524486361537-8ad15938e1a3"),  # tomatoes in a greenhouse
    "tomato_rows":     unsplash("photo-1566218246241-934ad8b38ea6"),  # a long row of tomatoes
    "roadside":        unsplash("photo-1615992955236-ec38cbfc6fe2"),  # green plants beside a road
    "field_houses":    unsplash("photo-1734036871909-906fb9b3d474"),  # green field with houses beyond
    "terraces":        unsplash("photo-1761201509055-30c04b68901c"),  # terraced hillside with a water tank
    "terrace_garden":  unsplash("photo-1777821986421-2dc388bd392a"),  # terraced flower and vegetable gardens
    "orchard":         unsplash("photo-1757270828839-9b9d252d5627"),  # rows of orchard trees
    "crop_rows":       unsplash("photo-1560493676-04071c5f467b"),     # rows of crops at sunset
    "crate_garden":    unsplash("photo-1607529107925-04e67ae44b09"),  # green plants in a wooden crate
    "house_yard":      unsplash("photo-1669181120940-21b180f2c3a6"),  # small house with a green yard
    "buildings_grass": unsplash("photo-1461175827210-5ceac3e39dd2"),  # green patch between buildings
    "hills_field":     unsplash("photo-1592650938062-c4cc6ab48951"),  # green field below hills
    "open_field":      unsplash("photo-1586249149466-ab4d39822001"),  # open green field
    "trees_plants":    unsplash("photo-1516906561371-53f48df1254d"),  # green plants near trees
    "dry_shamba":      unsplash("photo-1614531341773-3bff8b7cb3fc"),  # trees on a dry grass field
}

# Each listing is one plain dictionary, so it is easy to read and to edit.
# "photo" is a key from PHOTOS above. Coordinates are approximate centres of real Nairobi-area neighbourhoods.
SAMPLE_LISTINGS = [
    dict(title="Sunny backyard plot", photo="raised_bed", location_name="Kilimani, Nairobi", location_lat=-1.2897, location_lng=36.7872,
         size_acres=0.25, water_availability="Piped water", sunlight="Full sun", soil_info="Loamy",
         description="Fenced backyard behind a quiet residential block. Good for vegetables and herbs.",
         price_type="fixed", price_value=6000, availability_start=date(2026, 11, 1), availability_end=date(2027, 5, 1)),
    dict(title="Quarter acre near the river", photo="garden_green", location_name="Lavington, Nairobi", location_lat=-1.2800, location_lng=36.7700,
         size_acres=0.25, water_availability="River nearby", sunlight="Partial shade", soil_info="Rich dark soil",
         description="Gentle slope beside a small stream. Easy watering all year.",
         price_type="harvest_share", price_value=20, availability_start=date(2026, 11, 15), availability_end=date(2027, 6, 15)),
    dict(title="Open plot with borehole", photo="open_field", location_name="Karen, Nairobi", location_lat=-1.3190, location_lng=36.7070,
         size_acres=1.0, water_availability="Borehole", sunlight="Full sun", soil_info="Red volcanic",
         description="One acre with a working borehole and a small tool shed.",
         price_type="fixed", price_value=14000, availability_start=date(2026, 11, 1), availability_end=date(2027, 11, 1)),
    dict(title="Greenhouse-ready corner", photo="greenhouse", location_name="Runda, Nairobi", location_lat=-1.2180, location_lng=36.8050,
         size_acres=0.5, water_availability="Piped water", sunlight="Full sun", soil_info="Sandy loam",
         description="Flat, levelled corner of a large compound. Owner is happy for a greenhouse.",
         price_type="negotiable", price_value=12000, availability_start=date(2026, 12, 1), availability_end=date(2027, 12, 1)),
    dict(title="Rooftop-adjacent garden space", photo="crate_garden", location_name="Westlands, Nairobi", location_lat=-1.2676, location_lng=36.8108,
         size_acres=0.1, water_availability="Piped water", sunlight="Morning sun", soil_info="Raised beds",
         description="Small courtyard garden with raised beds already built.",
         price_type="fixed", price_value=4000, availability_start=date(2026, 11, 1), availability_end=date(2027, 3, 1)),
    dict(title="One acre off Thika Road", photo="crop_rows", location_name="Kasarani, Nairobi", location_lat=-1.2220, location_lng=36.8960,
         size_acres=1.0, water_availability="Well", sunlight="Full sun", soil_info="Clay loam",
         description="One acre beside the road, easy to reach by matatu. Suited to maize, beans or sukuma wiki.",
         price_type="harvest_share", price_value=30, availability_start=date(2026, 11, 1), availability_end=date(2027, 7, 1)),
    dict(title="Hillside terraces", photo="terraces", location_name="Ruaka, Kiambu", location_lat=-1.2000, location_lng=36.7700,
         size_acres=1.0, water_availability="Rainwater tank", sunlight="Full sun", soil_info="Red volcanic",
         description="Already terraced hillside with good drainage.",
         price_type="fixed", price_value=9000, availability_start=date(2026, 11, 10), availability_end=date(2027, 5, 10)),
    dict(title="Family shamba, shared use", photo="dry_shamba", location_name="Rongai, Kajiado", location_lat=-1.3960, location_lng=36.7440,
         size_acres=1.5, water_availability="Borehole", sunlight="Full sun", soil_info="Sandy",
         description="Part of a family plot. The owner keeps one corner for his own crops.",
         price_type="negotiable", price_value=15000, availability_start=date(2026, 11, 1), availability_end=date(2027, 10, 1)),
    dict(title="Fenced half acre", photo="field_houses", location_name="Kitengela, Kajiado", location_lat=-1.4780, location_lng=36.9500,
         size_acres=0.5, water_availability="Borehole", sunlight="Full sun", soil_info="Black cotton",
         description="Fully fenced with a gate and a night watchman on the compound.",
         price_type="fixed", price_value=7000, availability_start=date(2026, 12, 1), availability_end=date(2027, 6, 1)),
    dict(title="Ngong hills view plot", photo="hills_field", location_name="Ngong, Kajiado", location_lat=-1.3600, location_lng=36.6600,
         size_acres=2.0, water_availability="River nearby", sunlight="Full sun", soil_info="Loamy",
         description="Two acres with a seasonal river. Cool climate, good for potatoes and kale.",
         price_type="harvest_share", price_value=25, availability_start=date(2026, 11, 1), availability_end=date(2027, 11, 1)),
    dict(title="Compound garden", photo="veg_rows", location_name="Juja, Kiambu", location_lat=-1.1020, location_lng=37.0130,
         size_acres=0.3, water_availability="Piped water", sunlight="Full sun", soil_info="Loamy",
         description="Garden strip inside a student-housing compound. Near the university.",
         price_type="fixed", price_value=3500, availability_start=date(2026, 11, 1), availability_end=date(2027, 4, 1)),
    dict(title="Riverside vegetable patch", photo="garden_lush", location_name="Kiambu Town, Kiambu", location_lat=-1.1714, location_lng=36.8356,
         size_acres=0.75, water_availability="River nearby", sunlight="Morning sun", soil_info="Rich dark soil",
         description="Fertile ground beside the river, already used for tomatoes and kale.",
         price_type="negotiable", price_value=8000, availability_start=date(2026, 11, 20), availability_end=date(2027, 5, 20)),
    dict(title="Embakasi roadside plot", photo="buildings_grass", location_name="Embakasi, Nairobi", location_lat=-1.3200, location_lng=36.9000,
         size_acres=0.5, water_availability="Piped water", sunlight="Full sun", soil_info="Clay",
         description="Flat plot between buildings with piped water at the gate.",
         price_type="fixed", price_value=6500, availability_start=date(2026, 12, 1), availability_end=date(2027, 12, 1)),
    dict(title="Syokimau mixed plot", photo="roadside", location_name="Syokimau, Machakos", location_lat=-1.3600, location_lng=36.9380,
         size_acres=1.0, water_availability="Borehole", sunlight="Full sun", soil_info="Sandy loam",
         description="One acre of cleared ground. Suitable for vegetables or fruit trees.",
         price_type="harvest_share", price_value=15, availability_start=date(2026, 11, 1), availability_end=date(2027, 8, 1)),
    dict(title="Langata back garden", photo="house_yard", location_name="Langata, Nairobi", location_lat=-1.3600, location_lng=36.7500,
         size_acres=0.2, water_availability="Piped water", sunlight="Partial shade", soil_info="Loamy",
         description="Quiet back garden. Compost bins are already on site.",
         price_type="fixed", price_value=5000, availability_start=date(2026, 11, 5), availability_end=date(2027, 5, 5)),
    dict(title="Ruiru backyard shamba", photo="plant_field", location_name="Ruiru, Kiambu", location_lat=-1.1500, location_lng=36.9600,
         size_acres=0.4, water_availability="Well", sunlight="Full sun", soil_info="Red volcanic",
         description="Small shamba behind a family home. Already planted with sukuma wiki and spinach.",
         price_type="negotiable", price_value=5500, availability_start=date(2026, 11, 1), availability_end=date(2027, 9, 1)),
    dict(title="Kahawa shared compound", photo="tomato_rows", location_name="Kahawa, Nairobi", location_lat=-1.1800, location_lng=36.9300,
         size_acres=0.4, water_availability="Rainwater tank", sunlight="Full sun", soil_info="Loamy",
         description="Part of a shared compound. Neighbours already grow vegetables here.",
         price_type="fixed", price_value=4500, availability_start=date(2026, 12, 1), availability_end=date(2027, 6, 1)),
    dict(title="Limuru highland plot", photo="terrace_garden", location_name="Limuru, Kiambu", location_lat=-1.1070, location_lng=36.6420,
         size_acres=2.0, water_availability="River nearby", sunlight="Partial shade", soil_info="Volcanic loam",
         description="Cool highland climate. Good for peas, carrots and flowers.",
         price_type="harvest_share", price_value=35, availability_start=date(2026, 11, 1), availability_end=date(2027, 11, 1)),
    dict(title="Mlolongo corner plot", photo="trees_plants", location_name="Mlolongo, Machakos", location_lat=-1.3950, location_lng=36.9400,
         size_acres=0.6, water_availability="Borehole", sunlight="Full sun", soil_info="Sandy",
         description="Corner plot with road access on two sides.",
         price_type="fixed", price_value=6500, availability_start=date(2026, 11, 15), availability_end=date(2027, 5, 15)),
    dict(title="Kikuyu orchard land", photo="orchard", location_name="Kikuyu, Kiambu", location_lat=-1.2460, location_lng=36.6630,
         size_acres=1.2, water_availability="Piped water", sunlight="Full sun", soil_info="Red volcanic",
         description="Old orchard land with room for new rows. Avocado trees on one side.",
         price_type="negotiable", price_value=10000, availability_start=date(2026, 11, 1), availability_end=date(2027, 10, 1)),
]

# Titles used by an earlier version of this file. --reset removes them too.
RETIRED_TITLES = {"Two acres off Thika Road", "Airport road open land", "Ruiru farm strip"}

# Two of the sample listings are shown as already booked, so the "Booked" state is visible in the app
BOOKED_TITLES = {"Open plot with borehole", "Riverside vegetable patch"}


def main():
    db = SessionLocal()

    sample_titles = {item["title"] for item in SAMPLE_LISTINGS} | RETIRED_TITLES
    old_rows = db.query(models.Listing).filter(models.Listing.title.in_(sample_titles)).all()

    if "--reset" in sys.argv:
        print(f"This will DELETE {len(old_rows)} sample listings (only the ones with a sample title).")
        if input("Type yes to continue: ").strip().lower() != "yes":
            print("Cancelled. Nothing was changed.")
            db.close()
            return
        for row in old_rows:
            db.delete(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            print("Some sample listings are used by bookings and cannot be deleted. Nothing was changed.")
            db.close()
            return
        print(f"Deleted {len(old_rows)} sample listings.")
    elif any(row.title in RETIRED_TITLES for row in old_rows):
        print("Older sample listings are in the database. Run:  python seed_listings.py --reset")
        print("Nothing was changed.")
        db.close()
        return

    # The demo landowners made by seed_users.py have phone numbers starting +254700
    owners = (
        db.query(models.User)
        .filter(models.User.role == "landowner", models.User.phone.like("+254700%"))
        .order_by(models.User.id)
        .all()
    )
    if not owners:
        print("No demo landowners found. Run seed_users.py first. Nothing was changed.")
        db.close()
        return

    existing_titles = {title for (title,) in db.query(models.Listing.title)}

    created = 0
    for index, item in enumerate(SAMPLE_LISTINGS):
        if item["title"] in existing_titles:
            continue  # already in the database

        fields = {key: value for key, value in item.items() if key != "photo"}
        # Same rules the real API uses. A bad sample would fail here, not silently get saved.
        checked = schemas.ListingCreate(**fields, photo_url=PHOTOS[item["photo"]])

        owner = owners[index % len(owners)]  # take turns between the landowners
        db.add(models.Listing(
            **checked.model_dump(),
            owner_id=owner.id,
            status="reserved" if item["title"] in BOOKED_TITLES else "available",
        ))
        created += 1

    db.commit()
    print(f"Done. Added {created} sample listings.")
    db.close()


main()