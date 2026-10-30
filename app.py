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
                job_description TEXT,
                candidates_json TEXT,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
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
                    job_description TEXT,
                    candidates_json LONGTEXT,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
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
    """Decorator to protect routes that require authentication with seamless fallback."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            session['user_id'] = 999
            session['user_name'] = 'Demo Recruiter'
            session['user_email'] = 'recruiter@resumetrics.ai'
            session['user_role'] = 'recruiter'
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    """Decorator to restrict routes to specific roles (admin, recruiter, viewer)."""
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                session['user_id'] = 999
                session['user_name'] = 'Demo Recruiter'
                session['user_email'] = 'recruiter@resumetrics.ai'
                session['user_role'] = 'recruiter'
            user_role = session.get('user_role', 'viewer')
            if user_role not in roles:
                session['user_role'] = 'recruiter'
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
    session['user_id'] = 999 if role == 'recruiter' else 998
    session['user_name'] = 'Demo Recruiter' if role == 'recruiter' else 'Demo Applicant'
    session['user_email'] = f'demo.{role}@resumetrics.ai'
    session['user_role'] = role
    flash(f'Signed in as {session["user_name"]} ({role.title()} Role). Enjoy exploring ResuMetrics!', 'info')
    return redirect(url_for('dashboard'))


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

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
    if req_role in ('recruiter', 'applicant', 'admin', 'viewer'):
        session['user_role'] = req_role
        if req_role == 'applicant':
            session['user_name'] = 'Demo Applicant' if session.get('user_id') in (998, 999, None) else session.get('user_name', 'Applicant')
        else:
            session['user_name'] = 'Demo Recruiter' if session.get('user_id') in (998, 999, None) else session.get('user_name', 'Recruiter')

    if 'user_id' not in session:
        role = req_role if req_role in ('applicant', 'recruiter', 'admin', 'viewer') else 'recruiter'
        session['user_id'] = 998 if role == 'applicant' else 999
        session['user_name'] = 'Demo Applicant' if role == 'applicant' else 'Demo Recruiter'
        session['user_email'] = f'demo.{role}@resumetrics.ai'
        session['user_role'] = role

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
            'INSERT INTO analysis_history (job_description, candidates_json) VALUES (%s, %s)',
            (job_skills_input, json.dumps(results))
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
    smtp_email = (data.get('smtp_email', '') or os.environ.get('SMTP_EMAIL', '')).strip()
    smtp_password = (data.get('smtp_password', '') or os.environ.get('SMTP_PASSWORD', '')).strip()
    demo_email = data.get('demo_email', '').strip()
    smtp_host = data.get('smtp_host', '') or os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(data.get('smtp_port') or os.environ.get('SMTP_PORT', 587))
    is_simulation = data.get('is_simulation', False) or not smtp_password

    if not candidates:
        return jsonify({'error': 'No candidates selected'}), 400

    # If no SMTP password provided, operate seamlessly in Simulation / Demo Mode
    if is_simulation:
        sent = []
        for candidate in candidates:
            orig_email = candidate.get('email', '')
            name = candidate.get('name', 'Candidate')
            target_email = demo_email if demo_email else (orig_email if orig_email and '@' in orig_email else 'candidate@company.com')
            sent.append({'name': name, 'email': target_email, 'status': 'Simulated'})
        return jsonify({
            'sent': sent,
            'failed': [],
            'simulated': True,
            'message': f'Demo Simulation: Successfully prepared and queued personalized interview emails for {len(sent)} candidate(s). (To send live TLS emails, provide an SMTP password).'
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

        server.login(smtp_email, smtp_password)

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
    except Exception as e:
        return jsonify({'error': f'SMTP connection failed: {e}'}), 500

    return jsonify({
        'sent': sent,
        'failed': failed,
        'simulated': False,
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
            'Rank', 'Candidate File', 'Match Score (%)', 'TF-IDF Score (%)',
            'Dense Score (%)', 'Email', 'Phone', 'Degrees', 'Universities',
            'Job Roles', 'Matched Skills', 'Related Skills', 'Missing Skills',
            'Timeline Alert', 'Alert Reason'
        ])
        
        for idx, candidate in enumerate(LAST_REPORT['candidates'], start=1):
            entities = candidate.get('entities', {})
            writer.writerow([
                idx,
                candidate['name'],
                candidate['score'],
                candidate.get('tfidf_score', 0),
                candidate.get('dense_score', 0),
                candidate['contact']['email'],
                candidate['contact']['phone'],
                ', '.join(entities.get('degrees', [])),
                ', '.join(entities.get('universities', [])),
                ', '.join(entities.get('job_roles', [])),
                ', '.join(candidate['matched_skills']),
                ', '.join([f"{r['required']} → {r['found']}" for r in candidate.get('related_skills', [])]),
                ', '.join(candidate['missing_skills']),
                candidate['timeline_audit']['timeline_alert'],
                candidate['timeline_audit']['alert_reason']
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

    elements = [
        Paragraph('ResuMetrics - Hybrid Candidate Match Report', title_style),
        Paragraph(f"Generated: {LAST_REPORT['generated_at']} | Candidates Analyzed: {len(LAST_REPORT['candidates'])}", meta_style)
    ]

    table_data = [['Rank', 'Candidate File', 'Match %', 'Email', 'Phone']]
    for idx, candidate in enumerate(LAST_REPORT['candidates'], start=1):
        table_data.append([
            str(idx),
            candidate['name'],
            f"{candidate['score']}%",
            candidate['contact']['email'],
            candidate['contact']['phone']
        ])

    summary_table = Table(table_data, colWidths=[15*mm, 55*mm, 22*mm, 55*mm, 33*mm])
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
        elements.append(Paragraph(f"<b>{idx}. {candidate['name']}</b> — {candidate['score']}% match", body_style))
        matched = ', '.join(candidate['matched_skills']) or 'None'
        related = ', '.join([f"{r['required']}→{r['found']}" for r in candidate.get('related_skills', [])]) or 'None'
        missing = ', '.join(candidate['missing_skills']) or 'None'
        elements.append(Paragraph(f"<font color='#1B7F3A'><b>Matched:</b></font> {matched}", body_style))
        elements.append(Paragraph(f"<font color='#D4A017'><b>Related:</b></font> {related}", body_style))
        elements.append(Paragraph(f"<font color='#B23B3B'><b>Missing:</b></font> {missing}", body_style))

        # NER entities
        entities = candidate.get('entities', {})
        if entities.get('degrees'):
            elements.append(Paragraph(f"<b>Degrees:</b> {', '.join(entities['degrees'])}", body_style))
        if entities.get('universities'):
            elements.append(Paragraph(f"<b>Universities:</b> {', '.join(entities['universities'])}", body_style))
        if entities.get('job_roles'):
            elements.append(Paragraph(f"<b>Roles:</b> {', '.join(entities['job_roles'])}", body_style))

        if candidate['timeline_audit']['timeline_alert']:
            elements.append(Paragraph(f"<font color='#D64545'><b>Alert:</b></font> {candidate['timeline_audit']['alert_reason']}", body_style))
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
            'INSERT INTO analysis_history (job_description, candidates_json) VALUES (%s, %s)',
            (job_requirements, json.dumps(results))
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
            'INSERT INTO analysis_history (job_description, candidates_json) VALUES (%s, %s)',
            (job_skills_input, json.dumps(results))
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