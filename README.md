# ResuMetrics 🚀
### AI-Powered Hybrid Resume Screening, Candidate Matching & Applicant Tracking System (ATS)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask 3.0](https://img.shields.io/badge/flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![Tests Passing](https://img.shields.io/badge/tests-37%2F37%20passing-brightgreen.svg)](test_app.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**ResuMetrics** is a production-grade, enterprise talent acquisition platform and AI resume screening engine. It evaluates candidate resumes (PDF or DOCX) against job requirements with sub-second latency, providing hybrid AI scoring (TF-IDF + Dense Vector Embeddings + Exact Skill Overlap), timeline fraud auditing, ATS Kanban pipeline tracking, AI take-home assessment generation, and dual-database persistence.

---

## 📑 Table of Contents

- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Technologies Used](#-technologies-used)
- [Project Folder Structure](#-project-folder-structure)
- [Installation & Setup](#-installation--setup)
- [Database Configuration](#-database-configuration)
- [Environment Variables](#-environment-variables)
- [Running the Application](#-running-the-application)
- [Running the Automated Test Suite](#-running-the-automated-test-suite)
- [Important API Endpoints](#-important-api-endpoints)
- [Deployment Guidelines](#-deployment-guidelines)
- [License](#-license)

---

## 🌟 Key Features

### 1. Dual-Role Experience & Dashboards
- **Recruiter Dashboard (`/dashboard`):**
  - Batch resume upload (PDF/DOCX) with multithreaded in-memory text streaming.
  - Interactive weights customization (TF-IDF, Skill Overlap, Dense Vectors).
  - 5-axis Candidate Radar Charts (Tech Match, Semantic, Culture, Velocity, Soft Skills).
  - AI Take-Home Technical Assessment Generator tailored to verified candidate skills.
  - Side-by-Side Candidate Comparison Grid with dynamic candidate counter.
  - Automated Outreach Draft generator with one-click clipboard copying.
  - SMTP Interview Invitation sender with safe simulation mode.
  - Real-time interactive drag-and-drop Kanban ATS Pipeline (`Applied` → `Shortlisted` → `Interviewing` → `Rejected`) with full database persistence.
- **Applicant Self-Evaluation Portal (`/dashboard?role=applicant`):**
  - **8 Industry Role Presets:** 1-click calibration for Full-Stack, Backend Architect, DevOps/SRE, ML/AI, Data Science, Frontend Architect, Cybersecurity, and Mobile.
  - **Interactive "What-If" ATS Score Simulator:** Real-time projected score calculation and progress bar as candidates check off missing skills.
  - **🛡️ ATS Pre-Flight Formatting & Health Audit:** Word count density analysis against optimal 450–900 word thresholds, 4-point contact verification (Email, Phone, LinkedIn, GitHub), and passive buzzword/cliché detection.
  - **⚡ AI Resume Bullet Rewriter:** Transforms weak descriptions into 3 high-impact variations following Google's *XYZ Formula* (*Accomplished [X] measured by [Y] by doing [Z]*), Senior Leadership, and Systems Design.
  - **✉️ AI Tailored Executive Cover Letter:** Auto-synthesizes candidate skills, tenure, and target job description into an editable 3-paragraph executive cover letter with 1-click clipboard copy and `.txt` export.
  - **Interactive 5-Axis Radar Chart:** Multi-dimensional assessment across Technical Match, Semantic AI, Culture Fit, Velocity, and Soft Skills.
  - **AI Predicted Recruiter Interview Questions:** Customized interview preparation based on identified skill gaps, with strategic STAR answering guidelines.
  - **1-Click Sample Profile Benchmark (`/api/applicant/sample`):** Instantly loads and evaluates a sample software engineer profile without mutating active recruiter screening sessions.
  - **Multi-Format Exporting:** High-fidelity print-styled PDF (`window.print()`) and structured Markdown audit report (`ResuMetrics_Audit_<Candidate>.md`).
- **1-Click Instant Demo Login (`/demo-login`, `/applicant-demo-login`):**
  - Frictionless instant access to live features without mandatory credential creation.

### 2. Multi-Dimensional Hybrid AI Scoring Pipeline
- **Sparse TF-IDF N-Gram Vectorizer (40% default):** Sublinear unigram and bigram TF-IDF matching.
- **Exact & Adjacent Skill Overlap (35% default):** Standardizes technical aliases (`CI/CD` → `cicd`, `UI/UX` → `uiux`, `REST APIs` → `restapi`) and awards partial credit for transferable background (e.g. PyTorch for TensorFlow).
- **Dense Neural Semantic Embeddings (25% default):** Uses `SentenceTransformer('all-MiniLM-L6-v2')` with SHA-256 caching and an ultra-fast character-ngram projection fallback when PyTorch is absent.
- **Reciprocal Rank Fusion (RRF):** Dynamically harmonizes all three score dimensions into a single balanced compatibility rating (0–100%).

### 3. Timeline Fraud & Discrepancy Auditing
- Extracts employment date ranges (textual months, numeric `MM/YYYY`, parenthesized dates, and `Present`).
- Chronologically merges overlapping positions to eliminate false-positive warnings for concurrent roles.
- Flags discrepancy alerts if self-reported total years exceed verified employment tenure by > 1.5 years.

### 4. Zero-Dependency DOCX & PDF Parsing
- Extracts raw text in-memory from PDF files using `pypdf` and `pdfplumber`.
- Extracts raw text from DOCX files using `python-docx` with an automatic, zero-dependency XML zipfile fallback (`zipfile` + `xml.etree.ElementTree`).

### 5. Conversational AI Hiring Assistant (`/chat`)
- Natural-language queries over active and archived resumes:
  - *"What is the current hiring pipeline breakdown?"*
  - *"Who has the most experience with AWS?"*
  - *"Tell me about the top candidate"*
  - *"Which candidates are fast trackers?"*

---

## 🏛 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│             WEB CLIENT (Desktop / Tablet / Mobile)          │
│   Landing Page | Recruiter Dashboard | Applicant Portal     │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / JSON / Multipart
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 FLASK 3.0 APPLICATION (app.py)              │
│  • RBAC & Session Management (Admin / Recruiter / Applicant)│
│  • In-Memory Parallel Upload Ingestion (ThreadPoolExecutor) │
│  • Headless Developer API (/api/v1/analyze)                 │
│  • PDF / CSV Report Exporters (ReportLab)                   │
└──────────────────────────────┬──────────────────────────────┘
                               │
        ┌──────────────────────┴──────────────────────┐
        ▼                                             ▼
┌───────────────────────────────┐     ┌───────────────────────────────┐
│     AI PARSER & NLP ENGINE    │     │       HYBRID DATA LAYER       │
│      (resume_parser.py)       │     │ • MySQL / TiDB (Primary)      │
│ • Technical Alias Normalizer  │     │ • SQLiteProxy (Auto-Fallback) │
│ • Entity & Credential (NER)   │     │ • candidates                  │
│ • Date Interval Timeline Merge│     │ • users (bcrypt passwords)    │
│ • TF-IDF + Dense Transformers │     │ • analysis_history            │
│ • Reciprocal Rank Fusion (RRF)│     │ • applicant_evaluations       │
└───────────────────────────────┘     └───────────────────────────────┘
```

---

## 🛠 Technologies Used

- **Backend:** Python 3.10+, Flask 3.0, Werkzeug
- **NLP & Machine Learning:** scikit-learn, sentence-transformers, PyTorch, NumPy
- **Document Processing:** PyPDF, pdfplumber, python-docx, built-in XML zipfile engine
- **Database:** PyMySQL (MySQL / TiDB), SQLite3 (with transparent `SQLiteConnectionProxy`)
- **PDF Generation:** ReportLab 4.x
- **Frontend:** Vanilla ES6+ JavaScript, CSS3 Design Tokens, Chart.js (Radar Charts), HTML5

---

## 📁 Project Folder Structure

```
Resumetrics/
├── app.py                      # Core Flask web server, auth decorators, and API routes
├── resume_parser.py            # NLP engine, tokenization, NER, timeline auditing & scoring
├── generate_samples.py         # Generates 20 diverse realistic sample resumes (PDF)
├── generate_summary.py         # ReportLab PDF executive documentation generator
├── generate_workflow.py        # ReportLab PDF system workflow diagram generator
├── test_app.py                 # Comprehensive unit & integration test suite (37 tests)
├── requirements.txt            # Production dependencies
├── resumetrics.db              # High-speed SQLite fallback database
├── sample_resumes/             # 20 diverse, realistic candidate PDF resumes
├── static/
│   ├── css/style.css           # Modern dark-theme responsive stylesheets
│   └── js/main.js              # Recruiter dashboard, drag-drop, Kanban, charts, AI chat
├── templates/
│   ├── landing.html            # Public marketing landing page & feature showcase
│   ├── login.html              # Secure user authentication interface
│   ├── register.html           # User account registration with role assignment
│   ├── dashboard.html          # Recruiter talent analytics & ATS screening dashboard
│   ├── applicant_dashboard.html# Applicant self-evaluation and optimization portal
│   ├── privacy.html            # Privacy policy document
│   └── terms.html              # Terms of service document
├── public/                     # Static distribution bundle for Vercel CDN
│   └── static/
└── vercel.json                 # Serverless deployment configuration
```

---

## 💻 Installation & Setup

### 1. Prerequisites
- Python 3.10, 3.11, 3.12, 3.13, or 3.14
- Git

### 2. Clone Repository & Create Virtual Environment
```bash
git clone https://github.com/your-username/Resumetrics.git
cd Resumetrics

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Generate Sample Resumes (Optional)
```bash
python generate_samples.py
```
This populates `sample_resumes/` with 20 realistic candidate profiles spanning Full-Stack, Backend, DevOps, ML Engineering, Data Science, and Security.

---

## 🗄 Database Configuration

ResuMetrics features **Zero-Configuration Dual Database Architecture**:
1. **Local MySQL / TiDB Cloud (Default):**
   - ResuMetrics will attempt to connect to MySQL on `localhost:3306` with database `resumetrics`.
2. **Seamless SQLite Fallback:**
   - If MySQL is not running or unreachable, `SQLiteConnectionProxy` transparently handles queries and saves state to `resumetrics.db` without crashing or throwing unhandled errors.

To connect your custom MySQL instance, provide environment variables:
```bash
export MYSQL_HOST="localhost"
export MYSQL_PORT="3306"
export MYSQL_USER="root"
export MYSQL_PASSWORD="your_password"
export MYSQL_DB="resumetrics"
```

---

## ⚙️ Environment Variables

| Variable | Default Value | Description |
|---|---|---|
| `SECRET_KEY` | `resumetrics-secret-key-change-in-prod` | Flask session encryption key |
| `MYSQL_HOST` | `localhost` | MySQL hostname or TiDB cloud endpoint |
| `MYSQL_PORT` | `3306` | MySQL port |
| `MYSQL_USER` | `root` | Database user |
| `MYSQL_PASSWORD` | `nitesh123` | Database password |
| `MYSQL_DB` | `resumetrics` | Database schema name |
| `MYSQL_SSL` | `None` | Set to `1` for TiDB / Aiven SSL connections |

---

## 🚀 Running the Application

Start the Flask development server:
```bash
python app.py
```

Open your browser at:
`http://127.0.0.1:5000`

### Default Demo Access:
- **Recruiter Demo:** Click **"Recruiter Demo"** or visit `http://127.0.0.1:5000/demo-login`
- **Applicant Demo:** Click **"Applicant Demo"** or visit `http://127.0.0.1:5000/applicant-demo-login`

---

## 🧪 Running the Automated Test Suite

Execute the comprehensive 31-test suite covering parser algorithms, scoring pipelines, security boundaries, and API routes:

```bash
python -m unittest test_app.py
```

Verbose mode:
```bash
python -m unittest test_app.py -v
```

All 37 tests pass with zero regressions:
```
Ran 37 tests in 0.510s
OK
```

---

## 🔌 Important API Endpoints

### 1. Recruiter & ATS Endpoints
- `POST /analyze`: Ingests multipart files (`resumes`) and job description (`skills`). Returns ranked candidates with TF-IDF, dense, and skill scores.
- `POST /generate-assignment`: Generates custom AI take-home coding assessments tailored to candidate skills and target role.
- `POST /api/candidate/stage`: Persists ATS Kanban stage transitions (`applied`, `shortlisted`, `interviewing`, `rejected`).
- `GET /analytics`: Aggregates cohort metrics, average match index, fast tracker count, and top skill gaps.
- `POST /chat`: Conversational AI query endpoint for resume evaluation.
- `GET /export-csv`: Streams a formatted spreadsheet of ranked candidates with ATS stages.
- `GET /export-report`: Streams an executive ReportLab PDF evaluation report.
- `GET /history`: Lists past candidate screening sessions.
- `GET /history/<id>`: Reloads a historical screening session.

### 2. Applicant Endpoints
- `POST /api/applicant/evaluate`: Isolated single-resume evaluation endpoint for applicants.
- `POST /api/applicant/sample`: 1-Click sample resume evaluation.
- `POST /api/applicant/optimize-bullet`: Rewrites weak resume bullet points into 3 high-impact variations using Google XYZ, Leadership, and Systems Design formulas.
- `POST /api/applicant/cover-letter`: Auto-generates a tailored 3-paragraph executive cover letter based on parsed resume intelligence.

### 3. Developer & Integration API
- `POST /api/v1/analyze`: Headless JSON API endpoint for external ATS integrations. Authenticated via `X-API-Key: demo-api-key-123`.

---

## 🚢 Deployment Guidelines

### 1. Vercel Serverless
ResuMetrics includes built-in `vercel.json` and `VercelRoutingMiddleware`.
Deploy with the Vercel CLI:
```bash
vercel --prod
```

### 2. Production WSGI Server (Gunicorn)
Run with Gunicorn on Linux / Docker:
```bash
gunicorn --workers 4 --bind 0.0.0.0:8000 app:app
```

---

## 📄 License

This project is licensed under the MIT License — see the LICENSE file for details.

