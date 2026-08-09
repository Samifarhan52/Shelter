import os
import datetime
import urllib.parse
import json
import base64
import re
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    firebase_admin = None
    credentials = None
    firestore = None
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "shelter_hunt_secret_key_2026")

db = None

def get_firestore():
    global db
    if db is not None:
        return db
    try:
        if not firebase_admin._apps:
            cred_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
            if cred_json:
                cred_dict = json.loads(cred_json)
                cred = credentials.Certificate(cred_dict)
            elif os.path.exists("firebase_key.json"):
                cred = credentials.Certificate("firebase_key.json")
            else:
                print("Warning: Firebase service account credentials not found!")
                return None
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        return db
    except Exception as e:
        print(f"Firebase connection error: {e}")
        return None

# Real-Time Visitor Tracking Hook
@app.before_request
def track_website_activity():
    path = request.path
    if path.startswith('/static') or path.startswith('/admin') or path in ['/submit-quick-lead', '/check-availability', '/admin/bulk-add-sites']:
        return

    if 'visitor_session_id' not in session:
        session['visitor_session_id'] = os.urandom(12).hex()

    firestore_db = get_firestore()
    if firestore_db:
        try:
            today_str = datetime.date.today().isoformat()
            now_iso = datetime.datetime.now().isoformat()
            user_agent = request.user_agent.string
            device = "Mobile" if ("Mobile" in user_agent or "Android" in user_agent or "iPhone" in user_agent) else "Desktop"

            firestore_db.collection('page_views').add({
                'path': path,
                'visit_date': today_str,
                'timestamp': now_iso,
                'visitor_session': session['visitor_session_id'],
                'device': device,
                'ip': request.remote_addr or '127.0.0.1'
            })
        except Exception as e:
            print(f"Tracking error: {e}")

# Unified Data Storage Layer
DATA_FILE = os.path.join(os.path.dirname(__file__), "data_store.json")

def load_local_store():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading local data store: {e}")
    return {
        'settings': {},
        'masters': {},
        'sites': [],
        'post_site_leads': []
    }

def save_local_store(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving local data store: {e}")

# Helper Functions
def get_bhk_options():
    defaults = ["1 BHK", "2 BHK", "3 BHK", "4 BHK", "4+ BHK"]
    local_store = load_local_store()
    if local_store.get('masters', {}).get('bhk_options'):
        return local_store['masters']['bhk_options']
    firestore_db = get_firestore()
    if firestore_db:
        try:
            docs = firestore_db.collection('masters').document('bhk_options').get()
            if docs.exists:
                custom = docs.to_dict().get('items', [])
                if custom:
                    return custom
        except Exception:
            pass
    return defaults

def get_facing_options():
    defaults = ["East", "West", "North", "South", "North-East", "North-West", "South-East", "South-West"]
    local_store = load_local_store()
    if local_store.get('masters', {}).get('facing_options'):
        return local_store['masters']['facing_options']
    firestore_db = get_firestore()
    if firestore_db:
        try:
            docs = firestore_db.collection('masters').document('facing_options').get()
            if docs.exists:
                custom = docs.to_dict().get('items', [])
                if custom:
                    return custom
        except Exception:
            pass
    return defaults

def get_zone_options():
    defaults = ["North Bengaluru", "South Bengaluru", "East Bengaluru", "West Bengaluru", "Central Bengaluru", "IT Corridor"]
    local_store = load_local_store()
    if local_store.get('masters', {}).get('zone_options'):
        return local_store['masters']['zone_options']
    firestore_db = get_firestore()
    if firestore_db:
        try:
            docs = firestore_db.collection('masters').document('zone_options').get()
            if docs.exists:
                custom = docs.to_dict().get('items', [])
                if custom:
                    return custom
        except Exception:
            pass
    return defaults

def get_age_options():
    defaults = ["Under Construction", "Ready to Move", "0-1 Year", "1-5 Years", "5-10 Years", "10+ Years"]
    local_store = load_local_store()
    if local_store.get('masters', {}).get('age_options'):
        return local_store['masters']['age_options']
    firestore_db = get_firestore()
    if firestore_db:
        try:
            docs = firestore_db.collection('masters').document('age_options').get()
            if docs.exists:
                custom = docs.to_dict().get('items', [])
                if custom:
                    return custom
        except Exception:
            pass
    return defaults

def get_site_settings():
    defaults = {
        'brand_name': 'SHELTER HUNT',
        'brand_tagline': 'CONSULTANTS',
        'brand_logo': '',
        'whatsapp_number': '918050749331',
        'contact_phone': '+91 8050749331',
        'contact_email': 'contact@shelterhunt.com',
        'contact_address': '58, opposite ganesh temple, Carmelaram, Chikkabellandur, Bengaluru, Karnataka 560035',
        'hero_title': 'Smart Property Decisions Start Here.',
        'hero_subtitle': "We don't push properties — we listen, research, and match you with the right one. Expert consultation that puts your requirements first, every single time.",
        'philosophy_text': 'Shelter Hunt Consultants is a knowledge-first agency built on the belief that real estate decisions deserve expert guidance, not sales pressure.',
        'about_tagline': 'Our Philosophy & Expertise',
        'footer_copyright': '© 2026 Shelter Hunt Consultants. All rights reserved.',
        'meta_title': 'Shelter Hunt Consultants | Premium Real Estate Advisory Bengaluru',
        'meta_description': 'Verified premium property listings, site visit coordination, and unbiased property advisory across Bengaluru.',
        'meta_keywords': 'Real Estate Bengaluru, Property Consultation, 2 BHK Apartments, 3 BHK Flats, Shelter Hunt',
        'ga_tracking_id': '',
        'meta_pixel_id': '',
        'social_facebook': '',
        'social_instagram': '',
        'social_linkedin': '',
        'social_youtube': '',
        'google_maps_embed_url': 'https://maps.google.com/maps?q=58,+opposite+ganesh+temple,+Carmelaram,+Chikkabellandur,+Bengaluru,+Karnataka+560035&t=&z=15&ie=UTF8&iwloc=&output=embed'
    }
    
    # 1. Local Persistence Store Overrides
    local_store = load_local_store()
    if local_store.get('settings'):
        for k, v in local_store['settings'].items():
            if v != '':
                defaults[k] = v

    # 2. Firestore Database Overrides
    firestore_db = get_firestore()
    if firestore_db:
        try:
            docs = firestore_db.collection('settings').stream()
            for d in docs:
                d_dict = d.to_dict()
                if 'value' in d_dict:
                    val = d_dict['value']
                    if val != '':
                        defaults[d.id] = val
        except Exception as e:
            print(f"Error loading live settings: {e}")
            
    return defaults

def get_builder_brands():
    defaults = [
        "Sobha Developers", "Prestige Group", "Brigade Group", "Godrej Properties", 
        "Puravankara Limited", "Total Environment", "Provident Housing", 
        "Assetz Property Group", "Sattva Group", "Lodha Group"
    ]
    local_store = load_local_store()
    if local_store.get('masters', {}).get('builder_brands'):
        return local_store['masters']['builder_brands']
    firestore_db = get_firestore()
    if firestore_db:
        try:
            docs = firestore_db.collection('masters').document('builder_brands').get()
            if docs.exists:
                custom = docs.to_dict().get('items', [])
                if custom:
                    return custom
        except Exception:
            pass
    return defaults

def get_default_sites():
    return [
        {
            "id": "sobha-neopolis-1",
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
            "image_filename": "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=1200&q=80"
        },
        {
            "id": "prestige-lavender-2",
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
            "image_filename": "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=1200&q=80"
        },
        {
            "id": "brigade-eldorado-3",
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
            "image_filename": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=1200&q=80"
        },
        {
            "id": "godrej-woodscapes-4",
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
            "image_filename": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80"
        },
        {
            "id": "purva-park-hill-5",
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
            "image_filename": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1200&q=80"
        },
        {
            "id": "total-environment-6",
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
            "image_filename": "https://images.unsplash.com/photo-1600566753376-12c8ab7fb75b?auto=format&fit=crop&w=1200&q=80"
        }
    ]

def get_all_sites():
    all_sites = []
    
    # 1. Stream from Firestore Database
    firestore_db = get_firestore()
    if firestore_db:
        try:
            sites_ref = firestore_db.collection('sites').stream()
            for d in sites_ref:
                data = d.to_dict()
                data['id'] = d.id
                all_sites.append(data)
        except Exception as e:
            print(f"Error streaming sites from Firestore: {e}")
            
    # 2. Merge Local Store
    local_store = load_local_store()
    local_sites = local_store.get('sites', [])
    existing_ids = {s.get('id') for s in all_sites}
    for ls in local_sites:
        if ls.get('id') not in existing_ids:
            all_sites.append(ls)
            
    # 3. Merge Default Portfolio
    if not all_sites:
        all_sites = get_default_sites()
    else:
        existing_ids = {s.get('id') for s in all_sites}
        for d_site in get_default_sites():
            if d_site['id'] not in existing_ids:
                all_sites.append(d_site)
                
    return all_sites

# Global Template Context Processor
@app.context_processor
def inject_global_data():
    return {
        'settings': get_site_settings(),
        'bhk_options': get_bhk_options(),
        'facing_options': get_facing_options(),
        'zone_options': get_zone_options(),
        'age_options': get_age_options(),
        'builder_brands': get_builder_brands()
    }

def get_daily_slots():
    return [
        "09:00 AM", "09:30 AM", "10:00 AM", "10:30 AM", "11:00 AM", "11:30 AM",
        "12:00 PM", "12:30 PM", "01:00 PM", "01:30 PM", "02:00 PM", "02:30 PM",
        "03:00 PM", "03:30 PM", "04:00 PM", "04:30 PM", "05:00 PM", "05:30 PM",
        "06:00 PM", "06:30 PM", "07:00 PM"
    ]

# --- Public Routes ---
@app.route('/')
def home():
    all_sites = get_all_sites()
    return render_template('index.html', sites=all_sites[:6], bhk_options=get_bhk_options(), settings=get_site_settings())

@app.route('/sites')
def sites():
    query = request.args.get('q', '').strip().lower()
    bhk_filter = request.args.get('bhk', '').strip()
    facing_filter = request.args.get('facing', '').strip()
    zone_filter = request.args.get('zone', '').strip()
    age_filter = request.args.get('age', '').strip()
    
    # Require active search parameter or filter to display property listings
    has_searched = bool(query or (bhk_filter and bhk_filter.lower() != 'all') or 
                        (facing_filter and facing_filter.lower() != 'all') or 
                        (zone_filter and zone_filter.lower() != 'all') or 
                        (age_filter and age_filter.lower() != 'all'))
    
    all_properties = get_all_sites()
                
    sites_list = []
    recommendations = []
    
    if has_searched:
        q_tokens = [t for t in query.lower().replace(',', ' ').split() if len(t) > 0] if query else []
        
        for data in all_properties:
            title = str(data.get('title', '')).lower()
            location = str(data.get('location', '')).lower()
            sub_location = str(data.get('sub_location', '')).lower()
            description = str(data.get('description', '')).lower()
            bhk_type = str(data.get('bhk_type', '')).lower()
            facing = str(data.get('facing', '')).lower()
            zone = str(data.get('zone', '')).lower()
            building_age = str(data.get('building_age', '')).lower()
            
            searchable_text = f"{title} {location} {sub_location} {description} {bhk_type} {facing} {zone} {building_age}"
            
            matches_q = True
            if q_tokens:
                # Property matches if ANY token matches searchable text
                matches_q = any(token in searchable_text for token in q_tokens)
                
            matches_bhk = True
            if bhk_filter and bhk_filter.lower() != 'all':
                matches_bhk = (bhk_filter.lower() in bhk_type)

            matches_facing = True
            if facing_filter and facing_filter.lower() != 'all':
                matches_facing = (facing_filter.lower() == facing)

            matches_zone = True
            if zone_filter and zone_filter.lower() != 'all':
                matches_zone = (zone_filter.lower() in zone or zone_filter.lower() in location or zone_filter.lower() in sub_location)

            matches_age = True
            if age_filter and age_filter.lower() != 'all':
                matches_age = (age_filter.lower() == building_age)
                
            if matches_q and matches_bhk and matches_facing and matches_zone and matches_age:
                sites_list.append(data)
                
        # If active search yielded 0 matches, provide recommendations from default sites
        if not sites_list:
            recommendations = get_default_sites()
            
    return render_template('sites.html', 
                           sites=sites_list,
                           recommendations=recommendations,
                           has_searched=has_searched,
                           bhk_options=get_bhk_options(),
                           facing_options=get_facing_options(),
                           zone_options=get_zone_options(),
                           age_options=get_age_options(),
                           settings=get_site_settings(), 
                           search_query=query, 
                           selected_bhk=bhk_filter,
                           selected_facing=facing_filter,
                           selected_zone=zone_filter,
                           selected_age=age_filter)

@app.route('/site/<string:site_id>')
def site_detail(site_id):
    firestore_db = get_firestore()
    if firestore_db:
        try:
            doc = firestore_db.collection('sites').document(site_id).get()
            if doc.exists:
                site_data = doc.to_dict()
                site_data['id'] = doc.id
                return render_template('site_detail.html', site=site_data, bhk_options=get_bhk_options(), settings=get_site_settings())
        except Exception as e:
            print(f"Error fetching site details: {e}")
            
    # Check default fallback sites
    for default_site in get_default_sites():
        if default_site['id'] == site_id:
            return render_template('site_detail.html', site=default_site, bhk_options=get_bhk_options(), settings=get_site_settings())
            
    flash("Property site not found.", "warning")
    return redirect(url_for('sites'))

@app.route('/about')
def about():
    return render_template('about.html', bhk_options=get_bhk_options(), settings=get_site_settings())

@app.route('/services')
def services():
    return render_template('services.html', bhk_options=get_bhk_options(), settings=get_site_settings())

@app.route('/submit-quick-lead', methods=['POST'])
def submit_quick_lead():
    full_name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    
    digits_only = re.sub(r'\D', '', phone)
    if not full_name or len(digits_only) != 10:
        return jsonify({'success': False, 'message': 'Please provide a valid full name and exactly 10-digit mobile number.'}), 400

    settings = get_site_settings()
    target_wa = settings.get('whatsapp_number', '918050749331').replace('+', '').replace(' ', '')

    firestore_db = get_firestore()
    if firestore_db:
        try:
            firestore_db.collection('sessions').add({
                'session_date': datetime.date.today().isoformat(),
                'slot_time': 'Quick Lead Callback',
                'full_name': full_name,
                'email': email or 'N/A',
                'phone': digits_only,
                'location': 'General Inquiry',
                'budget': 'N/A',
                'message': 'Quick Lead Callback requested via Website Popup',
                'status': 'Confirmed',
                'booked_at': datetime.datetime.now().isoformat()
            })
        except Exception as e:
            print(f"Quick lead save error: {e}")

    wa_text = (
        f"Hello Shelter Hunt Consultants!\n\n"
        f"I would like to request a callback for property consultation.\n\n"
        f"📌 *Contact Details:*\n"
        f"• *Name:* {full_name}\n"
        f"• *Phone:* {digits_only}\n"
        f"• *Email:* {email if email else 'N/A'}\n\n"
        f"Please connect with me shortly. Thank you!"
    )
    encoded_message = urllib.parse.quote(wa_text)
    whatsapp_url = f"https://wa.me/{target_wa}?text={encoded_message}"

    return jsonify({'success': True, 'whatsapp_url': whatsapp_url})

@app.route('/book-session')
def booking_slots():
    today_str = datetime.date.today().isoformat()
    selected_date = request.args.get('date', today_str)
    
    if selected_date < today_str:
        selected_date = today_str

    all_slots = get_daily_slots()
    booked_slots = []
    
    firestore_db = get_firestore()
    if firestore_db:
        try:
            sessions_ref = firestore_db.collection('sessions').where('session_date', '==', selected_date).stream()
            for s in sessions_ref:
                s_data = s.to_dict()
                if s_data.get('status', 'Confirmed') == 'Confirmed':
                    booked_slots.append(s_data.get('slot_time'))
        except Exception:
            pass
    
    return render_template('booking.html', date=selected_date, today=today_str, all_slots=all_slots, booked_slots=booked_slots, bhk_options=get_bhk_options(), settings=get_site_settings())

@app.route('/check-availability', methods=['GET'])
def check_availability():
    slot = request.args.get('slot')
    current_date = request.args.get('date', datetime.date.today().isoformat())
    recommendations = []
    
    firestore_db = get_firestore()
    if firestore_db:
        try:
            check_date = datetime.date.fromisoformat(current_date)
            for i in range(1, 15):
                check_date += datetime.timedelta(days=1)
                date_str = check_date.isoformat()
                
                query = firestore_db.collection('sessions').where('session_date', '==', date_str).where('slot_time', '==', slot).limit(1).stream()
                docs = list(query)
                if not docs or docs[0].to_dict().get('status') == 'Cancelled':
                    recommendations.append(date_str)
                    if len(recommendations) >= 3:
                        break
        except Exception:
            pass
        
    return {"slot": slot, "recommendations": recommendations}

@app.route('/confirm-booking', methods=['POST'])
def confirm_booking():
    session_date = request.form.get('session_date')
    slot_time = request.form.get('slot_time')
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    message = request.form.get('message', '').strip()
    
    digits_only = re.sub(r'\D', '', phone)
    if len(digits_only) != 10:
        flash("Please enter a valid 10-digit mobile number.", "danger")
        return redirect(url_for('booking_slots', date=session_date))

    today_str = datetime.date.today().isoformat()
    if session_date < today_str:
        flash("Cannot book consultation slots for past dates.", "danger")
        return redirect(url_for('booking_slots'))

    settings = get_site_settings()
    target_wa = settings.get('whatsapp_number', '918050749331').replace('+', '').replace(' ', '')

    firestore_db = get_firestore()
    if firestore_db:
        try:
            existing = firestore_db.collection('sessions').where('session_date', '==', session_date).where('slot_time', '==', slot_time).limit(1).stream()
            docs = list(existing)
            if docs and docs[0].to_dict().get('status', 'Confirmed') == 'Confirmed':
                flash(f"Sorry! The {slot_time} slot on {session_date} was just booked by someone else. Please choose another slot.", "warning")
                return redirect(url_for('booking_slots', date=session_date))

            firestore_db.collection('sessions').add({
                'session_date': session_date,
                'slot_time': slot_time,
                'full_name': full_name,
                'email': email,
                'phone': digits_only,
                'location': 'General Property Advisory',
                'budget': 'N/A',
                'message': message,
                'status': 'Confirmed',
                'booked_at': datetime.datetime.now().isoformat()
            })
        except Exception as e:
            print(f"Booking save error: {e}")

    wa_text = (
        f"Hello Shelter Hunt Consultants!\n\n"
        f"I have just booked a Property Strategy Session on your website.\n\n"
        f"📌 *Booking Details:*\n"
        f"• *Date:* {session_date}\n"
        f"• *Slot Time:* {slot_time}\n"
        f"• *Name:* {full_name}\n"
        f"• *Phone:* {digits_only}\n"
        f"• *Email:* {email if email else 'N/A'}\n"
    )
    if message:
        wa_text += f"• *Notes/Requirements:* {message}\n"
        
    wa_text += "\nPlease confirm my appointment slot. Thank you!"

    encoded_message = urllib.parse.quote(wa_text)
    whatsapp_url = f"https://wa.me/{target_wa}?text={encoded_message}"
    
    return redirect(whatsapp_url)

@app.route('/post-your-site')
def post_your_site():
    return render_template('post_site.html', 
                           settings=get_site_settings(), 
                           zone_options=get_zone_options(),
                           bhk_options=get_bhk_options())

@app.route('/submit-post-site-lead', methods=['POST'])
def submit_post_site_lead():
    try:
        data = request.get_json() or request.form
        full_name = str(data.get('name', '')).strip()
        email = str(data.get('email', '')).strip()
        phone = str(data.get('phone', '')).strip()
        location = str(data.get('location', '')).strip()
        site_type = str(data.get('site_type', '')).strip()
        price = str(data.get('price', '')).strip()
        sqft = str(data.get('sqft', '')).strip()
        rate_per_sqft = str(data.get('rate_per_sqft', '')).strip()
        floor_info = str(data.get('floor_info', '')).strip()
        zone = str(data.get('zone', '')).strip()
        notes = str(data.get('notes', '')).strip()

        digits_only = re.sub(r'\D', '', phone)
        if not full_name:
            return jsonify({'success': False, 'message': 'Please enter your full name.'}), 400
        if not email or '@' not in email:
            return jsonify({'success': False, 'message': 'Please enter a valid email address.'}), 400
        if len(digits_only) != 10:
            return jsonify({'success': False, 'message': 'Please enter a valid 10-digit mobile number.'}), 400
        if not location:
            return jsonify({'success': False, 'message': 'Please enter the site location/address.'}), 400

        now_iso = datetime.datetime.now().isoformat()
        firestore_db = get_firestore()
        if firestore_db:
            try:
                firestore_db.collection('post_site_leads').add({
                    'name': full_name,
                    'email': email,
                    'phone': digits_only,
                    'location': location,
                    'site_type': site_type or 'Apartment',
                    'price': price,
                    'sqft': sqft,
                    'rate_per_sqft': rate_per_sqft,
                    'floor_info': floor_info,
                    'zone': zone,
                    'notes': notes,
                    'submitted_at': now_iso,
                    'status': 'New'
                })
            except Exception as e:
                print(f"Error storing post site lead: {e}")

        return jsonify({
            'success': True, 
            'message': 'Thank you! Your property listing application has been submitted successfully to our Admin team. Our executive team will review your site details and contact you shortly.'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# CMS Admin Control Panel
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    firestore_db = get_firestore()
    
    if request.method == 'POST' and ('login' in request.form or 'master_login' in request.form):
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        master_key = request.form.get('master_key', '').strip()
        
        # 1. Master Security Recovery Bypass (ElavateX)
        if master_key == 'ElavateX':
            session['admin_logged_in'] = True
            session['force_password_reset'] = True
            flash("🔑 Master Recovery Access Granted! Please enter and update your new Admin Password below.", "success")
            return redirect(url_for('admin', tab='settings', reset='1'))
        
        # 2. Standard Admin Login with Firestore Database Password
        if firestore_db:
            try:
                # Retrieve admin user document from Firestore
                doc = firestore_db.collection('users').document('admin@shelterhunt.com').get()
                if not doc.exists and email:
                    doc = firestore_db.collection('users').document(email).get()
                
                if doc.exists:
                    user = doc.to_dict()
                    stored_pwd = user.get('password', '')
                    if stored_pwd and (check_password_hash(stored_pwd, password) or stored_pwd == password):
                        session['admin_logged_in'] = True
                        return redirect(url_for('admin'))
                    else:
                        flash("Invalid Admin Credentials.", "danger")
                        return render_template('admin_login.html')
            except Exception as e:
                print(f"Login error: {e}")
        
        # Initial setup fallback ONLY if no user document has been created yet in Firestore
        if email == 'admin@shelterhunt.com' and password == 'David!234':
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
            
        flash("Invalid Admin Credentials.", "danger")

    if session.get('admin_logged_in'):
        leads, post_site_leads, sites_list = [], [], []
        analytics = {
            'total_views': 0,
            'today_views': 0,
            'today_unique': 0,
            'page_breakdown': {},
            'recent_views': []
        }

        if firestore_db:
            try:
                leads_docs = firestore_db.collection('sessions').stream()
                for l in leads_docs:
                    d = l.to_dict()
                    d['id'] = l.id
                    leads.append(d)
                leads.sort(key=lambda x: x.get('booked_at', ''), reverse=True)

                ps_docs = firestore_db.collection('post_site_leads').stream()
                for p in ps_docs:
                    d = p.to_dict()
                    d['id'] = p.id
                    post_site_leads.append(d)
                post_site_leads.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)

                sites_docs = firestore_db.collection('sites').stream()
                for s in sites_docs:
                    d = s.to_dict()
                    d['id'] = s.id
                    sites_list.append(d)
                if not sites_list:
                    sites_list = get_default_sites()

                today_str = datetime.date.today().isoformat()
                views_ref = firestore_db.collection('page_views').stream()
                
                unique_sessions_today = set()
                page_counts = {}
                recent_logs = []

                for v in views_ref:
                    v_data = v.to_dict()
                    analytics['total_views'] += 1

                    v_date = v_data.get('visit_date', '')
                    v_path = v_data.get('path', '/')

                    if v_date == today_str:
                        analytics['today_views'] += 1
                        unique_sessions_today.add(v_data.get('visitor_session', ''))
                        page_counts[v_path] = page_counts.get(v_path, 0) + 1

                    recent_logs.append(v_data)

                analytics['today_unique'] = len(unique_sessions_today)
                analytics['page_breakdown'] = page_counts
                
                recent_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                analytics['recent_views'] = recent_logs[:20]

            except Exception as e:
                print(f"Admin fetch error: {e}")
        
        if not sites_list:
            sites_list = get_default_sites()
        
        force_reset = session.get('force_password_reset', False) or request.args.get('reset') == '1'
        
        return render_template('admin.html', 
                               leads=leads, 
                               post_site_leads=post_site_leads,
                               sites=sites_list, 
                               bhk_options=get_bhk_options(),
                               facing_options=get_facing_options(),
                               zone_options=get_zone_options(),
                               age_options=get_age_options(),
                               analytics=analytics, 
                               settings=get_site_settings(),
                               force_reset=force_reset)
        
    return render_template('admin_login.html')

@app.route('/admin/save-settings', methods=['POST'])
def admin_save_settings():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    settings_data = {
        'brand_name': request.form.get('brand_name', 'SHELTER HUNT').strip(),
        'brand_tagline': request.form.get('brand_tagline', 'CONSULTANTS').strip(),
        'whatsapp_number': request.form.get('whatsapp_number', '918050749331').strip(),
        'contact_phone': request.form.get('contact_phone', '+91 8050749331').strip(),
        'contact_email': request.form.get('contact_email', 'contact@shelterhunt.com').strip(),
        'contact_address': request.form.get('contact_address', 'Bengaluru, Karnataka, India').strip(),
        'hero_title': request.form.get('hero_title', 'Smart Property Decisions Start Here.').strip(),
        'hero_subtitle': request.form.get('hero_subtitle', '').strip(),
        'philosophy_text': request.form.get('philosophy_text', '').strip(),
        'about_tagline': request.form.get('about_tagline', '').strip(),
        'footer_copyright': request.form.get('footer_copyright', '').strip(),
        'meta_title': request.form.get('meta_title', '').strip(),
        'meta_description': request.form.get('meta_description', '').strip(),
        'meta_keywords': request.form.get('meta_keywords', '').strip(),
        'ga_tracking_id': request.form.get('ga_tracking_id', '').strip(),
        'meta_pixel_id': request.form.get('meta_pixel_id', '').strip(),
        'social_facebook': request.form.get('social_facebook', '').strip(),
        'social_instagram': request.form.get('social_instagram', '').strip(),
        'social_linkedin': request.form.get('social_linkedin', '').strip(),
        'social_youtube': request.form.get('social_youtube', '').strip(),
        'google_maps_embed_url': request.form.get('google_maps_embed_url', '').strip()
    }
    
    # Check for Logo File Upload
    brand_logo = request.form.get('brand_logo_url', '').strip()
    if 'logo_file' in request.files:
        file = request.files['logo_file']
        if file and file.filename != '':
            file_bytes = file.read()
            if len(file_bytes) > 0:
                mime_type = file.mimetype or 'image/jpeg'
                encoded = base64.b64encode(file_bytes).decode('utf-8')
                brand_logo = f"data:{mime_type};base64,{encoded}"
    
    if brand_logo:
        settings_data['brand_logo'] = brand_logo
    
    # 1. Update Local Store
    local_store = load_local_store()
    if 'settings' not in local_store:
        local_store['settings'] = {}
    for k, v in settings_data.items():
        local_store['settings'][k] = v
    save_local_store(local_store)

    # 2. Update Firestore Database
    firestore_db = get_firestore()
    if firestore_db:
        try:
            for key, val in settings_data.items():
                firestore_db.collection('settings').document(key).set({'value': val})
        except Exception as e:
            print(f"Error saving settings to Firestore: {e}")

    flash("Global site settings, logo, branding, and integrations updated successfully across live website!", "success")
    return redirect(url_for('admin'))

@app.route('/admin/add-master-option', methods=['POST'])
def admin_add_master_option():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    master_type = request.form.get('master_type', '').strip()
    new_val = request.form.get('option_value', '').strip()
    
    if master_type and new_val:
        # 1. Update Local Store
        local_store = load_local_store()
        if 'masters' not in local_store:
            local_store['masters'] = {}
        if master_type not in local_store['masters']:
            local_store['masters'][master_type] = []
        if new_val not in local_store['masters'][master_type]:
            local_store['masters'][master_type].append(new_val)
        save_local_store(local_store)

        # 2. Update Firestore
        firestore_db = get_firestore()
        if firestore_db:
            try:
                doc_ref = firestore_db.collection('masters').document(master_type)
                doc = doc_ref.get()
                items = doc.to_dict().get('items', []) if doc.exists else []
                if new_val not in items:
                    items.append(new_val)
                    doc_ref.set({'items': items})
            except Exception as e:
                print(f"Error adding master option to Firestore: {e}")
                
        flash(f"Added '{new_val}' to master configurations.", "success")
                
    return redirect(url_for('admin'))

@app.route('/admin/delete-master-option', methods=['POST'])
def admin_delete_master_option():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    master_type = request.form.get('master_type', '').strip()
    target_val = request.form.get('option_value', '').strip()
    
    if master_type and target_val:
        # 1. Update Local Store
        local_store = load_local_store()
        if 'masters' in local_store and master_type in local_store['masters']:
            local_store['masters'][master_type] = [i for i in local_store['masters'][master_type] if i != target_val]
            save_local_store(local_store)

        # 2. Update Firestore
        firestore_db = get_firestore()
        if firestore_db:
            try:
                doc_ref = firestore_db.collection('masters').document(master_type)
                doc = doc_ref.get()
                if doc.exists:
                    items = doc.to_dict().get('items', [])
                    items = [i for i in items if i != target_val]
                    doc_ref.set({'items': items})
            except Exception as e:
                print(f"Error deleting master option from Firestore: {e}")

        flash(f"Removed '{target_val}' from master configurations.", "info")
                
    return redirect(url_for('admin'))

@app.route('/admin/change-password', methods=['POST'])
def admin_change_password():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()
    
    if not new_password or new_password != confirm_password:
        flash("Passwords do not match or field is empty.", "warning")
        return redirect(url_for('admin'))
        
    firestore_db = get_firestore()
    if firestore_db:
        try:
            hashed_pwd = generate_password_hash(new_password)
            firestore_db.collection('users').document('admin@shelterhunt.com').set({
                'password': hashed_pwd,
                'name': 'Admin',
                'email': 'admin@shelterhunt.com',
                'updated_at': datetime.datetime.now().isoformat()
            })
            session.pop('force_password_reset', None)
            flash("Admin account password successfully updated!", "success")
        except Exception as e:
            print(f"Error updating password: {e}")
            flash(f"Could not update password: {e}", "danger")
    else:
        flash("Database connection unavailable. Password not updated.", "danger")
        
    return redirect(url_for('admin'))

@app.route('/admin/toggle-session/<string:session_id>')
def admin_toggle_session(session_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    firestore_db = get_firestore()
    if firestore_db:
        try:
            doc_ref = firestore_db.collection('sessions').document(session_id)
            doc = doc_ref.get()
            if doc.exists:
                current_status = doc.to_dict().get('status', 'Confirmed')
                new_status = 'Cancelled' if current_status == 'Confirmed' else 'Confirmed'
                doc_ref.update({'status': new_status})
                flash(f"Booking status updated to {new_status}.", "info")
        except Exception as e:
            print(f"Error toggling session: {e}")
            flash("Could not update booking status.", "danger")
        
    return redirect(url_for('admin'))

@app.route('/admin/toggle-post-site-lead/<string:lead_id>')
def admin_toggle_post_site_lead(lead_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    firestore_db = get_firestore()
    if firestore_db:
        try:
            doc_ref = firestore_db.collection('post_site_leads').document(lead_id)
            doc = doc_ref.get()
            if doc.exists:
                current_status = doc.to_dict().get('status', 'New')
                new_status = 'Contacted' if current_status == 'New' else ('Listed' if current_status == 'Contacted' else 'New')
                doc_ref.update({'status': new_status})
                flash(f"Post Site lead status updated to {new_status}.", "info")
        except Exception as e:
            print(f"Error toggling post site lead: {e}")
            flash("Could not update lead status.", "danger")
        
    return redirect(url_for('admin'))

@app.route('/admin/delete-post-site-lead/<string:lead_id>')
def admin_delete_post_site_lead(lead_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    firestore_db = get_firestore()
    if firestore_db:
        try:
            firestore_db.collection('post_site_leads').document(lead_id).delete()
            flash("Post Site lead deleted.", "success")
        except Exception as e:
            print(f"Error deleting post site lead: {e}")
            flash("Could not delete lead.", "danger")
        
    return redirect(url_for('admin'))

@app.route('/admin/add-site', methods=['POST'])
def admin_add_site():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    title = request.form.get('title', '').strip()
    zone = request.form.get('zone', '').strip()
    location = request.form.get('location', '').strip()
    sub_location = request.form.get('sub_location', '').strip()
    unit_tier = request.form.get('unit_tier', '').strip()
    total_floors = request.form.get('total_floors', '').strip()
    bhk_type = request.form.get('bhk_type', '2 BHK').strip()
    facing = request.form.get('facing', 'East').strip()
    building_age = request.form.get('building_age', 'Ready to Move').strip()
    sqft = request.form.get('sqft', '').strip()
    price_per_sqft = request.form.get('price_per_sqft', '').strip()
    price = request.form.get('price', '').strip()
    description = request.form.get('description', '').strip()
    image_filename = request.form.get('image_filename', 'head.jpeg').strip() or 'head.jpeg'
    
    if 'media_file' in request.files:
        file = request.files['media_file']
        if file and file.filename != '':
            file_bytes = file.read()
            if len(file_bytes) > 0:
                mime_type = file.mimetype or 'image/jpeg'
                encoded = base64.b64encode(file_bytes).decode('utf-8')
                image_filename = f"data:{mime_type};base64,{encoded}"
    
    # 1. Update Local Store
    site_id = f"site-{int(datetime.datetime.now().timestamp()*1000)}"
    site_obj = {
        'id': site_id,
        'title': title,
        'zone': zone,
        'location': location,
        'sub_location': sub_location,
        'unit_tier': unit_tier,
        'total_floors': total_floors,
        'bhk_type': bhk_type,
        'facing': facing,
        'building_age': building_age,
        'sqft': sqft,
        'price_per_sqft': price_per_sqft,
        'price': price,
        'description': description,
        'image_filename': image_filename,
        'created_at': datetime.datetime.now().isoformat()
    }
    local_store = load_local_store()
    if 'sites' not in local_store:
        local_store['sites'] = []
    local_store['sites'].insert(0, site_obj)
    save_local_store(local_store)

    # 2. Update Firestore
    firestore_db = get_firestore()
    if firestore_db:
        try:
            firestore_db.collection('sites').document(site_id).set(site_obj)
        except Exception as e:
            print(f"Error adding site to Firestore: {e}")
            
    flash("New Property Site published successfully!", "success")
    return redirect(url_for('admin'))

@app.route('/admin/bulk-add-sites', methods=['POST'])
def admin_bulk_add_sites():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        payload = request.get_json()
        properties = payload.get('properties', [])
        
        if not properties or not isinstance(properties, list):
            return jsonify({'success': False, 'message': 'No properties provided in request.'}), 400
            
        inserted_count = 0
        now_iso = datetime.datetime.now().isoformat()
        firestore_db = get_firestore()
        local_store = load_local_store()
        if 'sites' not in local_store:
            local_store['sites'] = []
        
        for p in properties:
            title = str(p.get('title') or p.get('name') or p.get('property_name') or 'Featured Property').strip()
            zone = str(p.get('zone') or 'Bengaluru').strip()
            location = str(p.get('location') or p.get('area') or 'Bengaluru').strip()
            sub_location = str(p.get('sub_location') or '').strip()
            unit_tier = str(p.get('unit_tier') or p.get('unit') or '').strip()
            total_floors = str(p.get('total_floors') or '').strip()
            bhk_type = str(p.get('bhk_type') or p.get('bhk') or '2 BHK').strip()
            facing = str(p.get('facing') or 'East').strip()
            building_age = str(p.get('building_age') or p.get('age') or 'Ready to Move').strip()
            sqft = str(p.get('sqft') or p.get('size') or '').strip()
            price_per_sqft = str(p.get('price_per_sqft') or p.get('rate_per_sqft') or '').strip()
            price = str(p.get('price') or p.get('quoted_price') or '').strip()
            description = str(p.get('description') or f"Exclusive {bhk_type} property located in {location}, {zone}. Total area approx {sqft} sq.ft.").strip()
            image_filename = str(p.get('image_filename') or 'head.jpeg').strip()
            site_id = f"site-{int(datetime.datetime.now().timestamp()*1000)}-{inserted_count}"

            doc_data = {
                'id': site_id,
                'title': title,
                'zone': zone,
                'location': location,
                'sub_location': sub_location,
                'unit_tier': unit_tier,
                'total_floors': total_floors,
                'bhk_type': bhk_type,
                'facing': facing,
                'building_age': building_age,
                'sqft': sqft,
                'price_per_sqft': price_per_sqft,
                'price': price,
                'description': description,
                'image_filename': image_filename,
                'created_at': now_iso
            }
            
            local_store['sites'].insert(0, doc_data)
            if firestore_db:
                try:
                    firestore_db.collection('sites').document(site_id).set(doc_data)
                except Exception:
                    pass
            inserted_count += 1
            
        save_local_store(local_store)
        flash(f"Successfully uploaded and published {inserted_count} properties live!", "success")
        return jsonify({'success': True, 'count': inserted_count, 'message': f"Published {inserted_count} properties."})
    except Exception as e:
        print(f"Bulk import error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/edit-site/<string:site_id>', methods=['GET', 'POST'])
def admin_edit_site(site_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    if request.method == 'GET':
        return redirect(url_for('admin'))
        
    title = request.form.get('title', '').strip()
    zone = request.form.get('zone', '').strip()
    location = request.form.get('location', '').strip()
    sub_location = request.form.get('sub_location', '').strip()
    unit_tier = request.form.get('unit_tier', '').strip()
    total_floors = request.form.get('total_floors', '').strip()
    bhk_type = request.form.get('bhk_type', '2 BHK').strip()
    facing = request.form.get('facing', 'East').strip()
    building_age = request.form.get('building_age', 'Ready to Move').strip()
    sqft = request.form.get('sqft', '').strip()
    price_per_sqft = request.form.get('price_per_sqft', '').strip()
    price = request.form.get('price', '').strip()
    description = request.form.get('description', '').strip()
    image_filename = request.form.get('image_filename', 'head.jpeg').strip() or 'head.jpeg'
    
    if 'media_file' in request.files:
        file = request.files['media_file']
        if file and file.filename != '':
            file_bytes = file.read()
            if len(file_bytes) > 0:
                mime_type = file.mimetype or 'image/jpeg'
                encoded = base64.b64encode(file_bytes).decode('utf-8')
                image_filename = f"data:{mime_type};base64,{encoded}"
    
    updated_fields = {
        'title': title,
        'zone': zone,
        'location': location,
        'sub_location': sub_location,
        'unit_tier': unit_tier,
        'total_floors': total_floors,
        'bhk_type': bhk_type,
        'facing': facing,
        'building_age': building_age,
        'sqft': sqft,
        'price_per_sqft': price_per_sqft,
        'price': price,
        'description': description,
        'image_filename': image_filename
    }

    # 1. Update Local Store
    local_store = load_local_store()
    for s in local_store.get('sites', []):
        if s.get('id') == site_id:
            s.update(updated_fields)
            break
    save_local_store(local_store)

    # 2. Update Firestore
    firestore_db = get_firestore()
    if firestore_db:
        try:
            firestore_db.collection('sites').document(site_id).update(updated_fields)
        except Exception as e:
            print(f"Error updating site in Firestore: {e}")

    flash("Property details updated successfully!", "success")
    return redirect(url_for('admin'))

@app.route('/admin/delete-site/<string:site_id>')
def admin_delete_site(site_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    # 1. Update Local Store
    local_store = load_local_store()
    if 'sites' in local_store:
        local_store['sites'] = [s for s in local_store['sites'] if s.get('id') != site_id]
        save_local_store(local_store)

    # 2. Update Firestore
    firestore_db = get_firestore()
    if firestore_db:
        try:
            firestore_db.collection('sites').document(site_id).delete()
        except Exception as e:
            print(f"Error deleting site from Firestore: {e}")

    flash("Property listing removed.", "info")
    return redirect(url_for('admin'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash("Logged out from CMS Dashboard.", "info")
    return redirect(url_for('home'))

@app.route('/sitemap.xml')
def sitemap():
    pages = []
    host = "https://shelterhuntconsultants.com"
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    pages.append({'loc': f"{host}/", 'lastmod': today, 'changefreq': 'daily', 'priority': '1.0'})
    pages.append({'loc': f"{host}/sites", 'lastmod': today, 'changefreq': 'daily', 'priority': '0.9'})
    
    firestore_db = get_firestore()
    if firestore_db:
        try:
            sites_ref = firestore_db.collection('sites').get()
            for doc in sites_ref:
                pages.append({
                    'loc': f"{host}/site/{doc.id}",
                    'lastmod': today,
                    'changefreq': 'weekly',
                    'priority': '0.8'
                })
        except Exception as e:
            print(f"Error fetching sites for sitemap: {e}")
            
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
    for page in pages:
        xml_content += '  <url>\n'
        xml_content += f"    <loc>{page['loc']}</loc>\n"
        xml_content += f"    <lastmod>{page['lastmod']}</lastmod>\n"
        xml_content += f"    <changefreq>{page['changefreq']}</changefreq>\n"
        xml_content += f"    <priority>{page['priority']}</priority>\n"
        if page['loc'] == f"{host}/":
            xml_content += '    <image:image>\n'
            xml_content += f'      <image:loc>{host}/static/logo.jpeg</image:loc>\n'
            xml_content += '      <image:title>Shelter Hunt Consultants Official Logo</image:title>\n'
            xml_content += '    </image:image>\n'
        xml_content += '  </url>\n'
    xml_content += '</urlset>'
    
    return app.response_class(xml_content, mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    content = "User-agent: *\n"
    content += "Allow: /\n"
    content += "Disallow: /admin\n"
    content += "Disallow: /admin/*\n"
    content += "\n"
    content += "Sitemap: https://shelterhuntconsultants.com/sitemap.xml\n"
    return app.response_class(content, mimetype='text/plain')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/x-icon')

if __name__ == '__main__':
    app.run(debug=True, port=5000)