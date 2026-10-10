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

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'resumetrics-secret-key-change-in-prod')

# ---------------------------------------------------------------------------
# MySQL Database Configuration & Initialization
# ---------------------------------------------------------------------------
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'nitesh123')
MYSQL_DB = os.environ.get('MYSQL_DB', 'resumetrics')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))

def get_db_connection():
    # If running on Vercel (or a cloud DB is used), enable SSL which TiDB/Aiven require
    use_ssl = {'ssl': {'ca': '/etc/ssl/certs/ca-certificates.crt'}} if os.environ.get('VERCEL') else None
    
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        ssl=use_ssl
    )

def init_db():
    try:
        # Create database if it doesn't exist (only locally, not on serverless)
        if not os.environ.get('VERCEL'):
            conn = pymysql.connect(host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD)
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB}")
            conn.commit()
            conn.close()

        # Connect and create tables
        conn = get_db_connection()
        cursor = conn.cursor()
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
        conn.close()
    except Exception as e:
        print(f"Database initialization failed: {e}")

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
            flash('Please sign in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    """Decorator to restrict routes to specific roles (admin, recruiter, viewer)."""
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please sign in to access this page.', 'warning')
                return redirect(url_for('login'))
            user_role = session.get('user_role', 'viewer')
            if user_role not in roles:
                flash('You do not have permission to access this feature.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ---------------------------------------------------------------------------
# Auth Routes
# ---------------------------------------------------------------------------
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please fill in all fields.', 'error')
            return render_template('login.html')

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

    return render_template('login.html')


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
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

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been signed out.', 'info')
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Main Application Routes (Protected)
# ---------------------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
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

    return jsonify({'candidates': results, 'skipped': skipped_files})


# ---------------------------------------------------------------------------
# Auto-Shortlist & Mail
# ---------------------------------------------------------------------------
@app.route('/send-shortlist-email', methods=['POST'])
@role_required('admin', 'recruiter')
def send_shortlist_email():
    """Send shortlist notification emails to selected candidates."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    candidates = data.get('candidates', [])
    subject = data.get('subject', 'Interview Invitation - ResuMetrics')
    body_template = data.get('body', '')
    smtp_email = data.get('smtp_email', '')
    smtp_password = data.get('smtp_password', '')
    demo_email = data.get('demo_email', '').strip()
    smtp_host = data.get('smtp_host', 'smtp.gmail.com')
    smtp_port = int(data.get('smtp_port', 587))

    if not candidates:
        return jsonify({'error': 'No candidates selected'}), 400

    if not smtp_email or not smtp_password:
        return jsonify({'error': 'SMTP credentials are required. Enter your email and app password.'}), 400

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
                
            # If demo mode is active, redirect to the demo email. Otherwise, send to the real candidate.
            email = demo_email if demo_email else original_email

            # Personalize the body (using the original email just in case they want to see it in the template)
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
        'message': f'Successfully sent {len(sent)} email(s). {len(failed)} failed.'
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
    """Returns all past analysis runs from the database (for teacher demonstration)."""
    import json
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, job_description, analyzed_at, candidates_json FROM analysis_history ORDER BY analyzed_at DESC')
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        history.append({
            'id': row[0],
            'job_description': row[1],
            'analyzed_at': row[2],
            'candidates_analyzed': len(json.loads(row[3]))
        })
    return jsonify({'analysis_history': history})


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
    """RAG Chatbot over resumes."""
    data = request.get_json()
    query = data.get('query', '') if data else ''
    
    if not query:
         return jsonify({"answer": "Please ask a question."})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT filename, extracted_text FROM candidates ORDER BY analyzed_at DESC LIMIT 50')
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
         return jsonify({"answer": "No resumes available to search in the database."})
    
    filenames = [r[0] for r in rows]
    texts = [r[1] for r in rows]
    
    scores = calculate_dense_scores(texts, query)
    
    # Get top 3
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:3]
    top_cands = [filenames[i] for i in top_indices if scores[i] > 10]
    
    if top_cands:
         return jsonify({"answer": f"Based on semantic search, the candidates that best match your query are: {', '.join(top_cands)}."})
    return jsonify({"answer": "I couldn't find any candidates matching that specific query."})


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

@app.errorhandler(413)
def file_too_large(e):
    return jsonify({'error': 'Upload payload too large.'}), 413


@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error.'}), 500


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)