import os
import datetime
import base64
import urllib.parse
import json
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "shelter_hunt_secret_key_2026")

# Initialize Firebase Admin SDK
def init_firebase():
    if not firebase_admin._apps:
        cred_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if cred_json:
            # Load from Vercel Environment Variable
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
        elif os.path.exists("firebase_key.json"):
            # Load from Local JSON File
            cred = credentials.Certificate("firebase_key.json")
        else:
            raise Exception("Firebase credentials not found! Place firebase_key.json in project root or set FIREBASE_SERVICE_ACCOUNT env var.")
        firebase_admin.initialize_app(cred)

init_firebase()
db = firestore.client()

# Seed default data on start if database collections are empty
def seed_firebase_data():
    try:
        # 1. Seed Default Admin User
        users_ref = db.collection('users')
        if len(list(users_ref.limit(1).stream())) == 0:
            hashed_pwd = generate_password_hash("Admin@123")
            users_ref.document('admin@shelterhunt.com').set({
                'name': 'Admin',
                'email': 'admin@shelterhunt.com',
                'password': hashed_pwd
            })

        # 2. Seed Default Settings
        settings_ref = db.collection('settings')
        if len(list(settings_ref.limit(1).stream())) == 0:
            default_settings = {
                'whatsapp_number': '918050749331',
                'contact_phone': '+91 8050749331',
                'contact_email': 'contact@shelterhunt.com',
                'contact_address': 'Bengaluru, Karnataka, India',
                'hero_title': 'Smart Property Decisions Start Here.',
                'hero_subtitle': "We don't push properties — we listen, research, and match you with the right one. Expert consultation that puts your requirements first, every single time."
            }
            for key, val in default_settings.items():
                settings_ref.document(key).set({'value': val})

        # 3. Seed Default Builders
        builders_ref = db.collection('builders')
        if len(list(builders_ref.limit(1).stream())) == 0:
            default_builders = ['Prestige Group', 'Brigade Group', 'Sobha Developers', 'Godrej Properties']
            for b in default_builders:
                builders_ref.add({'name': b, 'is_active': True})

        # 4. Seed Default Sites
        sites_ref = db.collection('sites')
        if len(list(sites_ref.limit(1).stream())) == 0:
            default_sites = [
                {'title': 'Blue Bells Luxury Enclave', 'builder': 'Prestige Group', 'location': 'Electronic City, Bengaluru', 'description': 'Premium residential township with modern architecture, clubhouse, and lush green views.', 'image_filename': 'bluebells.jpeg', 'created_at': datetime.datetime.now().isoformat()},
                {'title': 'Prestige City - Luxury Apartments', 'builder': 'Prestige Group', 'location': 'Sarjapur Road, Bengaluru', 'description': 'High-rise residential township offering premium 2 & 3 BHK residences.', 'image_filename': 'head.jpeg', 'created_at': datetime.datetime.now().isoformat()},
                {'title': 'Brigade Eldorado', 'builder': 'Brigade Group', 'location': 'Aerospace Park, KIADB, Bengaluru', 'description': 'Modern integrated enclave designed for professionals seeking high rental yields.', 'image_filename': 'head.jpeg', 'created_at': datetime.datetime.now().isoformat()},
                {'title': 'Sobha Town Park', 'builder': 'Sobha Developers', 'location': 'Hosur Road, Bengaluru', 'description': 'Luxury New-York styled residential community built with Sobha German technology.', 'image_filename': 'head.jpeg', 'created_at': datetime.datetime.now().isoformat()}
            ]
            for s in default_sites:
                sites_ref.add(s)
    except Exception as e:
        print(f"Firebase Seeding Warning: {e}")

seed_firebase_data()

# Helper Functions
def get_active_builders():
    try:
        docs = db.collection('builders').stream()
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
        'whatsapp_number': '918050749331',
        'contact_phone': '+91 8050749331',
        'contact_email': 'contact@shelterhunt.com',
        'contact_address': 'Bengaluru, Karnataka, India',
        'hero_title': 'Smart Property Decisions Start Here.',
        'hero_subtitle': "We don't push properties — we listen, research, and match you with the right one. Expert consultation that puts your requirements first, every single time."
    }
    try:
        docs = db.collection('settings').stream()
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
    try:
        sites_ref = db.collection('sites').stream()
        sites_list = []
        for d in sites_ref:
            data = d.to_dict()
            data['id'] = d.id
            sites_list.append(data)
        sites_list.reverse()
        sites_list = sites_list[:6]
    except Exception:
        sites_list = []
        
    return render_template('index.html', sites=sites_list, builders=get_active_builders(), settings=get_site_settings())

@app.route('/sites')
def sites():
    query = request.args.get('q', '').strip().lower()
    builder_filter = request.args.get('builder', '').strip().lower()
    
    try:
        sites_ref = db.collection('sites').stream()
        sites_list = []
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
        sites_list = []
        
    return render_template('sites.html', sites=sites_list, builders=get_active_builders(), settings=get_site_settings(), search_query=query, selected_builder=builder_filter)

@app.route('/about')
def about():
    return render_template('about.html', builders=get_active_builders(), settings=get_site_settings())

@app.route('/services')
def services():
    return render_template('services.html', builders=get_active_builders(), settings=get_site_settings())

# --- Strategy Session Booking ---
@app.route('/book-session')
def booking_slots():
    today_str = datetime.date.today().isoformat()
    selected_date = request.args.get('date', today_str)
    
    if selected_date < today_str:
        selected_date = today_str

    all_slots = get_daily_slots()
    
    try:
        sessions_ref = db.collection('sessions').where('session_date', '==', selected_date).stream()
        booked_slots = []
        for s in sessions_ref:
            s_data = s.to_dict()
            if s_data.get('status', 'Confirmed') == 'Confirmed':
                booked_slots.append(s_data.get('slot_time'))
    except Exception:
        booked_slots = []
    
    return render_template('booking.html', date=selected_date, today=today_str, all_slots=all_slots, booked_slots=booked_slots, builders=get_active_builders(), settings=get_site_settings())

@app.route('/check-availability', methods=['GET'])
def check_availability():
    slot = request.args.get('slot')
    current_date = request.args.get('date', datetime.date.today().isoformat())
    
    recommendations = []
    try:
        check_date = datetime.date.fromisoformat(current_date)
        for i in range(1, 15):
            check_date += datetime.timedelta(days=1)
            date_str = check_date.isoformat()
            
            query = db.collection('sessions').where('session_date', '==', date_str).where('slot_time', '==', slot).limit(1).stream()
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

    try:
        # Verify slot is open
        existing = db.collection('sessions').where('session_date', '==', session_date).where('slot_time', '==', slot_time).limit(1).stream()
        docs = list(existing)
        if docs and docs[0].to_dict().get('status', 'Confirmed') == 'Confirmed':
            flash(f"Sorry! The {slot_time} slot on {session_date} was just booked by someone else. Please choose another slot.", "warning")
            return redirect(url_for('booking_slots', date=session_date))

        # Insert booking in Firestore
        db.collection('sessions').add({
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
        
        # Pre-format WhatsApp Message
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

    except Exception as e:
        print(f"Booking error: {e}")
        flash("Error processing booking. Please try again.", "danger")
        return redirect(url_for('booking_slots'))

# --- CMS Admin Dashboard ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST' and 'login' in request.form:
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            doc = db.collection('users').document(email).get()
            if doc.exists:
                user = doc.to_dict()
                if check_password_hash(user['password'], password):
                    session['admin_logged_in'] = True
                    return redirect(url_for('admin'))
            flash("Invalid Admin Credentials.", "danger")
        except Exception as e:
            print(f"Login error: {e}")
            flash("Error during admin login. Please try again.", "danger")

    if session.get('admin_logged_in'):
        leads, sites_list, builders_list = [], [], []
        try:
            # Fetch Leads
            leads_docs = db.collection('sessions').stream()
            for l in leads_docs:
                d = l.to_dict()
                d['id'] = l.id
                leads.append(d)
            leads.sort(key=lambda x: x.get('booked_at', ''), reverse=True)

            # Fetch Sites
            sites_docs = db.collection('sites').stream()
            for s in sites_docs:
                d = s.to_dict()
                d['id'] = s.id
                sites_list.append(d)
            sites_list.reverse()

            # Fetch Builders
            builders_docs = db.collection('builders').stream()
            for b in builders_docs:
                d = b.to_dict()
                d['id'] = b.id
                builders_list.append(d)
            builders_list.sort(key=lambda x: x.get('name', ''))

        except Exception as e:
            print(f"Admin fetch error: {e}")
        
        return render_template('admin.html', leads=leads, sites=sites_list, builders=builders_list, settings=get_site_settings())
        
    return render_template('admin_login.html')

# CMS Actions: Save System Settings
@app.route('/admin/save-settings', methods=['POST'])
def admin_save_settings():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    settings_data = {
        'whatsapp_number': request.form.get('whatsapp_number', '918050749331').strip(),
        'contact_phone': request.form.get('contact_phone', '+91 8050749331').strip(),
        'contact_email': request.form.get('contact_email', 'contact@shelterhunt.com').strip(),
        'contact_address': request.form.get('contact_address', 'Bengaluru, Karnataka, India').strip(),
        'hero_title': request.form.get('hero_title', 'Smart Property Decisions Start Here.').strip(),
        'hero_subtitle': request.form.get('hero_subtitle', '').strip()
    }
    
    try:
        for key, val in settings_data.items():
            db.collection('settings').document(key).set({'value': val})
        flash("System Settings updated successfully across the entire website!", "success")
    except Exception as e:
        print(f"Error saving settings: {e}")
        flash("Could not update settings.", "danger")
        
    return redirect(url_for('admin'))

# CMS Actions: Update Admin Password
@app.route('/admin/change-password', methods=['POST'])
def admin_change_password():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not new_password or new_password != confirm_password:
        flash("Passwords do not match.", "warning")
        return redirect(url_for('admin'))
        
    try:
        hashed_pwd = generate_password_hash(new_password)
        db.collection('users').document('admin@shelterhunt.com').update({'password': hashed_pwd})
        flash("Admin account password successfully updated!", "success")
    except Exception as e:
        print(f"Error updating password: {e}")
        flash("Could not update password.", "danger")
        
    return redirect(url_for('admin'))

# Admin Action: Cancel or Reopen Booking
@app.route('/admin/toggle-session/<string:session_id>')
def admin_toggle_session(session_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    try:
        doc_ref = db.collection('sessions').document(session_id)
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

# CMS Actions: Add Site
@app.route('/admin/add-site', methods=['POST'])
def admin_add_site():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    title = request.form.get('title')
    builder = request.form.get('builder')
    location = request.form.get('location')
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
    
    try:
        db.collection('sites').add({
            'title': title,
            'builder': builder,
            'location': location,
            'description': description,
            'image_filename': image_filename,
            'created_at': datetime.datetime.now().isoformat()
        })
        flash("New Featured Site published successfully!", "success")
    except Exception as e:
        print(f"Error adding site: {e}")
        flash("Could not add site.", "danger")
    
    return redirect(url_for('admin'))

# CMS Actions: Edit Site
@app.route('/admin/edit-site/<string:site_id>', methods=['POST'])
def admin_edit_site(site_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    title = request.form.get('title')
    builder = request.form.get('builder')
    location = request.form.get('location')
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
    
    try:
        db.collection('sites').document(site_id).update({
            'title': title,
            'builder': builder,
            'location': location,
            'description': description,
            'image_filename': image_filename
        })
        flash("Site details updated successfully!", "success")
    except Exception as e:
        print(f"Error updating site: {e}")
        flash("Could not update site.", "danger")
        
    return redirect(url_for('admin'))

# CMS Actions: Delete Site
@app.route('/admin/delete-site/<string:site_id>')
def admin_delete_site(site_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    try:
        db.collection('sites').document(site_id).delete()
        flash("Site entry removed.", "info")
    except Exception as e:
        print(f"Error deleting site: {e}")
        flash("Could not delete site.", "danger")
        
    return redirect(url_for('admin'))

# CMS Actions: Add Builder / Brand
@app.route('/admin/add-builder', methods=['POST'])
def admin_add_builder():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    builder_name = request.form.get('builder_name')
    
    try:
        db.collection('builders').add({'name': builder_name, 'is_active': True})
        flash("New Builder / Brand added to filter options!", "success")
    except Exception as e:
        print(f"Error adding builder: {e}")
        flash("Could not add builder.", "danger")
            
    return redirect(url_for('admin'))

# CMS Actions: Toggle Builder Status
@app.route('/admin/toggle-builder/<string:builder_id>')
def admin_toggle_builder(builder_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    try:
        doc_ref = db.collection('builders').document(builder_id)
        doc = doc_ref.get()
        if doc.exists:
            curr = doc.to_dict().get('is_active', True)
            doc_ref.update({'is_active': not curr})
            flash("Builder status updated!", "info")
    except Exception as e:
        print(f"Error toggling builder: {e}")
        flash("Could not update status.", "danger")
        
    return redirect(url_for('admin'))

# CMS Actions: Delete Builder
@app.route('/admin/delete-builder/<string:builder_id>')
def admin_delete_builder(builder_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    try:
        db.collection('builders').document(builder_id).delete()
        flash("Builder removed.", "warning")
    except Exception as e:
        print(f"Error deleting builder: {e}")
        flash("Could not delete builder.", "danger")
        
    return redirect(url_for('admin'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash("Logged out from Admin CMS Dashboard.", "info")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)