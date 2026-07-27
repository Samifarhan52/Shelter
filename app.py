import sqlite3
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "shelter_hunt_secret_key_2026"
DATABASE = "database.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Admin Users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        
        # Leads / Booked Sessions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date TEXT NOT NULL,
                slot_time TEXT NOT NULL,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                location TEXT NOT NULL,
                budget TEXT NOT NULL,
                message TEXT,
                status TEXT DEFAULT 'New',
                booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # CMS Table: Featured Projects / Sites
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                builder TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # CMS Table: Builders / Brands Filter
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS builders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')

        # Setup Default Admin Account
        cursor.execute("SELECT * FROM users WHERE email = 'admin@shelterhunt.com'")
        if not cursor.fetchone():
            hashed_pwd = generate_password_hash("Admin@123")
            cursor.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                           ("Admin", "admin@shelterhunt.com", hashed_pwd))

        # Insert Default Builders if empty
        cursor.execute("SELECT COUNT(*) as count FROM builders")
        if cursor.fetchone()['count'] == 0:
            cursor.executemany("INSERT INTO builders (name) VALUES (?)", 
                               [('Prestige Group',), ('Brigade Group',), ('Sobha Developers',), ('Godrej Properties',)])

        # Insert Default Sites if empty
        cursor.execute("SELECT COUNT(*) as count FROM sites")
        if cursor.fetchone()['count'] == 0:
            cursor.executemany('''
                INSERT INTO sites (title, builder, location, description)
                VALUES (?, ?, ?, ?)
            ''', [
                ('Prestige City - Luxury Apartments', 'Prestige Group', 'Sarjapur Road, Bengaluru', 'High-rise residential township offering premium 2 & 3 BHK residences.'),
                ('Brigade Eldorado', 'Brigade Group', 'Aerospace Park, KIADB, Bengaluru', 'Modern integrated enclave designed for professionals seeking high rental yields.'),
                ('Sobha Town Park', 'Sobha Developers', 'Hosur Road, Bengaluru', 'Luxury New-York styled residential community built with Sobha German technology.')
            ])

        conn.commit()

def get_daily_slots():
    return ["10:00 AM", "12:00 PM", "02:30 PM", "04:30 PM", "06:30 PM"]

# --- Public Routes ---
@app.route('/')
def home():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sites ORDER BY id DESC")
    sites_list = cursor.fetchall()
    return render_template('index.html', sites=sites_list)

@app.route('/sites')
def sites():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sites ORDER BY id DESC")
    sites_list = cursor.fetchall()
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
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT slot_time FROM sessions WHERE session_date = ?", (selected_date,))
    booked_records = cursor.fetchall()
    booked_slots = [r['slot_time'] for r in booked_records]
    
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
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sessions (session_date, slot_time, full_name, email, phone, location, budget, message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session_date, slot_time, full_name, email, phone, location, budget, message))
        conn.commit()
        
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
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
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
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sites (title, builder, location, description) VALUES (?, ?, ?, ?)",
                       (title, builder, location, description))
        conn.commit()
    
    flash("New Featured Site published successfully!", "success")
    return redirect(url_for('admin'))

# CMS Actions: Delete Site
@app.route('/admin/delete-site/<int:site_id>')
def admin_delete_site(site_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sites WHERE id = ?", (site_id,))
        conn.commit()
        
    flash("Site entry removed.", "info")
    return redirect(url_for('admin'))

# CMS Actions: Add Builder / Brand
@app.route('/admin/add-builder', methods=['POST'])
def admin_add_builder():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
        
    builder_name = request.form.get('builder_name')
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO builders (name) VALUES (?)", (builder_name,))
            conn.commit()
            flash("New Builder / Brand added to filter options!", "success")
        except sqlite3.IntegrityError:
            flash("Builder already exists.", "warning")
            
    return redirect(url_for('admin'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash("Logged out from Admin CMS Dashboard.", "info")
    return redirect(url_for('home'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)