import os
import sys
import datetime
from app import get_firestore

db = get_firestore()
if db:
    print("Seeding Firestore data...")
    
    # 1. Seed Masters & Builder Brands
    masters_ref = db.collection('masters')
    
    masters_ref.document('bhk_options').set({'items': ["1 BHK", "2 BHK", "3 BHK", "4 BHK", "4+ BHK", "Penthouse", "Plot"]})
    masters_ref.document('facing_options').set({'items': ["East", "West", "North", "South", "North-East", "North-West", "South-East", "South-West"]})
    masters_ref.document('zone_options').set({'items': ["East Bengaluru", "South Bengaluru", "North Bengaluru", "West Bengaluru", "Central Bengaluru", "IT Corridor"]})
    masters_ref.document('age_options').set({'items': ["Under Construction", "Ready to Move", "0-1 Year", "1-5 Years", "5-10 Years", "10+ Years"]})
    masters_ref.document('builder_brands').set({'items': [
        "Sobha Developers", "Prestige Group", "Brigade Group", "Godrej Properties", 
        "Puravankara Limited", "Total Environment", "Provident Housing", 
        "Assetz Property Group", "Sattva Group", "Lodha Group"
    ]})

    # 2. Seed Property Listings if empty
    sites_ref = db.collection('sites')
    existing_docs = list(sites_ref.stream())
    
    if len(existing_docs) < 3:
        initial_sites = [
            {
                "title": "Sobha Neopolis",
                "location": "Panathur, Off Marathahalli-Sarjapur ORR",
                "sub_location": "East Bengaluru",
                "price": "₹ 1.65 Cr - ₹ 3.20 Cr",
                "bhk_type": "3 BHK",
                "facing": "East",
                "zone": "East Bengaluru",
                "building_age": "Under Construction",
                "sqft": "1630 - 2361 Sq.Ft",
                "description": "Greek Architecture inspired luxury apartments with world-class amenities in the heart of IT Corridor.",
                "image_filename": "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=1200&q=80",
                "created_at": datetime.datetime.now().isoformat()
            },
            {
                "title": "Prestige Lavender Fields",
                "location": "Varthur, Whitefield",
                "sub_location": "East Bengaluru",
                "price": "₹ 1.20 Cr - ₹ 2.85 Cr",
                "bhk_type": "2 BHK",
                "facing": "North-East",
                "zone": "East Bengaluru",
                "building_age": "Under Construction",
                "sqft": "1275 - 2226 Sq.Ft",
                "description": "Premium high-rise residential towers set amidst sprawling green landscapes and modern amenities.",
                "image_filename": "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=1200&q=80",
                "created_at": datetime.datetime.now().isoformat()
            },
            {
                "title": "Brigade Eldorado",
                "location": "Aerospace Park, KIADB, Bagalur",
                "sub_location": "North Bengaluru",
                "price": "₹ 48 Lakhs - ₹ 85 Lakhs",
                "bhk_type": "2 BHK",
                "facing": "East",
                "zone": "North Bengaluru",
                "building_age": "Ready to Move",
                "sqft": "795 - 1068 Sq.Ft",
                "description": "Integrated smart township with 10+ acres of open green spaces near Kempegowda International Airport.",
                "image_filename": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=1200&q=80",
                "created_at": datetime.datetime.now().isoformat()
            },
            {
                "title": "Godrej Woodscapes",
                "location": "Budigere Cross, Old Madras Road",
                "sub_location": "East Bengaluru",
                "price": "₹ 1.30 Cr - ₹ 2.50 Cr",
                "bhk_type": "3 BHK",
                "facing": "North",
                "zone": "East Bengaluru",
                "building_age": "Under Construction",
                "sqft": "1500 - 2400 Sq.Ft",
                "description": "Nature-first forest themed luxury residential development with expansive clubhouse and sports arenas.",
                "image_filename": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80",
                "created_at": datetime.datetime.now().isoformat()
            },
            {
                "title": "Purva Park Hill",
                "location": "Kanakapura Road",
                "sub_location": "South Bengaluru",
                "price": "₹ 1.50 Cr - ₹ 2.40 Cr",
                "bhk_type": "3 BHK",
                "facing": "East",
                "zone": "South Bengaluru",
                "building_age": "Under Construction",
                "sqft": "1407 - 1936 Sq.Ft",
                "description": "Tri-deck luxury apartments overlooking Turahalli Forest Reserve with BluNex smart home automation.",
                "image_filename": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1200&q=80",
                "created_at": datetime.datetime.now().isoformat()
            },
            {
                "title": "Total Environment In That Quiet Earth",
                "location": "Hennur Main Road",
                "sub_location": "North Bengaluru",
                "price": "₹ 2.10 Cr - ₹ 4.50 Cr",
                "bhk_type": "4 BHK",
                "facing": "East",
                "zone": "North Bengaluru",
                "building_age": "0-1 Year",
                "sqft": "2305 - 3430 Sq.Ft",
                "description": "Handcrafted luxury homes with private terrace gardens and custom timber finishes by Total Environment.",
                "image_filename": "https://images.unsplash.com/photo-1600566753376-12c8ab7fb75b?auto=format&fit=crop&w=1200&q=80",
                "created_at": datetime.datetime.now().isoformat()
            }
        ]

        for s in initial_sites:
            sites_ref.add(s)
        print("Property sites seeded successfully!")

    print("Firestore masters & builder brands updated!")
else:
    print("Could not connect to Firestore.")
