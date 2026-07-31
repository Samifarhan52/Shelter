import os
import datetime
import urllib.parse
import json
import base64
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
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
    if path.startswith('/static') or path.startswith('/admin') or path == '/submit-quick-lead' or path == '/check-availability':
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
def get_active_builders():
    firestore_db = get_firestore()
    if not firestore_db:
        return [{'name': 'Prestige Group'}, {'name': 'Brigade Group'}, {'name': 'Sobha Developers'}]
    try:
        docs = firestore_db.collection('builders').stream()
        builders = []
        for d in docs:
            data = d.to_dict()
            data['id'] = d.id
            if data.get('is_active', True):
                builders.append(data)
        builders.sort(key=lambda x: x.get('name', ''))
        return builders if builders else [{'name': 'Prestige Group'}, {'name': 'Brigade Group'}, {'name': 'Sobha Developers'}]
    except Exception:
        return [{'name': 'Prestige Group'}, {'name': 'Brigade Group'}, {'name': 'Sobha Developers'}]

def get_site_settings():
    defaults = {
        'brand_name': 'SHELTER HUNT',
        'brand_tagline': 'CONSULTANTS',
        'whatsapp_number': '918050749331',
        'contact_phone': '+91 8050749331',
        'contact_email': 'contact@shelterhunt.com',
        'contact_address': 'Bengaluru, Karnataka, India',
        'hero_title': 'Smart Property Decisions Start Here.',
        'hero_subtitle': "We don't push properties — we listen, research, and match you with the right one. Expert consultation that puts your requirements first, every single time.",
        'philosophy_text': 'Shelter Hunt Consultants is a knowledge-first agency built on the belief that real estate decisions deserve expert guidance, not sales pressure.',
        'about_tagline': 'Our Philosophy & Expertise',
        'footer_copyright': '© 2026 Shelter Hunt Consultants. All rights reserved.'
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

def get_daily_slots():
    return ["10:00 AM", "12:00 PM", "02:30 PM", "04:30 PM", "06:30 PM"]

# --- Public Routes ---
@app.route('/')
def home():
    return render_template('index.html', builders=get_active_builders(), settings=get_site_settings())

@app.route('/sites')
def sites():
    query = request.args.get('q', '').strip().lower()
    builder_filter = request.args.get('builder', '').strip().lower()
    sites_list = []
    
    firestore_db = get_firestore()
    if firestore_db:
        try:
            sites_ref = firestore_db.collection('sites').stream()
            for d in sites_ref:
                data = d.to_dict()
                data['id'] = d.id
                
                title = data.get('title', '').lower()
                location = data.get('location', '').lower()
                description = data.get('description', '').lower()
                builder = data.get('builder', '').lower()
                
                matches_q = True
                if query:
                    matches_q = (query in title or query in location or query in description or query in builder)
                    
                matches_builder = True
                if builder_filter and builder_filter != 'builder':
                    matches_builder = (builder_filter in builder)
                    
                if matches_q and matches_builder:
                    sites_list.append(data)
                    
            sites_list.reverse()
        except Exception as e:
            print(f"Search error: {e}")
        
    return render_template('sites.html', sites=sites_list, builders=get_active_builders(), settings=get_site_settings(), search_query=query, selected_builder=builder_filter)

@app.route('/site/<string:site_id>')
def site_detail(site_id):
    firestore_db = get_firestore()
    if firestore_db:
        try:
            doc = firestore_db.collection('sites').document(site_id).get()
            if doc.exists:
                site_data = doc.to_dict()
                site_data['id'] = doc.id
                return render_template('site_detail.html', site=site_data, builders=get_active_builders(), settings=get_site_settings())
        except Exception as e:
            print(f"Error fetching site details: {e}")
            
    flash("Property site not found.", "warning")
    return redirect(url_for('sites'))

@app.route('/about')
def about():
    return render_template('about.html', builders=get_active_builders(), settings=get_site_settings())

@app.route('/services')
def services():
    return render_template('services.html', builders=get_active_builders(), settings=get_site_settings())

@app.route('/submit-quick-lead', methods=['POST'])
def submit_quick_lead():
    full_name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    
    if not full_name or not phone:
        return jsonify({'success': False, 'message': 'Name and phone number are required.'}), 400

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
                'phone': phone,
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
        f"• *Phone:* {phone}\n"
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
    
    return render_template('booking.html', date=selected_date, today=today_str, all_slots=all_slots, booked_slots=booked_slots, builders=get_active_builders(), settings=get_site_settings())

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
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    location = request.form.get('location')
    budget = request.form.get('budget')
    message = request.form.get('message', '')
    
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
                'phone': phone,
                'location': location,
                'budget': budget,
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
        f"• *Phone:* {phone}\n"
        f"• *Email:* {email}\n"
        f"• *Location:* {location}\n"
        f"• *Budget:* {budget}\n"
    )
    if message:
        wa_text += f"• *Notes:* {message}\n"
        
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
        leads, sites_list, builders_list = [], [], []
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

                builders_docs = firestore_db.collection('builders').stream()
                for b in builders_docs:
                    d = b.to_dict()
                    d['id'] = b.id
                    builders_list.append(d)
                builders_list.sort(key=lambda x: x.get('name', ''))

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
        
        return render_template('admin.html', leads=leads, sites=sites_list, builders=builders_list, analytics=analytics, settings=get_site_settings())
        
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
        'footer_copyright': request.form.get('footer_copyright', '').strip()
    }
    
    firestore_db = get_firestore()
    if firestore_db:
        try:
            for key, val in settings_data.items():
                if val:
                    firestore_db.collection('settings').document(key).set({'value': val})
            flash("Global settings and dynamic site content updated successfully!", "success")
        except Exception as e:
            print(f"Error saving settings: {e}")
            flash("Could not update settings.", "danger")
        
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
        
    title = request.form.get('title')
    builder = request.form.get('builder')
    location = request.form.get('location')
    price = request.form.get('price', '').strip()
    sqft = request.form.get('sqft', '').strip()
    price_per_sqft = request.form.get('price_per_sqft', '').strip()
    description = request.form.get('description')
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
                'builder': builder,
                'location': location,
                'price': price,
                'sqft': sqft,
                'price_per_sqft': price_per_sqft,
                'description': description,
                'image_filename': image_filename,
                'created_at': datetime.datetime.now().isoformat()
            })
            flash("New Property Site published successfully!", "success")
        except Exception as e:
            print(f"Error adding site: {e}")
            flash("Could not add site.", "danger")
    
    return redirect(url_for('admin'))

@app.route('/admin/edit-site/<string:site_id>', methods=['GET', 'POST'])
def admin_edit_site(site_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    if request.method == 'GET':
        return redirect(url_for('admin'))
        
    title = request.form.get('title')
    builder = request.form.get('builder')
    location = request.form.get('location')
    price = request.form.get('price', '').strip()
    sqft = request.form.get('sqft', '').strip()
    price_per_sqft = request.form.get('price_per_sqft', '').strip()
    description = request.form.get('description')
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
                'builder': builder,
                'location': location,
                'price': price,
                'sqft': sqft,
                'price_per_sqft': price_per_sqft,
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

@app.route('/admin/add-builder', methods=['POST'])
def admin_add_builder():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    builder_name = request.form.get('builder_name')
    
    firestore_db = get_firestore()
    if firestore_db:
        try:
            firestore_db.collection('builders').add({'name': builder_name, 'is_active': True})
            flash("New Builder Brand added!", "success")
        except Exception as e:
            print(f"Error adding builder: {e}")
            flash("Could not add builder.", "danger")
            
    return redirect(url_for('admin'))

@app.route('/admin/toggle-builder/<string:builder_id>')
def admin_toggle_builder(builder_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    firestore_db = get_firestore()
    if firestore_db:
        try:
            doc_ref = firestore_db.collection('builders').document(builder_id)
            doc = doc_ref.get()
            if doc.exists:
                curr = doc.to_dict().get('is_active', True)
                doc_ref.update({'is_active': not curr})
                flash("Builder status updated!", "info")
        except Exception as e:
            print(f"Error toggling builder: {e}")
            flash("Could not update status.", "danger")
        
    return redirect(url_for('admin'))

@app.route('/admin/delete-builder/<string:builder_id>')
def admin_delete_builder(builder_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    firestore_db = get_firestore()
    if firestore_db:
        try:
            firestore_db.collection('builders').document(builder_id).delete()
            flash("Builder removed.", "warning")
        except Exception as e:
            print(f"Error deleting builder: {e}")
            flash("Could not delete builder.", "danger")
        
    return redirect(url_for('admin'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash("Logged out from CMS Dashboard.", "info")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)