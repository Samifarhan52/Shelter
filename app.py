import os
import datetime
import urllib.parse
import json
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
        'whatsapp_number': '918050749331',
        'contact_phone': '+91 8050749331',
        'contact_email': 'contact@shelterhunt.com',
        'contact_address': 'Bengaluru, Karnataka, India',
        'hero_title': 'Smart Property Decisions Start Here.',
        'hero_subtitle': "We don't push properties — we listen, research, and match you with the right one. Expert consultation that puts your requirements first, every single time."
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

@app.route('/about')
def about():
    return render_template('about.html', builders=get_active_builders(), settings=get_site_settings())

@app.route('/services')
def services():
    return render_template('services.html', builders=get_active_builders(), settings=get_site_settings())

# --- Quick Modal Lead Submission API ---
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

    # Build WhatsApp URL
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

# --- Strategy Session Booking ---
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

# --- CMS Admin Dashboard ---
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
    
    firestore_db = get_firestore()
    if firestore_db:
        try:
            for key, val in settings_data.items():
                firestore_db.collection('settings').document(key).set({'value': val})
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

# Admin Action: Cancel or Reopen Booking
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
    
    firestore_db = get_firestore()
    if firestore_db:
        try:
            firestore_db.collection('sites').add({
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

# CMS Actions: Edit Site (Handles both GET and POST)
@app.route('/admin/edit-site/<string:site_id>', methods=['GET', 'POST'])
def admin_edit_site(site_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    if request.method == 'GET':
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
    
    firestore_db = get_firestore()
    if firestore_db:
        try:
            firestore_db.collection('sites').document(site_id).update({
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
        
    firestore_db = get_firestore()
    if firestore_db:
        try:
            firestore_db.collection('sites').document(site_id).delete()
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
    
    firestore_db = get_firestore()
    if firestore_db:
        try:
            firestore_db.collection('builders').add({'name': builder_name, 'is_active': True})
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

# CMS Actions: Delete Builder
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
    flash("Logged out from Admin CMS Dashboard.", "info")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)