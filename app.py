import os
import datetime
import urllib.parse
import json
import base64
import re
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

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

# Helper Functions
def get_bhk_options():
    defaults = ["1 BHK", "2 BHK", "3 BHK", "4 BHK", "4+ BHK"]
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
        'contact_address': 'Bengaluru, Karnataka, India',
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
        'google_maps_embed_url': ''
    }
    firestore_db = get_firestore()
    if not firestore_db:
        return defaults
    try:
        docs = firestore_db.collection('settings').stream()
        for d in docs:
            defaults[d.id] = d.to_dict().get('value', '')
    except Exception:
        pass
    return defaults

# Global Template Context Processor
@app.context_processor
def inject_global_data():
    return {
        'settings': get_site_settings(),
        'bhk_options': get_bhk_options(),
        'facing_options': get_facing_options(),
        'zone_options': get_zone_options(),
        'age_options': get_age_options()
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
    return render_template('index.html', bhk_options=get_bhk_options(), settings=get_site_settings())

@app.route('/sites')
def sites():
    query = request.args.get('q', '').strip().lower()
    bhk_filter = request.args.get('bhk', '').strip()
    facing_filter = request.args.get('facing', '').strip()
    zone_filter = request.args.get('zone', '').strip()
    age_filter = request.args.get('age', '').strip()
    
    sites_list = []
    
    firestore_db = get_firestore()
    if firestore_db:
        try:
            sites_ref = firestore_db.collection('sites').stream()
            for d in sites_ref:
                data = d.to_dict()
                data['id'] = d.id
                
                title = str(data.get('title', '')).lower()
                location = str(data.get('location', '')).lower()
                sub_location = str(data.get('sub_location', '')).lower()
                description = str(data.get('description', '')).lower()
                bhk_type = str(data.get('bhk_type', ''))
                facing = str(data.get('facing', ''))
                zone = str(data.get('zone', ''))
                building_age = str(data.get('building_age', ''))
                
                matches_q = True
                if query:
                    matches_q = (query in title or query in location or query in sub_location or query in description or query in bhk_type.lower() or query in zone.lower())
                    
                matches_bhk = True
                if bhk_filter and bhk_filter.lower() != 'all':
                    matches_bhk = (bhk_filter.lower() in bhk_type.lower())

                matches_facing = True
                if facing_filter and facing_filter.lower() != 'all':
                    matches_facing = (facing_filter.lower() == facing.lower())

                matches_zone = True
                if zone_filter and zone_filter.lower() != 'all':
                    matches_zone = (zone_filter.lower() in zone.lower() or zone_filter.lower() in location.lower())

                matches_age = True
                if age_filter and age_filter.lower() != 'all':
                    matches_age = (age_filter.lower() == building_age.lower())
                    
                if matches_q and matches_bhk and matches_facing and matches_zone and matches_age:
                    sites_list.append(data)
                    
            sites_list.reverse()
        except Exception as e:
            print(f"Search error: {e}")
        
    return render_template('sites.html', 
                           sites=sites_list, 
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

# CMS Admin Control Panel
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    firestore_db = get_firestore()
    
    if request.method == 'POST' and 'login' in request.form:
        email = request.form.get('email')
        password = request.form.get('password')
        
        if firestore_db:
            try:
                doc = firestore_db.collection('users').document(email).get()
                if doc.exists:
                    user = doc.to_dict()
                    if check_password_hash(user['password'], password):
                        session['admin_logged_in'] = True
                        return redirect(url_for('admin'))
            except Exception as e:
                print(f"Login error: {e}")
        
        if email == 'admin@shelterhunt.com' and password == 'Admin@123':
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
            
        flash("Invalid Admin Credentials.", "danger")

    if session.get('admin_logged_in'):
        leads, sites_list = [], []
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

                sites_docs = firestore_db.collection('sites').stream()
                for s in sites_docs:
                    d = s.to_dict()
                    d['id'] = s.id
                    sites_list.append(d)
                sites_list.reverse()

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
        
        return render_template('admin.html', 
                               leads=leads, 
                               sites=sites_list, 
                               bhk_options=get_bhk_options(),
                               facing_options=get_facing_options(),
                               zone_options=get_zone_options(),
                               age_options=get_age_options(),
                               analytics=analytics, 
                               settings=get_site_settings())
        
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
    
    firestore_db = get_firestore()
    if firestore_db:
        try:
            for key, val in settings_data.items():
                firestore_db.collection('settings').document(key).set({'value': val})
            flash("Global site settings, logo, branding, and integrations updated successfully!", "success")
        except Exception as e:
            print(f"Error saving settings: {e}")
            flash("Could not update settings.", "danger")
        
    return redirect(url_for('admin'))

@app.route('/admin/add-master-option', methods=['POST'])
def admin_add_master_option():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    master_type = request.form.get('master_type', '').strip()
    new_val = request.form.get('option_value', '').strip()
    
    if master_type and new_val:
        firestore_db = get_firestore()
        if firestore_db:
            try:
                doc_ref = firestore_db.collection('masters').document(master_type)
                doc = doc_ref.get()
                items = doc.to_dict().get('items', []) if doc.exists else []
                if new_val not in items:
                    items.append(new_val)
                    doc_ref.set({'items': items})
                    flash(f"Added '{new_val}' to master configurations.", "success")
            except Exception as e:
                print(f"Error adding master option: {e}")
                flash("Could not add master option.", "danger")
                
    return redirect(url_for('admin'))

@app.route('/admin/delete-master-option', methods=['POST'])
def admin_delete_master_option():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    master_type = request.form.get('master_type', '').strip()
    target_val = request.form.get('option_value', '').strip()
    
    if master_type and target_val:
        firestore_db = get_firestore()
        if firestore_db:
            try:
                doc_ref = firestore_db.collection('masters').document(master_type)
                doc = doc_ref.get()
                if doc.exists:
                    items = doc.to_dict().get('items', [])
                    items = [i for i in items if i != target_val]
                    doc_ref.set({'items': items})
                    flash(f"Removed '{target_val}' from master configurations.", "info")
            except Exception as e:
                print(f"Error deleting master option: {e}")
                flash("Could not delete master option.", "danger")
                
    return redirect(url_for('admin'))

@app.route('/admin/change-password', methods=['POST'])
def admin_change_password():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not new_password or new_password != confirm_password:
        flash("Passwords do not match.", "warning")
        return redirect(url_for('admin'))
        
    firestore_db = get_firestore()
    if firestore_db:
        try:
            hashed_pwd = generate_password_hash(new_password)
            firestore_db.collection('users').document('admin@shelterhunt.com').set({'password': hashed_pwd, 'name': 'Admin', 'email': 'admin@shelterhunt.com'})
            flash("Admin account password successfully updated!", "success")
        except Exception as e:
            print(f"Error updating password: {e}")
            flash("Could not update password.", "danger")
        
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
    
    firestore_db = get_firestore()
    if firestore_db:
        try:
            firestore_db.collection('sites').add({
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
            })
            flash("New Property Site published successfully!", "success")
        except Exception as e:
            print(f"Error adding site: {e}")
            flash("Could not add site.", "danger")
    
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
            
        firestore_db = get_firestore()
        if not firestore_db:
            return jsonify({'success': False, 'message': 'Database connection error.'}), 500
            
        inserted_count = 0
        now_iso = datetime.datetime.now().isoformat()
        
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

            doc_data = {
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
            
            firestore_db.collection('sites').add(doc_data)
            inserted_count += 1
            
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
    
    firestore_db = get_firestore()
    if firestore_db:
        try:
            firestore_db.collection('sites').document(site_id).update({
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
            })
            flash("Property details updated successfully!", "success")
        except Exception as e:
            print(f"Error updating site: {e}")
            flash("Could not update site.", "danger")
        
    return redirect(url_for('admin'))

@app.route('/admin/delete-site/<string:site_id>')
def admin_delete_site(site_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    firestore_db = get_firestore()
    if firestore_db:
        try:
            firestore_db.collection('sites').document(site_id).delete()
            flash("Property listing removed.", "info")
        except Exception as e:
            print(f"Error deleting site: {e}")
            flash("Could not delete site.", "danger")
        
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
    xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for page in pages:
        xml_content += '  <url>\n'
        xml_content += f"    <loc>{page['loc']}</loc>\n"
        xml_content += f"    <lastmod>{page['lastmod']}</lastmod>\n"
        xml_content += f"    <changefreq>{page['changefreq']}</changefreq>\n"
        xml_content += f"    <priority>{page['priority']}</priority>\n"
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)