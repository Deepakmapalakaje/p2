import os
import sqlite3
import json
import logging
import hashlib
from datetime import datetime, timedelta, time as dt_time
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from zoneinfo import ZoneInfo
import psutil
import secrets

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TRADING_DB = os.getenv("TRADING_DB", "database/upstox_v3_live_trading.db")
USER_DB = os.getenv("USER_DB", "database/users.db")
IST = ZoneInfo("Asia/Kolkata")

# Global variables
pipeline_running = False

# Create user database
def init_user_db():
    """Initialize user database with required tables"""
    os.makedirs(os.path.dirname(USER_DB), exist_ok=True)

    conn = sqlite3.connect(USER_DB)
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        is_active INTEGER DEFAULT 1,
        login_attempts INTEGER DEFAULT 0,
        locked_until DATETIME DEFAULT NULL,
        last_login DATETIME DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create admin user if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'dsar'")
    if not cursor.fetchone():
        admin_password = generate_password_hash('dsar')
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            ('dsar', 'admin@trendvision2004.com', admin_password, 'admin')
        )
        logger.info("Created admin user: dsar/dsar")

    # Create sessions table for persistent sessions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        session_token TEXT UNIQUE NOT NULL,
        expires_at DATETIME NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')

    conn.commit()
    conn.close()

# --- Database & App Helpers ---
def get_db_connection(db_path):
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def is_market_hours():
    """Check if current time is within market hours"""
    try:
        now = datetime.now(IST).time()

        # Market hours: 9:15 AM to 3:30 PM IST
        market_open = dt_time(9, 15)
        market_close = dt_time(15, 30)

        # Check if it's a weekday (Monday-Friday)
        current_day = datetime.now(IST).weekday()

        return (current_day < 5 and  # Monday-Friday
                market_open <= now <= market_close)
    except Exception as e:
        logger.error(f"Error checking market hours: {e}")
        return False

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-for-trendvision")

    # Rate limiting disabled for development
    # Limiter(
    #     get_remote_address,
    #     app=app,
    #     default_limits=["500 per day", "50 per hour", "5 per minute"]
    # )

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com;"
        return response

    # --- API Endpoints ---

    @app.route("/api/summary")
    def api_summary():
        """Enhanced API with cash flow, ITM options, and trend data"""
        try:
            with get_db_connection(TRADING_DB) as conn:
                cursor = conn.cursor()

                # Fetch Latest Cash Flow
                cursor.execute("SELECT * FROM options_cash_flow ORDER BY timestamp DESC LIMIT 1")
                cash_flow_row = cursor.fetchone()
                cash_flow = {
                    'cash': 0.0,
                    'min_cash': 0.0,
                    'max_cash': 0.0,
                    'timestamp': None
                }
                if cash_flow_row:
                    cash_flow = dict(cash_flow_row)

                # Fetch Latest NIFTY Index Data
                cursor.execute("SELECT * FROM latest_candles WHERE instrument_key = 'NSE_INDEX|Nifty 50' ORDER BY last_updated DESC LIMIT 1")
                nifty_row = cursor.fetchone()
                nifty_data = {}
                if nifty_row:
                    nifty_data = dict(nifty_row)

                # Fetch Latest NIFTY Future Data
                cursor.execute("SELECT * FROM latest_candles WHERE instrument_type = 'FUTURE' ORDER BY last_updated DESC LIMIT 1")
                future_row = cursor.fetchone()
                future_data = {}
                if future_row:
                    future_data = dict(future_row)

                # Get ITM Options based on NIFTY price
                itm_options = {'itm_ce': None, 'itm_pe': None}
                if nifty_data and 'close' in nifty_data:
                    nifty_price = nifty_data['close']
                    try:
                        # Find 1st ITM CE (highest strike below NIFTY)
                        cursor.execute("""
                            SELECT * FROM latest_candles
                            WHERE option_type = 'CE' AND strike_price < ? AND instrument_type = 'OPTION'
                            ORDER BY strike_price DESC, last_updated DESC LIMIT 1
                        """, (nifty_price,))
                        ce_row = cursor.fetchone()
                        if ce_row:
                            itm_options['itm_ce'] = dict(ce_row)

                        # Find 1st ITM PE (lowest strike above NIFTY)
                        cursor.execute("""
                            SELECT * FROM latest_candles
                            WHERE option_type = 'PE' AND strike_price > ? AND instrument_type = 'OPTION'
                            ORDER BY strike_price ASC, last_updated DESC LIMIT 1
                        """, (nifty_price,))
                        pe_row = cursor.fetchone()
                        if pe_row:
                            itm_options['itm_pe'] = dict(pe_row)
                    except Exception as e:
                        logger.error(f"Error fetching ITM options: {e}")

                # Fetch Latest Trend
                cursor.execute("SELECT * FROM trend WHERE buy_recommendation IS NOT NULL ORDER BY timestamp DESC LIMIT 1")
                trend_row = cursor.fetchone()
                trend_data = {}
                if trend_row:
                    trend_data = dict(trend_row)

                # Fetch Recent Buy Signals
                cursor.execute("SELECT * FROM trend WHERE buy_recommendation IS NOT NULL ORDER BY timestamp DESC LIMIT 5")
                signals_rows = cursor.fetchall()
                active_signals = [dict(row) for row in signals_rows]

                return jsonify({
                    "ok": True,
                    "cash_flow": cash_flow,
                    "nifty_data": nifty_data,
                    "future_data": future_data,
                    "itm_options": itm_options,
                    "latest_trend": trend_data,
                    "active_signals": active_signals,
                    "timestamp": datetime.now(IST).isoformat()
                })

        except Exception as e:
            logger.error(f"API summary error: {e}", exc_info=True)
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/cash_flow_history")
    def api_cash_flow_history():
        """Get cash flow history for charts"""
        try:
            with get_db_connection(TRADING_DB) as conn:
                cursor = conn.cursor()

                # Get last 100 cash flow entries
                cursor.execute("SELECT * FROM options_cash_flow ORDER BY timestamp DESC LIMIT 100")
                rows = cursor.fetchall()

                data = []
                for row in rows:
                    data.append({
                        'timestamp': row['timestamp'],
                        'cash': row['cash'],
                        'min_cash': row['min_cash'],
                        'max_cash': row['max_cash']
                    })

                return jsonify({"ok": True, "data": data})

        except Exception as e:
            logger.error(f"API cash flow history error: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/option_performance")
    def api_option_performance():
        """Get option performance data"""
        try:
            with get_db_connection(TRADING_DB) as conn:
                cursor = conn.cursor()

                # Get latest data for all options
                cursor.execute("""
                    SELECT instrument_name, strike_price, option_type, close, vwap, volume, delta, buy_volume, sell_volume
                    FROM latest_candles
                    WHERE instrument_type = 'OPTION'
                    ORDER BY volume DESC
                    LIMIT 60
                """)

                options_data = []
                for row in cursor.fetchall():
                    options_data.append(dict(row))

                return jsonify({"ok": True, "options": options_data})

        except Exception as e:
            logger.error(f"API option performance error: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/cash-flow")
    def api_cash_flow():
        """Get latest cash flow data for both 1min and 5min intervals"""
        try:
            with get_db_connection(TRADING_DB) as conn:
                cursor = conn.cursor()

                # Get latest 1-min cash flow
                cursor.execute("""
                    SELECT cash, min_cash, max_cash, timestamp
                    FROM options_cash_flow
                    WHERE interval_type = '1min'
                    ORDER BY timestamp DESC LIMIT 1
                """)
                result_1min = cursor.fetchone()

                # Get latest 5-min cash flow
                cursor.execute("""
                    SELECT cash, min_cash, max_cash, timestamp
                    FROM options_cash_flow
                    WHERE interval_type = '5min'
                    ORDER BY timestamp DESC LIMIT 1
                """)
                result_5min = cursor.fetchone()

                return jsonify({
                    'ok': True,
                    '1min': {
                        'cash': result_1min[0] if result_1min else 0,
                        'min_cash': result_1min[1] if result_1min else 0,
                        'max_cash': result_1min[2] if result_1min else 0,
                        'timestamp': result_1min[3] if result_1min else None
                    },
                    '5min': {
                        'cash': result_5min[0] if result_5min else 0,
                        'min_cash': result_5min[1] if result_5min else 0,
                        'max_cash': result_5min[2] if result_5min else 0,
                        'timestamp': result_5min[3] if result_5min else None
                    }
                })

        except Exception as e:
            logger.error(f"API cash flow error: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/itm-options")
    def api_itm_options():
        """Get 1st ITM CE and PE options"""
        try:
            with get_db_connection(TRADING_DB) as conn:
                cursor = conn.cursor()

                # Get latest NIFTY index close price
                cursor.execute("""
                    SELECT close FROM latest_candles
                    WHERE instrument_key = 'NSE_INDEX|Nifty 50'
                    ORDER BY last_updated DESC LIMIT 1
                """)
                nifty_row = cursor.fetchone()
                nifty_price = nifty_row[0] if nifty_row else 25000  # Fallback price

                # Get recent buy signals to determine ITM strikes
                cursor.execute("""
                    SELECT signal_type, option_key, strike, timestamp, status, cash_flow
                    FROM buy_signals
                    ORDER BY timestamp DESC LIMIT 10
                """)
                signals = cursor.fetchall()

                # Calculate ITM options from signals
                itm_ce_strike = None
                itm_pe_strike = None

                # Find most recent signals for ITM strikes
                for signal in signals:
                    if signal[0] == 'BUY_CE' and signal[2] < nifty_price and not itm_ce_strike:
                        itm_ce_strike = signal[2]
                    if signal[0] == 'BUY_PE' and signal[2] > nifty_price and not itm_pe_strike:
                        itm_pe_strike = signal[2]

                return jsonify({
                    'ok': True,
                    'nifty_price': nifty_price,
                    'itm_ce': {
                        'strike': itm_ce_strike,
                        'symbol': f'NIFTY{int(itm_ce_strike)}CE' if itm_ce_strike else None
                    },
                    'itm_pe': {
                        'strike': itm_pe_strike,
                        'symbol': f'NIFTY{int(itm_pe_strike)}PE' if itm_pe_strike else None
                    },
                    'recent_signals': [
                        {
                            'type': signal[0],
                            'strike': signal[2],
                            'timestamp': signal[3],
                            'status': signal[4],
                            'cash_flow': signal[5]
                        } for signal in signals[:5]  # Last 5 signals
                    ]
                })

        except Exception as e:
            logger.error(f"API ITM options error: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/buy-signals")
    def api_buy_signals():
        """Get recent buy signals"""
        try:
            with get_db_connection(TRADING_DB) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT timestamp, signal_type, option_key, strike, entry_price, target, sl, status, cash_flow
                    FROM buy_signals
                    ORDER BY timestamp DESC LIMIT 20
                """)
                signals = cursor.fetchall()

                return jsonify({
                    'ok': True,
                    'signals': [
                        {
                            'timestamp': signal[0],
                            'type': signal[1],
                            'option_key': signal[2],
                            'strike': signal[3],
                            'entry_price': signal[4],
                            'target': signal[5],
                            'sl': signal[6],
                            'status': signal[7],
                            'cash_flow': signal[8]
                        } for signal in signals
                    ]
                })

        except Exception as e:
            logger.error(f"API buy signals error: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/status")
    def api_status():
        try:
            # Get memory info
            memory = psutil.virtual_memory()
            memory_used_gb = round(memory.used / (1024 ** 3), 2)
            memory_limit_gb = round(memory.total / (1024 ** 3), 2)

            # Check if cleanup is needed (>80% usage)
            cleanup_needed = (memory.used / memory.total) > 0.8

            return jsonify({
                    "ok": True,
                    "pipeline_running": pipeline_running,
                    "market_hours": is_market_hours(),
                    "memory": {
                        "used": memory_used_gb,
                        "total": memory_limit_gb,
                        "percentage": (memory.used / memory.total) * 100,
                        "cleanup_needed": cleanup_needed
                    }
                })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    # --- Routes ---

    # Remove duplicate root route

    # Old login route removed - now use the proper one below

    @app.route("/dashboard")
    def dashboard():
        # Check if user is logged in
        if "user_id" not in session:
            logger.info("User not logged in, redirecting to login")
            return redirect(url_for("login"))

        logger.info(f"User {session.get('username')} accessing dashboard")
        return render_template("dashboard.html")

    @app.route("/")
    def home():
        # Check if user is already logged in
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))  # Redirect to login page

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            username = request.form.get("username")
            email = request.form.get("email")
            password = request.form.get("password")
            confirm_password = request.form.get("confirm_password")

            # Validate input
            if not username or not email or not password or not confirm_password:
                flash("All fields are required", "error")
                return redirect(url_for("signup"))

            if password != confirm_password:
                flash("Passwords do not match", "error")
                return redirect(url_for("signup"))

            if len(password) < 6:
                flash("Password must be at least 6 characters long", "error")
                return redirect(url_for("signup"))

            if len(username) < 3:
                flash("Username must be at least 3 characters long", "error")
                return redirect(url_for("signup"))

            try:
                conn = sqlite3.connect(USER_DB)
                cursor = conn.cursor()

                # Check if user exists - separate checks for better error messages
                cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                existing_username = cursor.fetchone()

                cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
                existing_email = cursor.fetchone()

                if existing_username and existing_email:
                    flash("Username and email already exist", "error")
                elif existing_username:
                    flash("Username already exists", "error")
                elif existing_email:
                    flash("Email already exists", "error")
                else:
                    # Create user
                    password_hash = generate_password_hash(password)
                    cursor.execute(
                        "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                        (username, email, password_hash, 'user')
                    )

                    conn.commit()
                    conn.close()

                    logger.info(f"New user registered: {username}")
                    flash("Account created successfully! Please login.", "success")
                    return redirect(url_for("login"))

                conn.close()
                return redirect(url_for("signup"))

            except Exception as e:
                logger.error(f"Signup error: {e}")
                flash("Error creating account. Please try again.", "error")
                return redirect(url_for("signup"))

        return render_template("signup.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        # Check if user is already logged in
        if "user_id" in session:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")

            if not email or not password:
                flash("Please provide both email and password", "error")
                return redirect(url_for("login"))

            try:
                conn = sqlite3.connect(USER_DB)
                cursor = conn.cursor()

                # Get user by email
                cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
                user = cursor.fetchone()

                if not user:
                    flash("Invalid email or password", "error")
                    conn.close()
                    return redirect(url_for("login"))

                # Check if account is locked
                locked_until = user[8]  # locked_until column
                if locked_until and datetime.fromisoformat(locked_until) > datetime.now():
                    flash("Account locked due to too many failed attempts", "error")
                    conn.close()
                    return redirect(url_for("login"))

                # Check password
                if not check_password_hash(user[3], password):  # password_hash column
                    # Increment login attempts
                    attempts = user[7] + 1  # login_attempts column
                    if attempts >= 5:
                        # Lock account for 30 minutes
                        locked_until = datetime.now() + timedelta(minutes=30)
                        cursor.execute(
                            "UPDATE users SET login_attempts = ?, locked_until = ? WHERE id = ?",
                            (attempts, locked_until.isoformat(), user[0])
                        )
                        flash("Account locked due to too many failed attempts", "error")
                    else:
                        cursor.execute(
                            "UPDATE users SET login_attempts = ? WHERE id = ?",
                            (attempts, user[0])
                        )
                        flash(f"Invalid email or password ({5-attempts} attempts remaining)", "error")

                    conn.commit()
                    conn.close()
                    return redirect(url_for("login"))

                # Successful login - reset login attempts
                cursor.execute(
                    "UPDATE users SET login_attempts = 0, locked_until = NULL, last_login = ? WHERE id = ?",
                    (datetime.now().isoformat(), user[0])
                )

                # Create session record
                session_token = secrets.token_hex(32)
                expires_at = datetime.now() + timedelta(days=7)

                cursor.execute(
                    "INSERT INTO sessions (user_id, session_token, expires_at) VALUES (?, ?, ?)",
                    (user[0], session_token, expires_at.isoformat())
                )

                conn.commit()
                conn.close()

                # Set session variables
                session["user_id"] = user[0]
                session["username"] = user[1]
                session["email"] = user[2]
                session["role"] = user[4]

                logger.info(f"User {user[1]} logged in successfully with email {email}")

                # Redirect based on role
                if user[4] == "admin":
                    return redirect(url_for("admin"))
                else:
                    return redirect(url_for("dashboard"))

            except Exception as e:
                logger.error(f"Login error: {e}")
                flash("Login error. Please try again.", "error")
                return redirect(url_for("login"))

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        if "user_id" in session:
            # Remove session from database
            try:
                conn = sqlite3.connect(USER_DB)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions WHERE user_id = ?", (session["user_id"],))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Logout session cleanup error: {e}")

        session.clear()
        return redirect(url_for("home"))

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        if request.method == "POST":
            email = request.form.get("email")
            otp = request.form.get("otp")
            new_password = request.form.get("new_password")

            # Step 1: Email submitted, send OTP
            if email and not otp and not new_password:
                # Check if user exists
                try:
                    conn = sqlite3.connect(USER_DB)
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
                    user = cursor.fetchone()
                    conn.close()

                    if not user:
                        flash("Email not found in our records", "error")
                        return redirect(url_for("forgot_password"))

                    # Generate OTP (6-digit random number)
                    import random
                    reset_otp = str(random.randint(100000, 999999))

                    # Store OTP in session (in production, use database with expiration)
                    session['reset_otp'] = reset_otp
                    session['reset_email'] = email

                    # Send OTP via email
                    try:
                        import smtplib
                        from email.mime.text import MIMEText
                        from email.mime.multipart import MIMEMultipart

                        # Load email configuration
                        email_config = config.get('EMAIL_CONFIG', {})
                        enable_email = email_config.get('ENABLE_EMAIL', False)

                        if enable_email:
                            SMTP_SERVER = email_config.get('SMTP_SERVER', 'smtp.gmail.com')
                            SMTP_PORT = email_config.get('SMTP_PORT', 587)
                            SENDER_EMAIL = email_config.get('SENDER_EMAIL', '')
                            SENDER_PASSWORD = email_config.get('SENDER_PASSWORD', '')

                            if SENDER_EMAIL and SENDER_PASSWORD:
                                # Create message
                                msg = MIMEMultipart()
                                msg['From'] = SENDER_EMAIL
                                msg['To'] = email
                                msg['Subject'] = "TrendVision Password Reset Code"

                                body = f"""
                                Hello,

                                Your password reset code for TrendVision is: {reset_otp}

                                This code will expire in 10 minutes.

                                If you didn't request this reset, please ignore this email.

                                Best regards,
                                TrendVision Team
                                """
                                msg.attach(MIMEText(body, 'plain'))

                                # Send email
                                server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
                                server.starttls()
                                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                                server.send_message(msg)
                                server.quit()

                                logger.info(f"OTP sent successfully to {email}")
                            else:
                                logger.warning("Email credentials not configured properly")
                                raise Exception("Email credentials missing")
                        else:
                            logger.info(f"Email disabled - OTP for password reset: {reset_otp} (Email: {email}) - Check console logs")

                    except Exception as email_error:
                        logger.error(f"Failed to send OTP email: {email_error}")
                        # Still allow the process to continue for local development
                        logger.info(f"OTP for password reset: {reset_otp} (Email: {email}) - Check console logs")

                    flash("Reset code sent to your email. Please check your inbox.", "success")
                    return redirect(url_for("forgot_password"))

                except Exception as e:
                    logger.error(f"Error in password reset: {e}")
                    flash("Error processing request. Please try again.", "error")

            # Step 2: OTP and new password submitted
            elif otp and new_password and 'reset_otp' in session and 'reset_email' in session:
                stored_otp = session.get('reset_otp')
                stored_email = session.get('reset_email')

                if otp == stored_otp and email == stored_email:
                    try:
                        # Update password
                        conn = sqlite3.connect(USER_DB)
                        cursor = conn.cursor()
                        password_hash = generate_password_hash(new_password)
                        cursor.execute(
                            "UPDATE users SET password_hash = ? WHERE email = ?",
                            (password_hash, email)
                        )
                        conn.commit()
                        conn.close()

                        # Clear session data
                        session.pop('reset_otp', None)
                        session.pop('reset_email', None)

                        flash("Password reset successfully! Please login with your new password.", "success")
                        return redirect(url_for("login"))

                    except Exception as e:
                        logger.error(f"Error updating password: {e}")
                        flash("Error updating password. Please try again.", "error")
                else:
                    flash("Invalid reset code. Please try again.", "error")

            else:
                flash("Invalid request. Please try again.", "error")

        return render_template("forgot.html")

    @app.route("/profile", methods=["GET", "POST"])
    def profile():
        if "user_id" not in session:
            return redirect(url_for("login"))

        try:
            conn = sqlite3.connect(USER_DB)
            cursor = conn.cursor()

            if request.method == "POST":
                # Handle profile update
                username = request.form.get("username")
                email = request.form.get("email")

                if username and email:
                    # Check if username or email already exists (excluding current user)
                    cursor.execute(
                        "SELECT id FROM users WHERE (username = ? OR email = ?) AND id != ?",
                        (username, email, session["user_id"])
                    )
                    if cursor.fetchone():
                        flash("Username or email already exists", "error")
                        conn.close()
                        return redirect(url_for("profile"))

                    # Update user profile
                    cursor.execute(
                        "UPDATE users SET username = ?, email = ?, updated_at = ? WHERE id = ?",
                        (username, email, datetime.now().isoformat(), session["user_id"])
                    )
                    conn.commit()

                    # Update session
                    session["username"] = username

                    flash("Profile updated successfully", "success")

            # Get updated user data
            cursor.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],))
            row = cursor.fetchone()
            conn.close()

            if row:
                # Convert sqlite3.Row to dictionary properly
                user = {
                    'id': row[0],
                    'username': row[1],
                    'email': row[2],
                    'role': row[4],
                    'is_active': row[5],
                    'login_attempts': row[6],
                    'last_login': row[8],
                    'created_at': row[9],
                    'updated_at': row[10]
                }

                return render_template("profile.html", user=user)
            else:
                return redirect(url_for("dashboard"))

        except Exception as e:
            logger.error(f"Profile error: {e}")
            flash("Error updating profile", "error")
            return redirect(url_for("dashboard"))

    # --- AUTOMATED CSV API ENDPOINTS ---

    @app.route("/api/fetch-instruments", methods=["POST"])
    def api_fetch_instruments():
        """Fetch latest instrument keys"""
        if "user_id" not in session or session.get("role") != "admin":
            return jsonify({"ok": False, "error": "Unauthorized"}), 401

        try:
            import subprocess
            result = subprocess.run(['python3', 'instructionkey.py'],
                                  capture_output=True, text=True, cwd='/opt/trendvision')

            if result.returncode == 0:
                return jsonify({"ok": True, "message": "Instruments fetched successfully"})
            else:
                return jsonify({"ok": False, "error": result.stderr}), 500

        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/get-expiries")
    def api_get_expiries():
        """Get available expiry dates"""
        if "user_id" not in session or session.get("role") != "admin":
            return jsonify({"ok": False, "error": "Unauthorized"}), 401

        try:
            import pandas as pd
            if not os.path.exists('NSE.csv'):
                return jsonify({"ok": False, "error": "NSE.csv not found. Please fetch instruments first."})

            df = pd.read_csv('NSE.csv')
            expiries = sorted(df['expiry'].unique().tolist())

            return jsonify({
                "ok": True,
                "expiries": expiries,
                "latest_expiry": expiries[-1] if expiries else None
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    @app.route("/api/extract-options", methods=["POST"])
    def api_extract_options():
        """Extract options for selected expiry"""
        if "user_id" not in session or session.get("role") != "admin":
            return jsonify({"ok": False, "error": "Unauthorized"}), 401

        try:
            data = request.get_json()
            expiry_date = data.get('expiry_date')

            if not expiry_date:
                return jsonify({"ok": False, "error": "Expiry date required"}), 400

            import subprocess
            result = subprocess.run(['python3', 'extract.py', expiry_date],
                                  capture_output=True, text=True, cwd='/opt/trendvision')

            if result.returncode == 0:
                return jsonify({"ok": True, "message": f"Options extracted for {expiry_date}"})
            else:
                return jsonify({"ok": False, "error": result.stderr}), 500

        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/csv-info")
    def api_csv_info():
        """Get current CSV file information"""
        if "user_id" not in session or session.get("role") != "admin":
            return jsonify({"ok": False, "error": "Unauthorized"}), 401

        try:
            csv_path = 'extracted_data.csv'

            if not os.path.exists(csv_path):
                return jsonify({
                    "ok": True,
                    "total_options": 0,
                    "ce_count": 0,
                    "pe_count": 0,
                    "last_updated": None,
                    "file_exists": False
                })

            # Get file info
            file_stat = os.stat(csv_path)
            last_updated = datetime.fromtimestamp(file_stat.st_mtime).isoformat()

            # Read CSV info
            import pandas as pd
            df = pd.read_csv(csv_path)
            ce_count = len(df[df['option_type'] == 'CE'])
            pe_count = len(df[df['option_type'] == 'PE'])

            return jsonify({
                "ok": True,
                "total_options": len(df),
                "ce_count": ce_count,
                "pe_count": pe_count,
                "last_updated": last_updated,
                "file_exists": True
            })

        except Exception as e:
            logger.error(f"CSV info error: {e}")
            return jsonify({"ok": False, "error": str(e)})

    # --- ADMIN ROUTES ---

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if "user_id" in session and session.get("role") == "admin":
            return redirect(url_for("admin"))

        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")

            # Check admin credentials
            if username == "dsar" and password == "dsar":
                session["user_id"] = 1  # Admin user ID
                session["username"] = username
                session["role"] = "admin"
                return redirect(url_for("admin"))
            else:
                flash("Invalid admin credentials", "error")

        return render_template("admin_login.html")

    @app.route("/admin")
    def admin():
        if "user_id" not in session or session.get("role") != "admin":
            return redirect(url_for("admin_login"))

        return render_template("admin.html")

    @app.route("/api/config", methods=["GET", "POST"])
    def api_config():
        if "user_id" not in session or session.get("role") != "admin":
            return jsonify({"ok": False, "error": "Unauthorized"}), 401

        config_path = "config/config.json"

        if request.method == "GET":
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return jsonify({"ok": True, "config": config})
            except Exception as e:
                return jsonify({"ok": False, "error": str(e)})

        elif request.method == "POST":
            try:
                new_config = request.get_json()

                # Load existing config
                existing_config = {}
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        existing_config = json.load(f)

                # Update config
                existing_config.update(new_config)

                # If ACCESS_TOKEN is updated, mark today's date
                if 'ACCESS_TOKEN' in new_config:
                    existing_config['TOKEN_UPDATE_DATE'] = datetime.now(IST).date().isoformat()
                    logger.info(f"✅ Access token updated for {existing_config['TOKEN_UPDATE_DATE']}")

                # Save updated config
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(existing_config, f, indent=2, ensure_ascii=False)

                return jsonify({"ok": True, "message": "Configuration updated successfully"})
            except Exception as e:
                return jsonify({"ok": False, "error": str(e)})

    @app.route("/api/memory-status")
    def api_memory_status():
        try:
            memory = psutil.virtual_memory()
            return jsonify({
                "ok": True,
                "memory_used_gb": round(memory.used / (1024 ** 3), 2),
                "memory_limit_gb": round(memory.total / (1024 ** 3), 2),
                "is_over_limit": (memory.used / memory.total) > 0.9,
                "cleanup_needed": (memory.used / memory.total) > 0.8
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    @app.route("/api/upload-csv", methods=["POST"])
    def api_upload_csv():
        """Upload and process options CSV file"""
        if "user_id" not in session or session.get("role") != "admin":
            return jsonify({"ok": False, "error": "Unauthorized"}), 401

        try:
            if 'csv_file' not in request.files:
                return jsonify({"ok": False, "error": "No file uploaded"}), 400

            file = request.files['csv_file']
            if file.filename == '':
                return jsonify({"ok": False, "error": "No file selected"}), 400

            if not file.filename.endswith('.csv'):
                return jsonify({"ok": False, "error": "File must be CSV format"}), 400

            # Save uploaded file
            csv_path = 'extracted_data.csv'
            file.save(csv_path)

            # Validate CSV structure
            import pandas as pd
            try:
                df = pd.read_csv(csv_path)
                required_columns = ['instrument_key', 'symbol', 'option_type', 'strike', 'last_price']
                missing_columns = [col for col in required_columns if col not in df.columns]

                if missing_columns:
                    return jsonify({
                        "ok": False,
                        "error": f"Missing required columns: {', '.join(missing_columns)}"
                    }), 400

                # Log CSV info
                ce_count = len(df[df['option_type'] == 'CE'])
                pe_count = len(df[df['option_type'] == 'PE'])

                logger.info(f"✅ CSV uploaded: {len(df)} options ({ce_count} CE + {pe_count} PE)")

                return jsonify({
                    "ok": True,
                    "message": f"CSV uploaded successfully: {len(df)} options ({ce_count} CE + {pe_count} PE)",
                    "total_options": len(df),
                    "ce_count": ce_count,
                    "pe_count": pe_count
                })

            except Exception as e:
                return jsonify({"ok": False, "error": f"Invalid CSV format: {str(e)}"}), 400

        except Exception as e:
            logger.error(f"CSV upload error: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/restart-pipeline", methods=["POST"])
    def api_restart_pipeline():
        """Restart trading pipeline service"""
        if "user_id" not in session or session.get("role") != "admin":
            return jsonify({"ok": False, "error": "Unauthorized"}), 401

        try:
            import subprocess
            result = subprocess.run(['sudo', 'systemctl', 'restart', 'trendvision-pipeline'],
                                  capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("Pipeline service restarted by admin")
                return jsonify({"ok": True, "message": "Pipeline restarted successfully"})
            else:
                return jsonify({"ok": False, "error": "Failed to restart pipeline"}), 500

        except Exception as e:
            logger.error(f"Pipeline restart error: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/restart-webapp", methods=["POST"])
    def api_restart_webapp():
        """Restart web application service"""
        if "user_id" not in session or session.get("role") != "admin":
            return jsonify({"ok": False, "error": "Unauthorized"}), 401

        try:
            import subprocess
            result = subprocess.run(['sudo', 'systemctl', 'restart', 'trendvision-web'],
                                  capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("Web app service restarted by admin")
                return jsonify({"ok": True, "message": "Web app restarted successfully"})
            else:
                return jsonify({"ok": False, "error": "Failed to restart web app"}), 500

        except Exception as e:
            logger.error(f"Web app restart error: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/admin/cleanup", methods=["POST"])
    def admin_cleanup():
        if "user_id" not in session or session.get("role") != "admin":
            return jsonify({"ok": False, "error": "Unauthorized"}), 401

        try:
            # Delete old trading data (>30 days)
            cutoff_date = datetime.now() - timedelta(days=30)
            cutoff_date_str = cutoff_date.strftime("%Y-%m-%d")

            # This is just a placeholder - actual cleanup would be more complex
            logger.info(f"Cleanup requested for data older than {cutoff_date_str}")
            return jsonify({"ok": True, "message": "Cleanup completed (placeholder)"})

        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            return jsonify({"ok": False, "error": str(e)})

    @app.route("/admin/export/<export_type>")
    def admin_export(export_type):
        if "user_id" not in session or session.get("role") != "admin":
            return jsonify({"ok": False, "error": "Unauthorized"}), 401

        try:
            import io
            import csv

            output = io.StringIO()
            writer = csv.writer(output)

            if export_type == "users":
                conn = sqlite3.connect(USER_DB)
                cursor = conn.cursor()
                cursor.execute("SELECT username, email, role, created_at FROM users")
                rows = cursor.fetchall()

                writer.writerow(["Username", "Email", "Role", "Created At"])
                for row in rows:
                    writer.writerow(row)

                conn.close()

            elif export_type == "market-data":
                conn = get_db_connection(TRADING_DB)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT instrument_key, timestamp, close, volume
                    FROM latest_candles
                    ORDER BY last_updated DESC LIMIT 1000
                """)
                rows = cursor.fetchall()

                writer.writerow(["Instrument", "Timestamp", "Close Price", "Volume"])
                for row in rows:
                    writer.writerow(row)

                conn.close()

            else:
                return jsonify({"ok": False, "error": "Unknown export type"})

            output.seek(0)
            response = Response(
                output.getvalue(),
                mimetype="text/csv",
                headers={"Content-disposition": f"attachment; filename={export_type}.csv"}
            )

            return response

        except Exception as e:
            logger.error(f"Export error: {e}")
            return jsonify({"ok": False, "error": str(e)})

    @app.route("/terms", methods=["GET", "POST"])
    def terms():
        if request.method == "POST":
            if request.form.get("agree"):
                # User accepted terms, redirect to dashboard or login
                if "user_id" in session:
                    return redirect(url_for("dashboard"))
                else:
                    return redirect(url_for("login"))
            else:
                flash("You must accept the terms and conditions to continue", "error")

        return render_template("terms.html")

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"ok": False, "error": "Endpoint not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Internal server error: {e}")
        return jsonify({"ok": False, "error": "Internal server error"}), 500

    return app

# Initialize user database when module is imported
init_user_db()

# --- Main Execution ---
if __name__ == "__main__":
    app = create_app()

    # Get configuration from environment variables
    host = os.getenv("HOST", "0.0.0.0")  # Listen on all interfaces for VM deployment
    port = int(os.getenv("PORT", 8080))
    debug = os.getenv("DEBUG", "False").lower() == "true"

    print("🚀 Starting TrendVision Server...")
    print(f"📍 Host: {host}")
    print(f"🌐 Port: {port}")
    print(f"🔧 Debug: {debug}")
    print(f"📊 Domain: {os.getenv('DOMAIN', 'trendvision2004.com')}")
    print("=" * 50)

    app.run(host=host, port=port, debug=debug, threaded=True)
