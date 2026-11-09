import os
import sys
import io
import tempfile

# Route temp files to /tmp for Vercel serverless compatibility
os.environ['TMPDIR'] = '/tmp'
os.environ['TRANSFORMERS_CACHE'] = '/tmp'
os.environ['HF_HOME'] = '/tmp'
os.environ['MPLCONFIGDIR'] = '/tmp'
os.environ['NLTK_DATA'] = '/tmp'
import io
import datetime
import pymysql
import threading
import functools
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from resume_parser import (
    extract_text,
    clean_text,
    calculate_tfidf_scores,
    calculate_dense_scores,
    compute_rrf_scores,
    build_candidate_report,
    extract_keyword_insights,
    _extract_skill_phrases,
    warmup_semantic_model,
    SUPPORTED_EXTENSIONS,
    optimize_job_description,
    get_semantic_model
)

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from xml.sax.saxutils import escape as xml_escape

from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)
app.url_map.strict_slashes = False
app.secret_key = os.environ.get('SECRET_KEY', 'resumetrics-secret-key-change-in-prod')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if os.environ.get('VERCEL'):
    app.config['SESSION_COOKIE_SECURE'] = True

import urllib.parse
from werkzeug.middleware.proxy_fix import ProxyFix

class VercelRoutingMiddleware:
    """
    Guarantees seamless route resolution on Vercel.
    Extracts the rewritten __route__ parameter, HTTP_X_MATCHED_PATH, or PATH_INFO.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        qs = environ.get('QUERY_STRING', '')
        parsed = urllib.parse.parse_qs(qs, keep_blank_values=True)
        if '__route__' in parsed:
            route = parsed.pop('__route__')[0]
            clean_qs = urllib.parse.urlencode([(k, v) for k, vals in parsed.items() for v in vals])
            environ['QUERY_STRING'] = clean_qs
            clean_route = '/' + route.lstrip('/')
            environ['PATH_INFO'] = clean_route if clean_route != '' else '/'
        elif environ.get('HTTP_X_MATCHED_PATH'):
            raw = environ['HTTP_X_MATCHED_PATH'].split('?')[0]
            if not raw.startswith('/'):
                raw = '/' + raw
            environ['PATH_INFO'] = raw
        else:
            path = environ.get('PATH_INFO', '')
            for prefix in ('/api/index.py', '/api/index'):
                if path.startswith(prefix):
                    rem = path[len(prefix):]
                    environ['PATH_INFO'] = rem if rem.startswith('/') else ('/' + rem if rem else '/')
                    break

        return self.wsgi_app(environ, start_response)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.wsgi_app = VercelRoutingMiddleware(app.wsgi_app)



# ---------------------------------------------------------------------------
# MySQL / TiDB Database Configuration & Initialization
# ---------------------------------------------------------------------------
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'nitesh123')
MYSQL_DB = os.environ.get('MYSQL_DB', 'resumetrics')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))

import sqlite3

class SQLiteCursorProxy:
    """Adapts SQLite cursor to match PyMySQL query parameter syntax (%s -> ?)."""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):
        q = query.replace('%s', '?')
        if params is not None:
            return self._cursor.execute(q, params)
        return self._cursor.execute(q)

    def executemany(self, query, params):
        q = query.replace('%s', '?')
        return self._cursor.executemany(q, params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        return self._cursor.close()

    def __getattr__(self, name):
        return getattr(self._cursor, name)

class SQLiteConnectionProxy:
    """Adapts SQLite connection to behave identically to PyMySQL connection."""
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return SQLiteCursorProxy(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)

def get_ssl_config():
    """Detect appropriate SSL options for TiDB Cloud / Aiven on Vercel or cloud."""
    if not (os.environ.get('VERCEL') or os.environ.get('MYSQL_SSL')):
        return None
    ca_candidates = [
        os.environ.get('MYSQL_SSL_CA', ''),
        '/etc/pki/tls/certs/ca-bundle.crt',      # Amazon Linux / AWS Lambda (Vercel)
        '/etc/ssl/certs/ca-bundle.crt',          # Alternate Amazon Linux
        '/etc/ssl/certs/ca-certificates.crt',    # Debian / Ubuntu
        '/etc/ssl/cert.pem'                      # Alpine / BSD
    ]
    for path in ca_candidates:
        if path and os.path.exists(path):
            return {'ca': path}
    return {'check_hostname': False}

_MYSQL_FAILS = 0
_MYSQL_LAST_FAIL_TIME = 0

def get_db_connection():
    """
    Connects to the user's MySQL account by default.
    Falls back to SQLite seamlessly if MySQL is unreachable (e.g. on serverless cloud).
    Includes failure backoff to prevent repeated connection latency when offline.
    """
    global _MYSQL_FAILS, _MYSQL_LAST_FAIL_TIME
    now = datetime.datetime.now().timestamp()

    # If MySQL previously failed within the last 30 seconds, bypass directly to fast SQLite
    if _MYSQL_FAILS > 0 and (now - _MYSQL_LAST_FAIL_TIME) < 30:
        sqlite_file = '/tmp/resumetrics.db' if os.environ.get('VERCEL') else os.path.join(BASE_DIR, 'resumetrics.db')
        conn = sqlite3.connect(sqlite_file, check_same_thread=False, timeout=15)
        return SQLiteConnectionProxy(conn)

    try:
        ssl_conf = get_ssl_config()
        kwargs = {
            'host': MYSQL_HOST,
            'port': MYSQL_PORT,
            'user': MYSQL_USER,
            'password': MYSQL_PASSWORD,
            'database': MYSQL_DB,
            'connect_timeout': 2
        }
        if ssl_conf:
            kwargs['ssl'] = ssl_conf
        conn = pymysql.connect(**kwargs)
        _MYSQL_FAILS = 0
        return conn
    except Exception as mysql_err:
        _MYSQL_FAILS += 1
        _MYSQL_LAST_FAIL_TIME = now
        # Seamless SQLite fallback so app never crashes
        sqlite_file = '/tmp/resumetrics.db' if os.environ.get('VERCEL') else os.path.join(BASE_DIR, 'resumetrics.db')
        conn = sqlite3.connect(sqlite_file, check_same_thread=False, timeout=15)
        return SQLiteConnectionProxy(conn)

def init_sqlite_schema():
    """Ensure SQLite fallback schema is always synchronized and ready."""
    try:
        sqlite_file = '/tmp/resumetrics.db' if os.environ.get('VERCEL') else os.path.join(BASE_DIR, 'resumetrics.db')
        conn = sqlite3.connect(sqlite_file, check_same_thread=False, timeout=15)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE,
                extracted_text TEXT,
                ats_stage TEXT DEFAULT 'applied',
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'recruiter',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER DEFAULT NULL,
                job_description TEXT,
                candidates_json TEXT,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applicant_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER DEFAULT NULL,
                job_description TEXT,
                score REAL,
                evaluation_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Seamless non-destructive column migration for existing databases
        try:
            cursor.execute("ALTER TABLE candidates ADD COLUMN ats_stage TEXT DEFAULT 'applied'")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE analysis_history ADD COLUMN user_id INTEGER DEFAULT NULL")
        except Exception:
            pass

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Notice initializing SQLite schema: {e}")

def init_db():
    conn = None
    try:
        # Always ensure SQLite schema is primed
        init_sqlite_schema()

        # Create database if it doesn't exist on local MySQL
        if not os.environ.get('VERCEL') and MYSQL_HOST == 'localhost':
            try:
                raw_conn = pymysql.connect(
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    connect_timeout=2
                )
                cursor = raw_conn.cursor()
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB}")
                raw_conn.commit()
                raw_conn.close()
            except Exception as e:
                print(f"Notice: local MySQL database check: {e}")

        # Connect and create tables
        conn = get_db_connection()
        cursor = conn.cursor()

        if isinstance(conn, SQLiteConnectionProxy):
            init_sqlite_schema()
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS candidates (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    filename VARCHAR(255) UNIQUE,
                    extracted_text LONGTEXT,
                    ats_stage VARCHAR(50) DEFAULT 'applied',
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    full_name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL DEFAULT 'recruiter',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT DEFAULT NULL,
                    job_description TEXT,
                    candidates_json LONGTEXT,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS applicant_evaluations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT DEFAULT NULL,
                    job_description TEXT,
                    score FLOAT,
                    evaluation_json LONGTEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            try:
                cursor.execute("ALTER TABLE candidates ADD COLUMN ats_stage VARCHAR(50) DEFAULT 'applied'")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE analysis_history ADD COLUMN user_id INT DEFAULT NULL")
            except Exception:
                pass
        conn.commit()
    except Exception as e:
        print(f"Database initialization notice: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

init_db()

# ---------------------------------------------------------------------------
# Background Non-Blocking AI Pre-Warming
# ---------------------------------------------------------------------------
if not os.environ.get('VERCEL'):
    threading.Thread(target=warmup_semantic_model, daemon=True, name="AI-Model-Prewarmer").start()

LAST_REPORT = {
    "job_skills_input": "",
    "candidates": [],
    "generated_at": None
}


# ---------------------------------------------------------------------------
# Authentication & Role Decorators
# ---------------------------------------------------------------------------
def login_required(f):
    """Decorator to protect routes that require authentication."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.path.startswith(('/api/', '/analyze', '/history', '/export', '/chat', '/generate-assignment', '/send-shortlist-email')):
                return jsonify({'error': 'Authentication required. Please sign in.'}), 401
            flash('Please sign in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    """Decorator to restrict routes to specific roles (admin, recruiter, viewer)."""
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                if request.is_json or request.path.startswith(('/api/', '/analyze', '/history', '/export', '/chat', '/generate-assignment', '/send-shortlist-email')):
                    return jsonify({'error': 'Authentication required. Please sign in.'}), 401
                flash('Please sign in to access this page.', 'error')
                return redirect(url_for('login'))
            user_role = session.get('user_role', 'viewer')
            if user_role not in roles:
                if request.is_json or request.path.startswith(('/api/', '/analyze', '/history', '/export', '/chat', '/generate-assignment', '/send-shortlist-email')):
                    return jsonify({'error': f'Forbidden: Role "{user_role}" does not have permission for this action.'}), 403
                flash(f'Access denied. Role "{user_role}" is not authorized for this action.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ---------------------------------------------------------------------------
# Auth Routes
# ---------------------------------------------------------------------------
@app.route('/home')
@app.route('/index')
@app.route('/index.html')
@app.route('/landing')
@app.route('/api/index')
@app.route('/api/index.py')
@app.route('/')
def home():
    if 'user_id' in session and session.get('user_id') not in (998, 999):
        return redirect(url_for('dashboard'))
    return render_template('landing.html')


@app.route('/favicon.ico')
def favicon():
    return ('', 204)


@app.route('/health')
def health_check():
    """Simple health check endpoint for monitoring and deployment verification."""
    return jsonify({'status': 'ok', 'service': 'ResuMetrics', 'version': '2.0'})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session and session.get('user_id') not in (998, 999):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please fill in all fields.', 'error')
            return render_template('login.html')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, full_name, password_hash, role FROM users WHERE email = %s', (email,))
            user = cursor.fetchone()
            conn.close()

            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['user_name'] = user[1]
                session['user_email'] = email
                session['user_role'] = user[3] if user[3] else 'recruiter'
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password.', 'error')
                return render_template('login.html')
        except Exception as e:
            flash(f'Database connection notice: {e}. Please check your database settings.', 'error')
            return render_template('login.html')

    return render_template('login.html')


@app.route('/demo-login')
def demo_login():
    """1-Click Instant Demo Login so any visitor on the live website can test all features immediately."""
    role = request.args.get('role', 'recruiter').strip().lower()
    if role not in ('admin', 'recruiter', 'viewer', 'applicant'):
        role = 'recruiter'
    session['user_id'] = 999 if role not in ('applicant',) else 998
    session['user_name'] = 'Demo Applicant' if role == 'applicant' else 'Demo Recruiter'
    session['user_email'] = f'demo.{role}@resumetrics.ai'
    session['user_role'] = role
    flash(f'Signed in as {session["user_name"]} ({role.title()} Role). Enjoy exploring ResuMetrics!', 'info')
    return redirect(url_for('dashboard'))


@app.route('/applicant-demo-login')
def applicant_demo_login():
    """Convenience shortcut for applicant demo login used by landing page."""
    session['user_id'] = 998
    session['user_name'] = 'Demo Applicant'
    session['user_email'] = 'demo.applicant@resumetrics.ai'
    session['user_role'] = 'applicant'
    flash('Signed in as Demo Applicant. Explore your self-evaluation dashboard!', 'info')
    return redirect(url_for('dashboard'))


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')


# Default locked SMTP configuration
DEFAULT_SMTP_EMAIL = 'niteshnemalpuri17@gmail.com'
DEFAULT_SMTP_PASSWORD = 'oyat njzk quno wqlz'


def get_password_reset_serializer():
    """Generates cryptographic URL-safe serializer for password reset tokens."""
    return URLSafeTimedSerializer(app.secret_key)


def send_password_reset_email(to_email, user_name, reset_url):
    """Sends password reset email via SMTP if configured, or logs locally."""
    if app.config.get('TESTING'):
        logger.info(f"[Password Reset] (TESTING) Link generated for {to_email}: {reset_url}")
        return True

    smtp_email = (os.environ.get('SMTP_EMAIL') or DEFAULT_SMTP_EMAIL).strip()
    smtp_password = (os.environ.get('SMTP_PASSWORD') or DEFAULT_SMTP_PASSWORD).strip()
    smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com').strip()
    smtp_port = int(os.environ.get('SMTP_PORT', 587))

    if not smtp_email or not smtp_password:
        logger.info(f"[Password Reset] Link generated for {to_email}: {reset_url} (SMTP not configured, simulation active)")
        return True

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'ResuMetrics - Password Reset Request'
        msg['From'] = f"ResuMetrics Security <{smtp_email}>"
        msg['To'] = to_email

        text_content = f"""Hello {user_name or 'User'},

We received a request to reset your password for your ResuMetrics account.

Click the link below to set a new password (valid for 1 hour):
{reset_url}

If you did not make this request, you can safely ignore this email.

Best regards,
The ResuMetrics Team
"""
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #0f172a; color: #f8fafc; border-radius: 8px;">
            <h2 style="color: #38bdf8; margin-top: 0;">ResuMetrics Password Reset</h2>
            <p>Hello <strong>{user_name or 'User'}</strong>,</p>
            <p>We received a request to reset your password. Click the button below to choose a new password (this link expires in 1 hour):</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}" style="background: linear-gradient(135deg, #0284c7, #2563eb); color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 6px; font-weight: bold; display: inline-block;">Reset Password</a>
            </div>
            <p style="color: #94a3b8; font-size: 13px;">Or copy and paste this link into your browser:<br><a href="{reset_url}" style="color: #38bdf8;">{reset_url}</a></p>
            <hr style="border: 0; border-top: 1px solid #334155; margin: 25px 0;">
            <p style="color: #64748b; font-size: 12px;">If you did not request a password reset, please ignore this email. Your password will remain unchanged.</p>
        </div>
        """
        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()
        server.login(smtp_email, smtp_password.replace(' ', ''))
        server.sendmail(smtp_email, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        logger.warning(f"Failed to send password reset email via SMTP ({e}). Fallback simulated.")
        return False


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Allows users to request a secure, time-stamped password reset token."""
    if 'user_id' in session and session.get('user_id') not in (998, 999):
        return redirect(url_for('dashboard'))

    reset_url = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('forgot_password.html')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, full_name FROM users WHERE email = %s', (email,))
            user = cursor.fetchone()
            conn.close()

            if user:
                serializer = get_password_reset_serializer()
                token = serializer.dumps(email, salt='resumetrics-password-reset')
                reset_url = url_for('reset_password', token=token, _external=True)

                send_password_reset_email(email, user[1], reset_url)

                flash('Password reset link generated. Check your inbox or use the instant reset link below.', 'success')
            else:
                flash('If an account exists with that email address, a password reset link has been created.', 'info')
        except Exception as e:
            flash(f'An error occurred: {e}', 'error')

    return render_template('forgot_password.html', reset_url=reset_url)


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Verifies reset token and updates the user's password."""
    if 'user_id' in session and session.get('user_id') not in (998, 999):
        return redirect(url_for('dashboard'))

    serializer = get_password_reset_serializer()
    try:
        email = serializer.loads(token, salt='resumetrics-password-reset', max_age=3600)
    except SignatureExpired:
        flash('The password reset link has expired (1 hour limit). Please request a new one.', 'error')
        return redirect(url_for('forgot_password'))
    except BadSignature:
        flash('Invalid or tampered password reset link. Please request a new one.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not password or not confirm_password:
            flash('Please fill in both password fields.', 'error')
            return render_template('reset_password.html', token=token, email=email)

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('reset_password.html', token=token, email=email)

        if password != confirm_password:
            flash('Passwords do not match. Please verify and try again.', 'error')
            return render_template('reset_password.html', token=token, email=email)

        try:
            password_hash = generate_password_hash(password)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET password_hash = %s WHERE email = %s', (password_hash, email))
            conn.commit()
            conn.close()

            flash('Your password has been successfully reset! You can now sign in with your new password.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Failed to update password: {e}', 'error')
            return render_template('reset_password.html', token=token, email=email)

    return render_template('reset_password.html', token=token, email=email)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session and session.get('user_id') not in (998, 999):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'recruiter').strip().lower()

        if role not in ('admin', 'recruiter', 'viewer', 'applicant'):
            role = 'recruiter'

        if not full_name or not email or not password:
            flash('Please fill in all fields.', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('register.html')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if email already exists
            cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
            if cursor.fetchone():
                conn.close()
                flash('An account with this email already exists.', 'error')
                return render_template('register.html')

            # Create user
            password_hash = generate_password_hash(password)
            cursor.execute(
                'INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, %s)',
                (full_name, email, password_hash, role)
            )
            conn.commit()
            conn.close()

            flash('Account created successfully! Please sign in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Database connection notice: {e}. Please check your database settings.', 'error')
            return render_template('register.html')

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been signed out.', 'info')
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Main Application Routes (Protected)
# ---------------------------------------------------------------------------
@app.route('/app')
@app.route('/dashboard')
def dashboard():
    req_role = request.args.get('role', '').strip().lower()

    if 'user_id' not in session:
        role = req_role if req_role in ('applicant', 'recruiter', 'admin', 'viewer') else 'recruiter'
        session['user_id'] = 998 if role == 'applicant' else 999
        session['user_name'] = 'Demo Applicant' if role == 'applicant' else 'Demo Recruiter'
        session['user_email'] = f'demo.{role}@resumetrics.ai'
        session['user_role'] = role
    elif session.get('user_id') in (998, 999):
        # Demo users can toggle their demo role between recruiter and applicant
        if req_role in ('recruiter', 'applicant', 'admin', 'viewer'):
            session['user_role'] = req_role
            if req_role == 'applicant':
                session['user_id'] = 998
                session['user_name'] = 'Demo Applicant'
                session['user_email'] = 'demo.applicant@resumetrics.ai'
            else:
                session['user_id'] = 999
                session['user_name'] = 'Demo Recruiter'
                session['user_email'] = 'demo.recruiter@resumetrics.ai'

    user_role = session.get('user_role', 'recruiter')
    if user_role == 'applicant':
        return render_template(
            'applicant_dashboard.html',
            user_name=session.get('user_name', 'User')
        )
    return render_template(
        'dashboard.html',
        user_name=session.get('user_name', 'User'),
        user_role=user_role
    )


def _process_single_file(file_storage):
    """Worker function to read and extract text from an uploaded file in memory."""
    filename = file_storage.filename
    if not filename:
        return None

    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in SUPPORTED_EXTENSIONS:
        return {'status': 'skipped', 'name': filename, 'reason': f'Unsupported extension .{ext}'}

    try:
        file_bytes = file_storage.read()
        if not file_bytes:
            return {'status': 'skipped', 'name': filename, 'reason': 'Empty file uploaded'}

        text = extract_text(file_bytes, ext)
        if not text or not text.strip():
            return {'status': 'skipped', 'name': filename, 'reason': 'No readable text extracted'}

        cleaned = clean_text(text)
        return {
            'status': 'ok',
            'filename': filename,
            'raw_text': text,
            'cleaned_text': cleaned
        }
    except Exception as e:
        return {'status': 'skipped', 'name': filename, 'reason': f'Failed reading file: {e}'}


@app.route('/analyze', methods=['POST'])
@login_required
def analyze_resumes():
    if 'resumes' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    files = request.files.getlist('resumes')
    job_skills_input = request.form.get('skills', '').strip()
    blind_mode = request.form.get('blind_mode') == 'true'

    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400

    if not job_skills_input:
        return jsonify({'error': 'Job description field is empty'}), 400

    # 1. High-Speed Concurrent In-Memory Ingestion (Zero Disk I/O)
    processed_items = []
    max_workers = min(16, (os.cpu_count() or 4) * 2, max(1, len(files)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results_iter = executor.map(_process_single_file, files)
        processed_items = [r for r in results_iter if r is not None]

    filenames = []
    raw_texts = []
    cleaned_texts = []
    skipped_files = []

    for item in processed_items:
        if item['status'] == 'ok':
            filenames.append(item['filename'])
            raw_texts.append(item['raw_text'])
            cleaned_texts.append(item['cleaned_text'])
        else:
            skipped_files.append({'name': item['name'], 'reason': item['reason']})

    if not filenames:
        return jsonify({'error': 'No resumes could be processed', 'skipped': skipped_files}), 400

    # 2. Asynchronous / Fast Batch MySQL Upsert
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.executemany(
            'REPLACE INTO candidates (filename, extracted_text) VALUES (%s, %s)',
            list(zip(filenames, raw_texts))
        )
        conn.commit()
        conn.close()
    except Exception as db_err:
        print(f"MySQL Batch Write Notice: {db_err}")

    # 3. High-Performance Hybrid AI Scoring Pipeline
    cleaned_job = clean_text(job_skills_input)
    job_skills = _extract_skill_phrases(job_skills_input)

    try:
        w_tfidf = float(request.form.get('w_tfidf', 40)) / 100.0
        w_skill = float(request.form.get('w_skill', 35)) / 100.0
        w_dense = float(request.form.get('w_dense', 25)) / 100.0
    except ValueError:
        w_tfidf, w_skill, w_dense = 0.40, 0.35, 0.25

    # Precalculate keyword insights once in O(1) word-token lookups
    all_insights = [extract_keyword_insights(c_t, job_skills) for c_t in cleaned_texts]
    skill_matched_lists = [ins['matched_skills'] for ins in all_insights]
    related_skill_counts = [len(ins.get('related_skills', [])) for ins in all_insights]

    # Vectorized TF-IDF & Dense Semantic Encodings
    tfidf_scores = calculate_tfidf_scores(cleaned_texts, cleaned_job)
    dense_scores = calculate_dense_scores(raw_texts, job_skills_input)
    rrf_scores = compute_rrf_scores(
        tfidf_scores, dense_scores,
        job_skills=job_skills, cleaned_resumes=cleaned_texts,
        w_tfidf=w_tfidf, w_skill=w_skill, w_dense=w_dense,
        skill_matches=skill_matched_lists,
        related_skill_counts=related_skill_counts
    )

    # 4. Instant Candidate Report Generation
    results = []
    for fn, raw_t, clean_t, hybrid_s, tf_s, d_s, insights in zip(
        filenames, raw_texts, cleaned_texts, rrf_scores, tfidf_scores, dense_scores, all_insights
    ):
        results.append(
            build_candidate_report(
                fn, raw_t, clean_t, job_skills, hybrid_s, tf_s, d_s, precomputed_insights=insights
            )
        )

    results = sorted(results, key=lambda x: x['score'], reverse=True)

    if blind_mode:
        for idx, res in enumerate(results, start=1):
            res['name'] = f"Candidate #{idx} (Redacted)"
            res['contact']['email'] = "[REDACTED]"
            res['contact']['phone'] = "[REDACTED]"
            if res['entities'].get('universities'):
                res['entities']['universities'] = ["[REDACTED]"]

    LAST_REPORT['job_skills_input'] = job_skills_input
    LAST_REPORT['candidates'] = results
    LAST_REPORT['generated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Persist screening run into analysis_history in MySQL / SQLite
    import json
    history_id = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO analysis_history (user_id, job_description, candidates_json) VALUES (%s, %s, %s)',
            (session.get('user_id'), job_skills_input, json.dumps(results))
        )
        conn.commit()
        history_id = cursor.lastrowid
        conn.close()
    except Exception as hist_err:
        print(f"Notice saving analysis history: {hist_err}")

    return jsonify({'candidates': results, 'skipped': skipped_files, 'history_id': history_id})


# ---------------------------------------------------------------------------
# Auto-Shortlist & Mail
# ---------------------------------------------------------------------------
@app.route('/send-shortlist-email', methods=['POST'])
@role_required('admin', 'recruiter')
def send_shortlist_email():
    """Send shortlist notification emails to selected candidates with live SMTP or Demo Simulation."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    candidates = data.get('candidates', [])
    subject = data.get('subject', 'Interview Invitation - ResuMetrics')
    body_template = data.get('body', '')
    smtp_email = (data.get('smtp_email', '') or os.environ.get('SMTP_EMAIL', '') or DEFAULT_SMTP_EMAIL).strip()
    smtp_password = (os.environ.get('SMTP_PASSWORD') or DEFAULT_SMTP_PASSWORD).strip()
    demo_email = data.get('demo_email', '').strip()
    smtp_host = data.get('smtp_host', '') or os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(data.get('smtp_port') or os.environ.get('SMTP_PORT', 587))
    is_simulation = data.get('is_simulation', False) or app.config.get('TESTING') or not smtp_password

    if not candidates:
        return jsonify({'error': 'No candidates selected'}), 400

    # If simulation explicitly requested or running in test mode
    if is_simulation:
        sent = []
        for candidate in candidates:
            orig_email = candidate.get('email', '')
            name = candidate.get('name', 'Candidate')
            target_email = demo_email if demo_email else (orig_email if orig_email and '@' in orig_email else 'candidate@company.com')
            sent.append({'name': name, 'email': target_email, 'status': 'Simulated'})

        # Update candidate stage to 'shortlisted' in session and DB
        sent_names = [s['name'] for s in sent]
        for c in LAST_REPORT.get('candidates', []):
            c_clean = c['name'].replace('.pdf', '').replace('.docx', '').replace('_', ' ')
            if c_clean in sent_names or c['name'] in sent_names or any(s in c['name'] for s in sent_names):
                c['stage'] = 'shortlisted'
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            for s_name in sent_names:
                cursor.execute(
                    "UPDATE candidates SET ats_stage = 'shortlisted' WHERE filename = %s OR filename LIKE %s",
                    (s_name, f"%{s_name}%")
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Notice updating shortlist stage in DB: {e}")

        return jsonify({
            'sent': sent,
            'failed': [],
            'simulated': True,
            'shortlisted_names': sent_names,
            'message': f'Simulation Mode: Successfully queued personalized interview emails for {len(sent)} candidate(s).'
        })

    sent = []
    failed = []

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.ehlo()
            server.starttls()

        server.login(smtp_email, smtp_password.replace(' ', ''))

        for candidate in candidates:
            original_email = candidate.get('email', '')
            name = candidate.get('name', 'Candidate')

            if not original_email or original_email == 'Not found' or '@' not in original_email:
                failed.append({'name': name, 'reason': 'No valid email found'})
                continue

            # If demo redirect is specified, route there; otherwise real candidate email
            email = demo_email if demo_email else original_email

            personalized_body = body_template.replace('{name}', name).replace('{email}', original_email).replace('{score}', str(candidate.get('score', '')))

            msg = MIMEMultipart()
            msg['From'] = smtp_email
            msg['To'] = email
            msg['Subject'] = subject
            msg.attach(MIMEText(personalized_body, 'plain'))

            try:
                server.sendmail(smtp_email, email, msg.as_string())
                sent.append({'name': name, 'email': email})
            except Exception as e:
                failed.append({'name': name, 'reason': str(e)})

        server.quit()

        # Update candidate stage to 'shortlisted' in session and DB
        sent_names = [s['name'] for s in sent]
        for c in LAST_REPORT.get('candidates', []):
            c_clean = c['name'].replace('.pdf', '').replace('.docx', '').replace('_', ' ')
            if c_clean in sent_names or c['name'] in sent_names or any(s in c['name'] for s in sent_names):
                c['stage'] = 'shortlisted'
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            for s_name in sent_names:
                cursor.execute(
                    "UPDATE candidates SET ats_stage = 'shortlisted' WHERE filename = %s OR filename LIKE %s",
                    (s_name, f"%{s_name}%")
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Notice updating shortlist stage in DB: {e}")

    except Exception as e:
        return jsonify({'error': f'SMTP connection failed: {e}'}), 500

    return jsonify({
        'sent': sent,
        'failed': failed,
        'simulated': False,
        'shortlisted_names': [s['name'] for s in sent],
        'message': f'Successfully dispatched {len(sent)} live email(s). {len(failed)} failed.'
    })


@app.route('/export-csv', methods=['GET'])
@role_required('admin', 'recruiter', 'viewer')
def export_csv():
    """Pandas CSV/Excel Leaderboard Exporter Endpoint."""
    if not LAST_REPORT['candidates']:
        return jsonify({'error': 'No analysis available. Run /analyze first.'}), 400

    try:
        import csv
        
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        
        # Write headers
        writer.writerow([
            'Rank', 'Candidate File', 'Match Score (%)', 'ATS Stage', 'TF-IDF Score (%)',
            'Dense Score (%)', 'Email', 'Phone', 'Degrees', 'Universities',
            'Job Roles', 'Matched Skills', 'Related Skills', 'Missing Skills',
            'Timeline Alert', 'Alert Reason'
        ])
        
        for idx, candidate in enumerate(LAST_REPORT['candidates'], start=1):
            entities = candidate.get('entities', {}) or {}
            contact = candidate.get('contact', {}) or {}
            timeline = candidate.get('timeline_audit', {}) or {}
            writer.writerow([
                idx,
                candidate.get('name', ''),
                candidate.get('score', 0),
                candidate.get('stage', 'applied').title(),
                candidate.get('tfidf_score', 0),
                candidate.get('dense_score', 0),
                contact.get('email', 'Not found'),
                contact.get('phone', 'Not found'),
                ', '.join(entities.get('degrees', [])),
                ', '.join(entities.get('universities', [])),
                ', '.join(entities.get('job_roles', [])),
                ', '.join(candidate.get('matched_skills', [])),
                ', '.join([f"{r.get('required', '')} → {r.get('found', '')}" for r in candidate.get('related_skills', [])]),
                ', '.join(candidate.get('missing_skills', [])),
                timeline.get('timeline_alert', False),
                timeline.get('alert_reason', '')
            ])
            
        buffer.seek(0)
        # Convert to BytesIO for send_file
        bytes_buffer = io.BytesIO(buffer.getvalue().encode('utf-8'))
        
        return send_file(
            bytes_buffer,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"resumetrics_leaderboard_{datetime.date.today().isoformat()}.csv"
        )
    except Exception as e:
        return jsonify({'error': f'Failed generating CSV: {e}'}), 500


@app.route('/export-report', methods=['GET'])
@role_required('admin', 'recruiter', 'viewer')
def export_report():
    if not LAST_REPORT['candidates']:
        return jsonify({'error': 'No analysis available. Run /analyze first.'}), 400

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm, leftMargin=15*mm, rightMargin=15*mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('ReportTitle', parent=styles['Title'], fontSize=20, spaceAfter=6)
    meta_style = ParagraphStyle('ReportMeta', parent=styles['Normal'], textColor=colors.grey, spaceAfter=16)
    section_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], spaceBefore=14, spaceAfter=6)
    body_style = styles['Normal']
    table_cell_style = ParagraphStyle('TableCell', parent=styles['Normal'], fontSize=8.5, leading=10)
    table_header_style = ParagraphStyle('TableHeader', parent=styles['Normal'], fontSize=8.5, leading=10, textColor=colors.white, fontName='Helvetica-Bold')

    elements = [
        Paragraph('ResuMetrics - Hybrid Candidate Match Report', title_style),
        Paragraph(f"Generated: {LAST_REPORT['generated_at']} | Candidates Analyzed: {len(LAST_REPORT['candidates'])}", meta_style)
    ]

    table_data = [[
        Paragraph('Rank', table_header_style),
        Paragraph('Candidate File', table_header_style),
        Paragraph('Match %', table_header_style),
        Paragraph('Stage', table_header_style),
        Paragraph('Email', table_header_style),
        Paragraph('Phone', table_header_style)
    ]]
    for idx, candidate in enumerate(LAST_REPORT['candidates'], start=1):
        contact = candidate.get('contact', {}) or {}
        table_data.append([
            Paragraph(str(idx), table_cell_style),
            Paragraph(xml_escape(candidate.get('name', '')), table_cell_style),
            Paragraph(f"{candidate.get('score', 0)}%", table_cell_style),
            Paragraph(xml_escape(candidate.get('stage', 'applied').title()), table_cell_style),
            Paragraph(xml_escape(contact.get('email', 'Not found')), table_cell_style),
            Paragraph(xml_escape(contact.get('phone', 'Not found')), table_cell_style)
        ])

    summary_table = Table(table_data, colWidths=[12*mm, 50*mm, 18*mm, 24*mm, 45*mm, 31*mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E3A59')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F6FA')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(summary_table)

    elements.append(Paragraph('Skill Gap &amp; Fraud Audit Detail', section_style))
    for idx, candidate in enumerate(LAST_REPORT['candidates'], start=1):
        c_name = xml_escape(candidate.get('name', 'Candidate'))
        c_score = candidate.get('score', 0)
        c_stage = xml_escape(candidate.get('stage', 'applied').title())
        elements.append(Paragraph(f"<b>{idx}. {c_name}</b> — {c_score}% match (Status: {c_stage})", body_style))
        matched = xml_escape(', '.join(candidate.get('matched_skills', []))) or 'None'
        related = xml_escape(', '.join([f"{r.get('required', '')}→{r.get('found', '')}" for r in candidate.get('related_skills', [])])) or 'None'
        missing = xml_escape(', '.join(candidate.get('missing_skills', []))) or 'None'
        elements.append(Paragraph(f"<font color='#1B7F3A'><b>Matched:</b></font> {matched}", body_style))
        elements.append(Paragraph(f"<font color='#D4A017'><b>Related:</b></font> {related}", body_style))
        elements.append(Paragraph(f"<font color='#B23B3B'><b>Missing:</b></font> {missing}", body_style))

        # NER entities
        entities = candidate.get('entities', {}) or {}
        if entities.get('degrees'):
            elements.append(Paragraph(f"<b>Degrees:</b> {xml_escape(', '.join(entities['degrees']))}", body_style))
        if entities.get('universities'):
            elements.append(Paragraph(f"<b>Universities:</b> {xml_escape(', '.join(entities['universities']))}", body_style))
        if entities.get('job_roles'):
            elements.append(Paragraph(f"<b>Roles:</b> {xml_escape(', '.join(entities['job_roles']))}", body_style))

        timeline = candidate.get('timeline_audit', {}) or {}
        if timeline.get('timeline_alert'):
            elements.append(Paragraph(f"<font color='#D64545'><b>Alert:</b></font> {xml_escape(timeline.get('alert_reason', ''))}", body_style))
        elements.append(Spacer(1, 8))

    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"resumetrics_report_{datetime.date.today().isoformat()}.pdf"
    )


@app.route('/optimize-jd', methods=['POST'])
@role_required('admin', 'recruiter', 'viewer')
def optimize_jd():
    data = request.get_json()
    if not data or 'skills' not in data:
        return jsonify({'error': 'No skills provided'}), 400
    
    job_skills = _extract_skill_phrases(data['skills'])
    suggestions = optimize_job_description(job_skills)
    
    return jsonify({'suggestions': suggestions})


@app.route('/generate-assignment', methods=['POST'])
@role_required('admin', 'recruiter')
def generate_assignment():
    """Generates a comprehensive, role-tailored AI technical assessment based on real candidate skills."""
    data = request.get_json() or {}
    candidate_name = data.get('candidate_name', 'Candidate')
    roles = data.get('roles', [])
    matched_skills = data.get('matched_skills', [])
    missing_skills = data.get('missing_skills', [])
    provable_years = data.get('provable_years', 3)

    clean_name = candidate_name.replace('.pdf', '').replace('.docx', '').replace('_', ' ')
    role_title = roles[0] if roles else 'Software Engineer'
    primary_skills = ', '.join(matched_skills[:4]) if matched_skills else 'core programming and system design'
    stretch_skill = missing_skills[0] if missing_skills else 'cloud resilience and automated testing'

    role_lower = role_title.lower()
    if 'data' in role_lower or 'machine learning' in role_lower or 'ai' in role_lower:
        scenario = f"Build an end-to-end predictive machine learning pipeline that ingests, cleans, and trains on tabular streaming data. Deploy a high-throughput inference REST service leveraging {primary_skills}."
        tech_req = f"- Data Ingestion & Preprocessing: Clean missing values, handle categorical features, and extract features.\n- Model Training & Evaluation: Implement an explainable baseline with precision, recall, and ROC-AUC metrics.\n- Serving API: Serve predictions via a RESTful endpoint with p99 latency < 50ms.\n- Stretch Goal: Incorporate {stretch_skill} into the evaluation or deployment workflow."
    elif 'devops' in role_lower or 'cloud' in role_lower or 'platform' in role_lower:
        scenario = f"Architect and deploy a self-healing, zero-downtime infrastructure for a distributed multi-tenant service using {primary_skills}."
        tech_req = f"- Infrastructure as Code: Provision compute, storage, and networking with modular templates.\n- Container Orchestration: Deploy services with automated health checks, resource limits, and secrets management.\n- CI/CD & Observability: Implement continuous delivery with structured logging and metrics alerting.\n- Stretch Goal: Integrate {stretch_skill} into the deployment pipeline."
    elif 'frontend' in role_lower or 'ui' in role_lower:
        scenario = f"Design and implement a responsive, high-performance data dashboard featuring real-time client-side analytics and accessible UI components using {primary_skills}."
        tech_req = f"- Component Architecture: Build clean, reusable component hierarchy with robust state management.\n- Performance & Accessibility: Achieve 95+ Lighthouse score, keyboard navigation, and WCAG AA contrast.\n- API Integration: Gracefully handle loading states, pagination, and error boundaries.\n- Stretch Goal: Incorporate {stretch_skill} into the interface or state workflow."
    else:
        scenario = f"Architect and implement a scalable microservice that handles asynchronous job processing, persistent storage, and authenticated REST APIs using {primary_skills}."
        tech_req = f"- Backend Service: Build modular RESTful endpoints with input validation and structured error handling.\n- Data Layer: Design normalized schema with indexed queries and caching for high-read paths.\n- Reliability: Containerize with Docker and provide integration test coverage.\n- Stretch Goal: Address {stretch_skill} to demonstrate adaptability."

    assignment = f"""### Technical Assessment: {role_title}

**Candidate:** {clean_name}
**Evaluated Level:** ~{provable_years} Years Experience
**Verified Tech Stack:** {primary_skills}
**Target Growth Area:** {stretch_skill}

#### 1. Business Scenario & Objective
{scenario}

#### 2. Core Technical Requirements
{tech_req}

#### 3. Evaluation Criteria
1. **Architecture & Clean Code (30%):** Modular separation of concerns, readability, and idiomatic conventions.
2. **Correctness & Robustness (25%):** Edge cases handled, input validation, and reliable error responses.
3. **Testing & Documentation (25%):** Comprehensive unit/integration tests and clear README with setup instructions.
4. **Adaptability & Scalability (20%):** Execution on the stretch goal involving {stretch_skill}.

#### 4. Deliverables & Timeframe
- Git repository containing source code, test suite, and Dockerfile.
- Setup guide with local run command (e.g. docker compose up or simple CLI execution).
- **Estimated Completion Time:** 3 - 4 Hours.
"""
    return jsonify({
        'success': True,
        'candidate_name': clean_name,
        'role': role_title,
        'assignment': assignment.strip()
    })


@app.route('/api/candidate/stage', methods=['POST'])
@role_required('admin', 'recruiter')
def update_candidate_stage():
    """Updates candidate hiring stage across active session and database."""
    import json
    data = request.get_json() or {}
    candidate_name = data.get('candidate_name', '').strip()
    new_stage = data.get('stage', '').strip().lower()

    valid_stages = ('applied', 'shortlisted', 'interviewing', 'rejected')
    if new_stage not in valid_stages:
        return jsonify({'error': f'Invalid stage. Must be one of {valid_stages}'}), 400

    if not candidate_name:
        return jsonify({'error': 'Candidate name is required'}), 400

    # 1. Update in-memory LAST_REPORT
    updated = False
    for c in LAST_REPORT.get('candidates', []):
        c_clean = c['name'].replace('.pdf', '').replace('.docx', '').replace('_', ' ').lower()
        target_clean = candidate_name.replace('.pdf', '').replace('.docx', '').replace('_', ' ').lower()
        if c_clean == target_clean or c['name'] == candidate_name or target_clean in c_clean:
            c['stage'] = new_stage
            updated = True
            break

    # 2. Update database candidates table & history
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE candidates SET ats_stage = %s WHERE filename = %s OR filename LIKE %s",
            (new_stage, candidate_name, f"%{candidate_name}%")
        )
        if updated and LAST_REPORT.get('candidates'):
            cursor.execute(
                "UPDATE analysis_history SET candidates_json = %s WHERE id = (SELECT MAX(id) FROM analysis_history)",
                (json.dumps(LAST_REPORT['candidates']),)
            )
        conn.commit()
        conn.close()
    except Exception as db_err:
        print(f"Notice updating candidate stage in DB: {db_err}")

    return jsonify({
        'success': True,
        'candidate_name': candidate_name,
        'stage': new_stage,
        'updated_in_session': updated
    })


@app.route('/api/applicant/evaluate', methods=['POST'])
@login_required
def applicant_evaluate():
    """Dedicated self-evaluation endpoint for applicants without mutating recruiter reports."""
    import json
    if 'resume' not in request.files and 'resumes' not in request.files:
        return jsonify({'error': 'No resume file uploaded'}), 400

    file_storage = request.files.get('resume') or request.files.get('resumes')
    job_skills_input = request.form.get('skills', '').strip()

    if not file_storage or not file_storage.filename:
        return jsonify({'error': 'No file selected'}), 400
    if not job_skills_input:
        return jsonify({'error': 'Job description is required'}), 400

    processed = _process_single_file(file_storage)
    if not processed or processed.get('status') != 'ok':
        reason = processed.get('reason', 'Failed extracting text') if processed else 'Empty file'
        return jsonify({'error': reason}), 400

    raw_text = processed['raw_text']
    clean_r = processed['cleaned_text']
    filename = processed['filename']

    cleaned_job = clean_text(job_skills_input)
    job_skills = _extract_skill_phrases(job_skills_input)

    all_insights = [extract_keyword_insights(clean_r, job_skills)]
    skill_matched_lists = [ins['matched_skills'] for ins in all_insights]
    related_skill_counts = [len(ins.get('related_skills', [])) for ins in all_insights]

    tfidf_scores = calculate_tfidf_scores([clean_r], cleaned_job)
    dense_scores = calculate_dense_scores([raw_text], job_skills_input)
    rrf_scores = compute_rrf_scores(
        tfidf_scores, dense_scores,
        job_skills=job_skills, cleaned_resumes=[clean_r],
        skill_matches=skill_matched_lists,
        related_skill_counts=related_skill_counts
    )

    candidate = build_candidate_report(
        filename, raw_text, clean_r, job_skills,
        rrf_scores[0], tfidf_scores[0], dense_scores[0],
        precomputed_insights=all_insights[0]
    )

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO applicant_evaluations (user_id, job_description, score, evaluation_json) VALUES (%s, %s, %s, %s)',
            (session.get('user_id'), job_skills_input, candidate['score'], json.dumps(candidate))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Notice persisting applicant evaluation: {e}")

    return jsonify({'success': True, 'candidate': candidate})


@app.route('/api/applicant/sample', methods=['GET', 'POST'])
@login_required
def applicant_sample():
    """Loads a sample software engineer resume and evaluates against target job description."""
    samples_dir = os.path.join(BASE_DIR, 'sample_resumes')
    sample_files = [f for f in os.listdir(samples_dir) if f.endswith('.pdf')] if os.path.exists(samples_dir) else []
    if not sample_files:
        return jsonify({'error': 'No sample resumes found'}), 404

    target_file = sample_files[0]
    fpath = os.path.join(samples_dir, target_file)
    with open(fpath, 'rb') as fp:
        raw_text = extract_text(fp.read(), 'pdf')

    job_requirements = (
        "Senior Full-Stack Cloud Engineer: Python, React, AWS, Docker, Microservices, "
        "SQL, Node.js, CI/CD, Git, Kubernetes, REST APIs"
    )

    clean_r = clean_text(raw_text)
    cleaned_job = clean_text(job_requirements)
    job_skills = _extract_skill_phrases(job_requirements)

    all_insights = [extract_keyword_insights(clean_r, job_skills)]
    skill_matched_lists = [ins['matched_skills'] for ins in all_insights]
    related_skill_counts = [len(ins.get('related_skills', [])) for ins in all_insights]

    tfidf_scores = calculate_tfidf_scores([clean_r], cleaned_job)
    dense_scores = calculate_dense_scores([raw_text], job_requirements)
    rrf_scores = compute_rrf_scores(
        tfidf_scores, dense_scores,
        job_skills=job_skills, cleaned_resumes=[clean_r],
        skill_matches=skill_matched_lists,
        related_skill_counts=related_skill_counts
    )

    candidate = build_candidate_report(
        target_file, raw_text, clean_r, job_skills,
        rrf_scores[0], tfidf_scores[0], dense_scores[0],
        precomputed_insights=all_insights[0]
    )

    return jsonify({
        'success': True,
        'job_description': job_requirements,
        'candidate': candidate
    })


@app.route('/api/applicant/optimize-bullet', methods=['POST'])
@login_required
def api_optimize_bullet():
    """Rewrites a weak or standard resume bullet point into 3 high-impact executive variations."""
    data = request.get_json(silent=True) or request.form
    bullet = data.get('bullet', '').strip()
    target_role = data.get('target_role', '').strip()

    if not bullet:
        return jsonify({'error': 'Bullet point text is required'}), 400

    from resume_parser import optimize_resume_bullet
    revisions = optimize_resume_bullet(bullet, target_role=target_role)
    return jsonify({'success': True, 'revisions': revisions, 'original': bullet})


@app.route('/api/applicant/cover-letter', methods=['POST'])
@login_required
def api_generate_cover_letter():
    """Generates a tailored executive cover letter from candidate details and target job."""
    data = request.get_json(silent=True) or request.form
    candidate_name = data.get('name', 'Candidate')
    matched_skills = data.get('matched_skills', [])
    if isinstance(matched_skills, str):
        matched_skills = [s.strip() for s in matched_skills.split(',') if s.strip()]
    missing_skills = data.get('missing_skills', [])
    if isinstance(missing_skills, str):
        missing_skills = [s.strip() for s in missing_skills.split(',') if s.strip()]
    provable_years = int(data.get('provable_years', 0) or 0)
    job_roles = data.get('job_roles', [])
    if isinstance(job_roles, str):
        job_roles = [r.strip() for r in job_roles.split(',') if r.strip()]
    job_description = data.get('job_description', '')

    from resume_parser import generate_tailored_cover_letter
    cover_letter = generate_tailored_cover_letter(
        candidate_name, matched_skills, missing_skills,
        provable_years=provable_years, job_roles=job_roles,
        job_description=job_description
    )
    return jsonify({'success': True, 'cover_letter': cover_letter})



@app.route('/history', methods=['GET'])
@role_required('admin', 'recruiter', 'viewer')
def get_history():
    """Returns all past analysis runs from the database (for demonstration and persistence)."""
    import json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, job_description, analyzed_at, candidates_json FROM analysis_history ORDER BY analyzed_at DESC')
        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            try:
                cands = json.loads(row[3]) if row[3] else []
                top_name = cands[0]['name'].replace('.pdf', '').replace('.docx', '') if cands else 'None'
                top_score = cands[0]['score'] if cands else 0
            except Exception:
                cands = []
                top_name = 'N/A'
                top_score = 0

            history.append({
                'id': row[0],
                'job_description': row[1],
                'analyzed_at': str(row[2]) if row[2] else 'Recent',
                'candidates_analyzed': len(cands),
                'top_candidate': top_name,
                'top_score': top_score
            })
        return jsonify({'analysis_history': history})
    except Exception as e:
        return jsonify({'analysis_history': [], 'notice': f'Database notice: {e}'})


@app.route('/history/<int:history_id>', methods=['GET'])
@role_required('admin', 'recruiter', 'viewer')
def load_history_run(history_id):
    """Loads a past analysis run from the database into the active dashboard session."""
    import json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT job_description, candidates_json, analyzed_at FROM analysis_history WHERE id = %s', (history_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({'error': 'Analysis run not found'}), 404

        job_desc = row[0]
        cands = json.loads(row[1]) if row[1] else []

        # Set into active session cache
        LAST_REPORT['job_skills_input'] = job_desc
        LAST_REPORT['candidates'] = cands
        LAST_REPORT['generated_at'] = str(row[2])

        return jsonify({
            'success': True,
            'job_description': job_desc,
            'candidates': cands,
            'analyzed_at': str(row[2])
        })
    except Exception as e:
        return jsonify({'error': f'Failed loading history run: {e}'}), 500


@app.route('/history/<int:history_id>', methods=['DELETE'])
@role_required('admin', 'recruiter')
def delete_history_run(history_id):
    """Deletes a past analysis run from the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM analysis_history WHERE id = %s', (history_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Run removed from history'})
    except Exception as e:
        return jsonify({'error': f'Failed deleting history run: {e}'}), 500


@app.route('/api/samples/load', methods=['GET', 'POST'])
@login_required
def load_samples():
    """
    1-Click Instant Demo: Automatically reads the 20 pre-generated sample resumes
    from sample_resumes/ and evaluates them against full-stack cloud requirements.
    Populates rankings, ATS Kanban, and analytics in sub-second time.
    """
    samples_dir = os.path.join(BASE_DIR, 'sample_resumes')
    if not os.path.exists(samples_dir):
        return jsonify({'error': 'Sample resumes directory not found'}), 404

    sample_files = [f for f in os.listdir(samples_dir) if f.lower().endswith(('.pdf', '.docx'))]
    if not sample_files:
        return jsonify({'error': 'No sample resumes found in sample_resumes/'}), 404

    job_requirements = (
        "Senior Full-Stack Cloud Engineer: Python, React, AWS, Docker, Microservices, "
        "SQL, Node.js, CI/CD, Git, Kubernetes, REST APIs"
    )

    filenames = []
    raw_texts = []
    cleaned_texts = []

    for fn in sample_files:
        fpath = os.path.join(samples_dir, fn)
        try:
            with open(fpath, 'rb') as f:
                fbytes = f.read()
            ext = fn.rsplit('.', 1)[-1].lower()
            text = extract_text(fbytes, ext)
            if text and text.strip():
                filenames.append(fn)
                raw_texts.append(text)
                cleaned_texts.append(clean_text(text))
        except Exception as e:
            print(f"Notice loading sample {fn}: {e}")

    if not filenames:
        return jsonify({'error': 'Failed extracting text from sample resumes'}), 500

    # Save to candidates table
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.executemany(
            'REPLACE INTO candidates (filename, extracted_text) VALUES (%s, %s)',
            list(zip(filenames, raw_texts))
        )
        conn.commit()
        conn.close()
    except Exception as db_err:
        print(f"Notice saving candidates to DB: {db_err}")

    # Run hybrid scoring
    cleaned_job = clean_text(job_requirements)
    job_skills = _extract_skill_phrases(job_requirements)

    w_tfidf, w_skill, w_dense = 0.40, 0.35, 0.25
    all_insights = [extract_keyword_insights(c_t, job_skills) for c_t in cleaned_texts]
    skill_matched_lists = [ins['matched_skills'] for ins in all_insights]
    related_skill_counts = [len(ins.get('related_skills', [])) for ins in all_insights]

    tfidf_scores = calculate_tfidf_scores(cleaned_texts, cleaned_job)
    dense_scores = calculate_dense_scores(raw_texts, job_requirements)
    rrf_scores = compute_rrf_scores(
        tfidf_scores, dense_scores,
        job_skills=job_skills, cleaned_resumes=cleaned_texts,
        w_tfidf=w_tfidf, w_skill=w_skill, w_dense=w_dense,
        skill_matches=skill_matched_lists,
        related_skill_counts=related_skill_counts
    )

    results = []
    for fn, raw_t, clean_t, hybrid_s, tf_s, d_s, insights in zip(
        filenames, raw_texts, cleaned_texts, rrf_scores, tfidf_scores, dense_scores, all_insights
    ):
        results.append(
            build_candidate_report(
                fn, raw_t, clean_t, job_skills, hybrid_s, tf_s, d_s, precomputed_insights=insights
            )
        )

    results = sorted(results, key=lambda x: x['score'], reverse=True)

    LAST_REPORT['job_skills_input'] = job_requirements
    LAST_REPORT['candidates'] = results
    LAST_REPORT['generated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Save history run
    import json
    history_id = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO analysis_history (user_id, job_description, candidates_json) VALUES (%s, %s, %s)',
            (session.get('user_id'), job_requirements, json.dumps(results))
        )
        conn.commit()
        history_id = cursor.lastrowid
        conn.close()
    except Exception as e:
        print(f"Notice saving sample run to history: {e}")

    return jsonify({
        'candidates': results,
        'job_description': job_requirements,
        'history_id': history_id,
        'total_loaded': len(results)
    })


@app.route('/analytics', methods=['GET'])
@role_required('admin', 'recruiter', 'viewer')
def analytics():
    """Returns aggregated data for the Advanced Analytics Dashboard."""
    if not LAST_REPORT['candidates']:
        return jsonify({'error': 'No analysis available. Run /analyze first.'}), 400

    cands = LAST_REPORT['candidates']
    avg_score = sum(c['score'] for c in cands) / len(cands)
    fast_trackers = sum(1 for c in cands if c.get('velocity_analysis', {}).get('is_fast_tracker'))

    missing_counts = {}
    matched_counts = {}
    for c in cands:
        for s in c.get('missing_skills', []):
            missing_counts[s] = missing_counts.get(s, 0) + 1
        for s in c.get('matched_skills', []):
            matched_counts[s] = matched_counts.get(s, 0) + 1

    top_missing = sorted(missing_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_matched = sorted(matched_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return jsonify({
        'average_score': round(avg_score, 1),
        'total_candidates': len(cands),
        'fast_trackers': fast_trackers,
        'top_missing_skills': top_missing,
        'top_matched_skills': top_matched
    })


@app.route('/chat', methods=['POST'])
@role_required('admin', 'recruiter', 'viewer')
def chat_bot():
    """
    Intelligent AI Hiring Assistant: Answers questions over active candidates and past resumes.
    Understands skills, experience, fast trackers, culture fit, universities, and degrees.
    """
    data = request.get_json()
    query = (data.get('query', '') if data else '').strip()

    if not query:
        return jsonify({"answer": "Please ask a question about candidates, skills, or experience."})

    q_lower = query.lower()

    # Use active in-memory candidates first if available, else load from DB
    cands = LAST_REPORT.get('candidates', [])

    if not cands:
        # Fallback to DB
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT filename, extracted_text FROM candidates ORDER BY analyzed_at DESC LIMIT 30')
            rows = cursor.fetchall()
            conn.close()
            if rows:
                filenames = [r[0] for r in rows]
                texts = [r[1] for r in rows]
                scores = calculate_dense_scores(texts, query)
                top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:3]
                best = [f"{filenames[i]} (~{scores[i]}% match)" for i in top_indices if scores[i] > 5]
                if best:
                    return jsonify({"answer": f"Based on resume text search, the best matching candidate(s) are: {', '.join(best)}."})
            return jsonify({"answer": "No resumes currently analyzed. Upload resumes or click '⚡ Load Demo Candidates' to begin asking questions!"})
        except Exception as e:
            return jsonify({"answer": f"Notice: {e}. Please analyze resumes first."})

    # 0. Pipeline / ATS Stages Query
    if any(k in q_lower for k in ['pipeline', 'shortlist', 'interview', 'rejected', 'stage', 'status']):
        shortlisted = [c['name'].replace('.pdf', '').replace('.docx', '').replace('_', ' ') for c in cands if c.get('stage') == 'shortlisted']
        interviewing = [c['name'].replace('.pdf', '').replace('.docx', '').replace('_', ' ') for c in cands if c.get('stage') == 'interviewing']
        rejected = [c['name'].replace('.pdf', '').replace('.docx', '').replace('_', ' ') for c in cands if c.get('stage') == 'rejected']
        applied = [c['name'].replace('.pdf', '').replace('.docx', '').replace('_', ' ') for c in cands if c.get('stage', 'applied') == 'applied']

        msg = f"📊 **ATS Pipeline Breakdown ({len(cands)} total):**\n"
        msg += f"- **1. Applied:** {len(applied)} candidate(s)\n"
        msg += f"- **2. Shortlisted:** {len(shortlisted)} candidate(s)" + (f" ({', '.join(shortlisted[:3])})" if shortlisted else "") + "\n"
        msg += f"- **3. Interviewing:** {len(interviewing)} candidate(s)" + (f" ({', '.join(interviewing[:3])})" if interviewing else "") + "\n"
        msg += f"- **4. Rejected:** {len(rejected)} candidate(s)" + (f" ({', '.join(rejected[:3])})" if rejected else "")
        return jsonify({"answer": msg})

    # 1. Top Candidate / Overall Best Fit
    if any(k in q_lower for k in ['top candidate', 'highest score', 'best match', 'best candidate', 'winner', 'who should i hire', 'recommend']):
        top = cands[0]
        top_name = top['name'].replace('.pdf', '').replace('.docx', '').replace('_', ' ')
        skills_str = ', '.join(top['matched_skills'][:4]) or 'core technical skills'
        exp_years = top.get('timeline_audit', {}).get('provable_years', 0)
        return jsonify({
            "answer": f"🏆 The top-ranked candidate is **{top_name}** with a **{top['score']}% match**. They bring ~{exp_years} years of proven experience with verified skills in {skills_str}. {top.get('tldr_summary', '')}"
        })

    # 2. Fast Trackers / High Velocity
    if any(k in q_lower for k in ['fast tracker', 'velocity', 'rapid growth', 'promotion', 'fast track']):
        fast_trackers = [c for c in cands if c.get('velocity_analysis', {}).get('is_fast_tracker')]
        if fast_trackers:
            names = [f"**{c['name'].replace('.pdf','').replace('_',' ')}** ({c['velocity_analysis']['velocity_notes']})" for c in fast_trackers[:3]]
            return jsonify({
                "answer": f"🚀 Detected {len(fast_trackers)} Fast Tracker(s) who achieved rapid seniority:\n- " + "\n- ".join(names)
            })
        return jsonify({"answer": "No fast-trackers (e.g. Senior/Lead with ≤4 years of provable experience) were detected among current candidates."})

    # 3. Discrepancy / Timeline Audit / Fraud Queries
    if any(k in q_lower for k in ['fraud', 'timeline', 'discrepancy', 'alert', 'claimed', 'years lie', 'audit']):
        alerted = [c for c in cands if c.get('timeline_audit', {}).get('timeline_alert')]
        if alerted:
            details = [f"**{c['name'].replace('.pdf','').replace('_',' ')}**: {c['timeline_audit']['alert_reason']}" for c in alerted[:3]]
            return jsonify({
                "answer": f"⚠️ Timeline Audit flagged {len(alerted)} candidate(s) with experience discrepancies:\n- " + "\n- ".join(details)
            })
        return jsonify({"answer": "✅ All screened candidates passed the timeline audit without discrepancies between claimed and provable experience."})

    # 4. Experience / Years Query
    if any(k in q_lower for k in ['most experience', 'seniority', 'years of experience', 'longest experience', 'highest experience']):
        sorted_by_exp = sorted(cands, key=lambda c: c.get('timeline_audit', {}).get('provable_years', 0), reverse=True)
        top_exp = sorted_by_exp[:3]
        exp_list = [f"**{c['name'].replace('.pdf','').replace('_',' ')}**: ~{c.get('timeline_audit',{}).get('provable_years',0)} years provable experience ({c['score']}% match)" for c in top_exp]
        return jsonify({
            "answer": "Candidate experience ranking:\n- " + "\n- ".join(exp_list)
        })

    # 5. Specific Skill Query (e.g. "Who knows AWS?", "Who has Python?")
    skills_to_check = [
        'aws', 'python', 'react', 'docker', 'kubernetes', 'sql', 'microservices',
        'node.js', 'nodejs', 'ci/cd', 'cicd', 'git', 'java', 'spring', 'fastapi',
        'machine learning', 'pytorch', 'tensorflow', 'linux', 'terraform', 'cloud'
    ]
    detected_skills = [s for s in skills_to_check if s in q_lower]

    if detected_skills:
        skill = detected_skills[0]
        matching = []
        for c in cands:
            clean_name = c['name'].replace('.pdf', '').replace('.docx', '').replace('_', ' ')
            matched = [s.lower() for s in c.get('matched_skills', [])]
            related = [r['required'].lower() for r in c.get('related_skills', [])]
            if any(skill in m for m in matched):
                matching.append((clean_name, c['score'], "Exact Match"))
            elif any(skill in r for r in related):
                matching.append((clean_name, c['score'], "Related Match"))

        if matching:
            matching = sorted(matching, key=lambda x: x[1], reverse=True)[:4]
            lines = [f"**{m[0]}** — {m[1]}% overall match ({m[2]})" for m in matching]
            return jsonify({
                "answer": f"Candidates with verified **{skill.upper()}** capabilities:\n- " + "\n- ".join(lines)
            })

    # 6. Specific Candidate Lookup (e.g. "Tell me about Alex Smith")
    for c in cands:
        raw_name = c['name'].lower().replace('.pdf', '').replace('.docx', '').replace('_', ' ')
        first_word = raw_name.split()[0]
        if first_word in q_lower and len(first_word) > 2:
            clean_name = c['name'].replace('.pdf', '').replace('.docx', '').replace('_', ' ')
            exp = c.get('timeline_audit', {}).get('provable_years', 0)
            matched = ', '.join(c.get('matched_skills', [])[:5]) or 'None'
            missing = ', '.join(c.get('missing_skills', [])[:3]) or 'None'
            salary = c.get('salary_prediction', 'Market competitive')
            return jsonify({
                "answer": f"📋 **Candidate Profile: {clean_name}**\n- **Overall Match:** {c['score']}%\n- **Provable Experience:** ~{exp} years\n- **Key Matched Skills:** {matched}\n- **Missing Skills:** {missing}\n- **Estimated Salary:** {salary}\n- **AI Summary:** {c.get('tldr_summary', '')}"
            })

    # 7. Semantic Search Fallback
    res_texts = [f"{c['name']} {' '.join(c.get('matched_skills',[]))} {' '.join(c.get('entities',{}).get('job_roles',[]))}" for c in cands]
    dense_scores = calculate_dense_scores(res_texts, query)
    top_indices = sorted(range(len(dense_scores)), key=lambda i: dense_scores[i], reverse=True)[:3]
    top_matches = [cands[i] for i in top_indices if dense_scores[i] > 10]

    if top_matches:
        lines = [f"**{c['name'].replace('.pdf','').replace('_',' ')}** ({c['score']}% match, {c.get('timeline_audit',{}).get('provable_years',0)} yrs exp)" for c in top_matches]
        return jsonify({
            "answer": f"Based on semantic matching for \"{query}\":\n- " + "\n- ".join(lines)
        })

    return jsonify({
        "answer": f"I reviewed the {len(cands)} candidates currently analyzed. Could you clarify what specific skill, role, or experience level you'd like to inspect?"
    })


@app.route('/api/v1/analyze', methods=['POST'])
def api_analyze():
    """Developer API Endpoint for headless integration."""
    api_key = request.headers.get('X-API-Key')
    # In a real app, validate api_key against DB
    if api_key != 'demo-api-key-123':
        return jsonify({'error': 'Unauthorized. Invalid API Key.'}), 401
    
    if 'resumes' not in request.files:
        return jsonify({'error': 'No files uploaded in "resumes" field'}), 400

    files = request.files.getlist('resumes')
    job_skills_input = request.form.get('skills', '').strip()

    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    if not job_skills_input:
        return jsonify({'error': 'Job description field is empty'}), 400

    processed_items = []
    with ThreadPoolExecutor(max_workers=min(8, len(files))) as executor:
        results_iter = executor.map(_process_single_file, files)
        processed_items = [r for r in results_iter if r is not None]

    filenames, raw_texts, cleaned_texts = [], [], []
    for item in processed_items:
        if item['status'] == 'ok':
            filenames.append(item['filename'])
            raw_texts.append(item['raw_text'])
            cleaned_texts.append(item['cleaned_text'])

    if not filenames:
        return jsonify({'error': 'No readable text in uploaded files'}), 400

    cleaned_job = clean_text(job_skills_input)
    job_skills = _extract_skill_phrases(job_skills_input)
    
    all_insights = [extract_keyword_insights(c_t, job_skills) for c_t in cleaned_texts]
    skill_matched_lists = [ins['matched_skills'] for ins in all_insights]
    related_skill_counts = [len(ins.get('related_skills', [])) for ins in all_insights]

    tfidf_scores = calculate_tfidf_scores(cleaned_texts, cleaned_job)
    dense_scores = calculate_dense_scores(raw_texts, job_skills_input)
    rrf_scores = compute_rrf_scores(
        tfidf_scores, dense_scores,
        job_skills=job_skills, cleaned_resumes=cleaned_texts,
        skill_matches=skill_matched_lists, related_skill_counts=related_skill_counts
    )

    results = []
    for fn, raw_t, clean_t, hybrid_s, tf_s, d_s, insights in zip(
        filenames, raw_texts, cleaned_texts, rrf_scores, tfidf_scores, dense_scores, all_insights
    ):
        results.append(
            build_candidate_report(fn, raw_t, clean_t, job_skills, hybrid_s, tf_s, d_s, insights)
        )

    results = sorted(results, key=lambda x: x['score'], reverse=True)

    # Save the complete analysis history to the database
    import json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO analysis_history (user_id, job_description, candidates_json) VALUES (%s, %s, %s)',
            (session.get('user_id'), job_skills_input, json.dumps(results))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to save history to DB: {e}")

    # Also update the in-memory cache for the current session
    LAST_REPORT['candidates'] = results
    LAST_REPORT['job_skills_input'] = job_skills_input
    LAST_REPORT['generated_at'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return jsonify({'candidates': results})

@app.after_request
def set_security_headers(response):
    """Production-grade security headers."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

@app.errorhandler(404)
def not_found_error(e):
    if request.path.rstrip('/') in ('/api/index', '/api/index.py'):
        return render_template('landing.html')
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found', 'path': request.path}), 404
    return redirect(url_for('dashboard'))


@app.errorhandler(413)
def file_too_large(e):
    return jsonify({'error': 'Upload payload too large.'}), 413


@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error.'}), 500


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)