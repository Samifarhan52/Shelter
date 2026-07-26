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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                session_date TEXT NOT NULL,
                slot_time TEXT NOT NULL,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                location TEXT NOT NULL,
                budget TEXT NOT NULL,
                message TEXT,
                booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        cursor.execute("SELECT * FROM users WHERE email = 'admin@shelterhunt.com'")
        if not cursor.fetchone():
            hashed_pwd = generate_password_hash("Admin@123")
            cursor.execute("INSERT INTO users (name, email, phone, password) VALUES (?, ?, ?, ?)",
                           ("Admin", "admin@shelterhunt.com", "0000000000", hashed_pwd))
        conn.commit()

def get_daily_slots():
    return ["10:00 AM", "12:00 PM", "02:30 PM", "04:30 PM", "06:30 PM"]

# --- Page Routes ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/sites')
def sites():
    return render_template('sites.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    return render_template('services.html')

# --- Auth Routes ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        hashed_pwd = generate_password_hash(password)
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (name, email, phone, password) VALUES (?, ?, ?, ?)",
                               (name, email, phone, hashed_pwd))
                conn.commit()
            flash("Account created successfully! Please login.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Email already registered.", "danger")
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('home'))
        else:
            flash("Invalid email or password.", "danger")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

# --- Booking Routes ---
@app.route('/book-session')
def booking_slots():
    if 'user_id' not in session:
        flash("Please log in or sign up to book a Property Strategy Session.", "warning")
        return redirect(url_for('login', next=url_for('booking_slots')))
        
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
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
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
            INSERT INTO sessions (user_id, session_date, slot_time, full_name, email, phone, location, budget, message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], session_date, slot_time, full_name, email, phone, location, budget, message))
        conn.commit()
        
    flash("Your Property Strategy Session is successfully booked!", "success")
    return redirect(url_for('home'))

@app.route('/admin')
def admin_dashboard():
    if session.get('user_email') != 'admin@shelterhunt.com':
        flash("Access Restricted.", "danger")
        return redirect(url_for('home'))
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions ORDER BY booked_at DESC")
    leads = cursor.fetchall()
    return render_template('admin.html', leads=leads)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)