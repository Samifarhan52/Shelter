import os
import datetime
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "shelter_hunt_secret_key_2026")

# Reads the cloud PostgreSQL URL from environment variables, falling back to local PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/shelter_hunt')

def get_db():
    url = DATABASE_URL
    # Enforce sslmode=require for cloud PostgreSQL instances like Supabase/Neon
    if url and 'sslmode' not in url and 'localhost' not in url:
        url += '?sslmode=require' if '?' not in url else '&sslmode=require'
        
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def init_db():
    if not DATABASE_URL:
        print("DATABASE_URL not set. Skipping DB initialization.")
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
        
        # Strategy Session Leads Table
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
                status VARCHAR(50) DEFAULT 'New',
                booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # CMS Table: Featured Projects / Sites
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sites (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                builder VARCHAR(255) NOT NULL,
                location VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # CMS Table: Builders / Brands Filter
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS builders (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL
            )
        ''')

        # Setup Default Admin Account
        cursor.execute("SELECT * FROM users WHERE email = %s", ('admin@shelterhunt.com',))
        if not cursor.fetchone():
            hashed_pwd = generate_password_hash("Admin@123")
            cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                           ("Admin", "admin@shelterhunt.com", hashed_pwd))

        # Insert Default Builders if empty
        cursor.execute("SELECT COUNT(*) as count FROM builders")
        if cursor.fetchone()['count'] == 0:
            cursor.executemany("INSERT INTO builders (name) VALUES (%s)", 
                               [('Prestige Group',), ('Brigade Group',), ('Sobha Developers',), ('Godrej Properties',)])

        # Insert Default Sites if empty
        cursor.execute("SELECT COUNT(*) as count FROM sites")
        if cursor.fetchone()['count'] == 0:
            cursor.executemany('''
                INSERT INTO sites (title, builder, location, description)
                VALUES (%s, %s, %s, %s)
            ''', [
                ('Prestige City - Luxury Apartments', 'Prestige Group', 'Sarjapur Road, Bengaluru', 'High-rise residential township offering premium 2 & 3 BHK residences.'),
                ('Brigade Eldorado', 'Brigade Group', 'Aerospace Park, KIADB, Bengaluru', 'Modern integrated enclave designed for professionals seeking high rental yields.'),
                ('Sobha Town Park', 'Sobha Developers', 'Hosur Road, Bengaluru', 'Luxury New-York styled residential community built with Sobha German technology.')
            ])

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Database Initialization Warning: {e}")

@app.before_request
def ensure_db_initialized():
    """Safely runs DB schema creation once before handling the first HTTP request."""
    if not getattr(app, '_db_initialized', False):
        init_db()
        app._db_initialized = True

def get_daily_slots():
    return ["10:00 AM", "12:00 PM", "02:30 PM", "04:30 PM", "06:30 PM"]

# --- Public Routes ---
@app.route('/')
def home():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sites ORDER BY id DESC")
        sites_list = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception:
        sites_list = []
    return render_template('index.html', sites=sites_list)

@app.route('/sites')
def sites():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sites ORDER BY id DESC")
        sites_list = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception:
        sites_list = []
    return render_template('sites.html', sites=sites_list)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    return render_template('services.html')

# --- Strategy Session Booking ---
@app.route('/book-session')
def booking_slots():
    selected_date = request.args.get('date', datetime.date.today().isoformat())
    all_slots = get_daily_slots()
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT slot_time FROM sessions WHERE session_date = %s", (selected_date,))
        booked_records = cursor.fetchall()
        booked_slots = [r['slot_time'] for r in booked_records]
        cursor.close()
        conn.close()
    except Exception:
        booked_slots = []
    
    return render_template('booking.html', date=selected_date, all_slots=all_slots, booked_slots=booked_slots)

@app.route('/confirm-booking', methods=['POST'])
def confirm_booking():
    session_date = request.form.get('session_date')
    slot_time = request.form.get('slot_time')
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    location = request.form.get('location')
    budget = request.form.get('budget')
    message = request.form.get('message')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sessions (session_date, slot_time, full_name, email, phone, location, budget, message)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ''', (session_date, slot_time, full_name, email, phone, location, budget, message))
    conn.commit()
    cursor.close()
    conn.close()
        
    flash("Your Property Strategy Session has been successfully booked!", "success")
    return redirect(url_for('home'))

# --- WordPress-Style CMS Admin Dashboard ---
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

# CMS Actions: Add Site
@app.route('/admin/add-site', methods=['POST'])
def admin_add_site():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    title = request.form.get('title')
    builder = request.form.get('builder')
    location = request.form.get('location')
    description = request.form.get('description')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sites (title, builder, location, description) VALUES (%s, %s, %s, %s)",
                   (title, builder, location, description))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("New Featured Site published successfully!", "success")
    return redirect(url_for('admin'))

# CMS Actions: Delete Site
@app.route('/admin/delete-site/<int:site_id>')
def admin_delete_site(site_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sites WHERE id = %s", (site_id,))
    conn.commit()
    cursor.close()
    conn.close()
        
    flash("Site entry removed.", "info")
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
        cursor.execute("INSERT INTO builders (name) VALUES (%s)", (builder_name,))
        conn.commit()
        flash("New Builder / Brand added to filter options!", "success")
    except psycopg2.IntegrityError:
        conn.rollback()
        flash("Builder already exists.", "warning")
    finally:
        cursor.close()
        conn.close()
            
    return redirect(url_for('admin'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash("Logged out from Admin CMS Dashboard.", "info")
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)