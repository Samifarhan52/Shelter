import os
import datetime
import base64
import urllib.parse
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "shelter_hunt_secret_key_2026")

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/shelter_hunt')

def get_db():
    url = DATABASE_URL
    if url and 'sslmode' not in url and 'localhost' not in url:
        url += '?sslmode=require' if '?' not in url else '&sslmode=require'
        
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def init_db():
    if not DATABASE_URL:
        return
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Admin Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            )
        ''')
        
        # Session Leads Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                session_date VARCHAR(50) NOT NULL,
                slot_time VARCHAR(50) NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                phone VARCHAR(50) NOT NULL,
                location VARCHAR(255) NOT NULL,
                budget VARCHAR(100) NOT NULL,
                message TEXT,
                status VARCHAR(50) DEFAULT 'Confirmed',
                booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Featured Sites / Projects Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sites (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                builder VARCHAR(255) NOT NULL,
                location VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                image_filename TEXT DEFAULT 'head.jpeg',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Builders Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS builders (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')

        # Schema Safety Migrations
        try:
            cursor.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'Confirmed';")
            cursor.execute("ALTER TABLE sites ADD COLUMN IF NOT EXISTS image_filename TEXT DEFAULT 'head.jpeg';")
            cursor.execute("ALTER TABLE sites ALTER COLUMN image_filename TYPE TEXT;")
            cursor.execute("ALTER TABLE builders ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;")
            conn.commit()
        except Exception:
            conn.rollback()

        # Default Admin Account
        cursor.execute("SELECT * FROM users WHERE email = %s", ('admin@shelterhunt.com',))
        if not cursor.fetchone():
            hashed_pwd = generate_password_hash("Admin@123")
            cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                           ("Admin", "admin@shelterhunt.com", hashed_pwd))

        # Seed Builders if empty
        cursor.execute("SELECT COUNT(*) as count FROM builders")
        if cursor.fetchone()['count'] == 0:
            cursor.executemany("INSERT INTO builders (name, is_active) VALUES (%s, %s)", 
                               [('Prestige Group', True), ('Brigade Group', True), ('Sobha Developers', True), ('Godrej Properties', True)])

        # Seed Sites if empty
        cursor.execute("SELECT COUNT(*) as count FROM sites")
        if cursor.fetchone()['count'] == 0:
            cursor.executemany('''
                INSERT INTO sites (title, builder, location, description, image_filename)
                VALUES (%s, %s, %s, %s, %s)
            ''', [
                ('Blue Bells Luxury Enclave', 'Prestige Group', 'Electronic City, Bengaluru', 'Premium residential township with modern architecture, clubhouse, and lush green views.', 'bluebells.jpeg'),
                ('Prestige City - Luxury Apartments', 'Prestige Group', 'Sarjapur Road, Bengaluru', 'High-rise residential township offering premium 2 & 3 BHK residences.', 'head.jpeg'),
                ('Brigade Eldorado', 'Brigade Group', 'Aerospace Park, KIADB, Bengaluru', 'Modern integrated enclave designed for professionals seeking high rental yields.', 'head.jpeg'),
                ('Sobha Town Park', 'Sobha Developers', 'Hosur Road, Bengaluru', 'Luxury New-York styled residential community built with Sobha German technology.', 'head.jpeg')
            ])

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Database Initialization Warning: {e}")

@app.before_request
def ensure_db_initialized():
    if not getattr(app, '_db_initialized', False):
        init_db()
        app._db_initialized = True

def get_active_builders():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM builders WHERE is_active = TRUE OR is_active IS NULL ORDER BY name ASC")
        builders = cursor.fetchall()
        cursor.close()
        conn.close()
        if not builders:
            return [{'name': 'Prestige Group'}, {'name': 'Brigade Group'}, {'name': 'Sobha Developers'}]
        return builders
    except Exception:
        return [{'name': 'Prestige Group'}, {'name': 'Brigade Group'}, {'name': 'Sobha Developers'}]

def get_daily_slots():
    return ["10:00 AM", "12:00 PM", "02:30 PM", "04:30 PM", "06:30 PM"]

# --- Public Routes ---
@app.route('/')
def home():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sites ORDER BY id DESC LIMIT 6")
        sites_list = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception:
        sites_list = []
        
    return render_template('index.html', sites=sites_list, builders=get_active_builders())

@app.route('/sites')
def sites():
    query = request.args.get('q', '').strip()
    builder_filter = request.args.get('builder', '').strip()
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        sql = "SELECT * FROM sites WHERE 1=1"
        params = []
        
        if query:
            sql += " AND (title ILIKE %s OR location ILIKE %s OR description ILIKE %s OR builder ILIKE %s)"
            search_param = f"%{query}%"
            params.extend([search_param, search_param, search_param, search_param])
            
        if builder_filter and builder_filter.lower() != 'builder':
            sql += " AND builder ILIKE %s"
            params.append(f"%{builder_filter}%")
            
        sql += " ORDER BY id DESC"
        
        cursor.execute(sql, tuple(params))
        sites_list = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error searching sites: {e}")
        sites_list = []
        
    return render_template('sites.html', sites=sites_list, builders=get_active_builders(), search_query=query, selected_builder=builder_filter)

@app.route('/about')
def about():
    return render_template('about.html', builders=get_active_builders())

@app.route('/services')
def services():
    return render_template('services.html', builders=get_active_builders())

# --- Strategy Session Booking ---
@app.route('/book-session')
def booking_slots():
    today_str = datetime.date.today().isoformat()
    selected_date = request.args.get('date', today_str)
    
    if selected_date < today_str:
        selected_date = today_str

    all_slots = get_daily_slots()
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT slot_time FROM sessions WHERE session_date = %s AND (status = 'Confirmed' OR status IS NULL)", (selected_date,))
        booked_records = cursor.fetchall()
        booked_slots = [r['slot_time'] for r in booked_records]
        cursor.close()
        conn.close()
    except Exception:
        booked_slots = []
    
    return render_template('booking.html', date=selected_date, today=today_str, all_slots=all_slots, booked_slots=booked_slots, builders=get_active_builders())

@app.route('/check-availability', methods=['GET'])
def check_availability():
    slot = request.args.get('slot')
    current_date = request.args.get('date', datetime.date.today().isoformat())
    
    recommendations = []
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        check_date = datetime.date.fromisoformat(current_date)
        for i in range(1, 15):
            check_date += datetime.timedelta(days=1)
            date_str = check_date.isoformat()
            cursor.execute("SELECT id FROM sessions WHERE session_date = %s AND slot_time = %s AND (status = 'Confirmed' OR status IS NULL)", (date_str, slot))
            if not cursor.fetchone():
                recommendations.append(date_str)
                if len(recommendations) >= 3:
                    break
        cursor.close()
        conn.close()
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

    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify slot is still open
        cursor.execute("SELECT id FROM sessions WHERE session_date = %s AND slot_time = %s AND (status = 'Confirmed' OR status IS NULL)", (session_date, slot_time))
        if cursor.fetchone():
            flash(f"Sorry! The {slot_time} slot on {session_date} was just booked by someone else. Please choose another slot.", "warning")
            cursor.close()
            conn.close()
            return redirect(url_for('booking_slots', date=session_date))

        # Insert booking into database
        cursor.execute('''
            INSERT INTO sessions (session_date, slot_time, full_name, email, phone, location, budget, message, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Confirmed')
        ''', (session_date, slot_time, full_name, email, phone, location, budget, message))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Pre-format WhatsApp Confirmation Message
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

        # Encode text & redirect directly to WhatsApp (+91 8050749331)
        encoded_message = urllib.parse.quote(wa_text)
        whatsapp_url = f"https://wa.me/918050749331?text={encoded_message}"
        
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
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        else:
            flash("Invalid Admin Credentials.", "danger")

    if session.get('admin_logged_in'):
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM sessions ORDER BY booked_at DESC")
        leads = cursor.fetchall()
        
        cursor.execute("SELECT * FROM sites ORDER BY id DESC")
        sites_list = cursor.fetchall()
        
        cursor.execute("SELECT * FROM builders ORDER BY id DESC")
        builders_list = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('admin.html', leads=leads, sites=sites_list, builders=builders_list)
        
    return render_template('admin_login.html')

# Admin Action: Cancel or Reopen Booking
@app.route('/admin/toggle-session/<int:session_id>')
def admin_toggle_session(session_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM sessions WHERE id = %s", (session_id,))
        res = cursor.fetchone()
        if res:
            current_status = res['status'] or 'Confirmed'
            new_status = 'Cancelled' if current_status == 'Confirmed' else 'Confirmed'
            cursor.execute("UPDATE sessions SET status = %s WHERE id = %s", (new_status, session_id))
            conn.commit()
            flash(f"Booking status updated to {new_status}.", "info")
        cursor.close()
        conn.close()
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
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sites (title, builder, location, description, image_filename) VALUES (%s, %s, %s, %s, %s)",
                       (title, builder, location, description, image_filename))
        conn.commit()
        cursor.close()
        conn.close()
        flash("New Featured Site published successfully!", "success")
    except Exception as e:
        print(f"Error adding site: {e}")
        flash("Could not add site.", "danger")
    
    return redirect(url_for('admin'))

# CMS Actions: Edit Site
@app.route('/admin/edit-site/<int:site_id>', methods=['POST'])
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
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE sites 
            SET title = %s, builder = %s, location = %s, description = %s, image_filename = %s
            WHERE id = %s
        ''', (title, builder, location, description, image_filename, site_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Site details updated successfully!", "success")
    except Exception as e:
        print(f"Error updating site: {e}")
        flash("Could not update site.", "danger")
        
    return redirect(url_for('admin'))

# CMS Actions: Delete Site
@app.route('/admin/delete-site/<int:site_id>')
def admin_delete_site(site_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sites WHERE id = %s", (site_id,))
        conn.commit()
        cursor.close()
        conn.close()
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
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO builders (name, is_active) VALUES (%s, %s)", (builder_name, True))
        conn.commit()
        flash("New Builder / Brand added to filter options!", "success")
    except psycopg2.IntegrityError:
        conn.rollback()
        flash("Builder already exists.", "warning")
    finally:
        cursor.close()
        conn.close()
            
    return redirect(url_for('admin'))

# CMS Actions: Toggle Builder Status
@app.route('/admin/toggle-builder/<int:builder_id>')
def admin_toggle_builder(builder_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE builders SET is_active = COALESCE(NOT is_active, TRUE) WHERE id = %s", (builder_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Builder status updated!", "info")
    except Exception as e:
        print(f"Error toggling builder: {e}")
        flash("Could not update status.", "danger")
        
    return redirect(url_for('admin'))

# CMS Actions: Delete Builder
@app.route('/admin/delete-builder/<int:builder_id>')
def admin_delete_builder(builder_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM builders WHERE id = %s", (builder_id,))
        conn.commit()
        cursor.close()
        conn.close()
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