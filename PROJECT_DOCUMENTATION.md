# ResuMetrics — Complete Project Documentation

> **AI-Powered Hybrid Resume Screening & Candidate Matching System**

---

## Table of Contents

1. [Project Summary](#1-project-summary)
2. [How It Works — The Big Picture](#2-how-it-works--the-big-picture)
3. [Tech Stack Overview](#3-tech-stack-overview)
4. [Project File Structure](#4-project-file-structure)
5. [Detailed Code Walkthrough](#5-detailed-code-walkthrough)
   - [resume_parser.py — The AI Brain](#51-resume_parserpy--the-ai-brain)
   - [app.py — The Web Server](#52-apppy--the-web-server)
   - [Frontend (HTML, CSS, JS)](#53-frontend-html-css-js)
   - [Supporting Scripts](#54-supporting-scripts)
6. [The Scoring Algorithm Explained](#6-the-scoring-algorithm-explained)
7. [Performance Optimizations](#7-performance-optimizations)
8. [How to Run the Project](#8-how-to-run-the-project)

---

## 1. Project Summary

**ResuMetrics** is a web application that helps recruiters and hiring managers quickly screen and rank job candidates by analyzing their resumes against a job description.

### What does it do?

- You **upload multiple resumes** (PDF or DOCX files) and **paste a job description** or list of required skills.
- The app **reads every resume**, **extracts the text**, and uses **AI-powered algorithms** to calculate how well each candidate matches the job requirements.
- It produces a **ranked leaderboard** of candidates with match scores, matched/missing skills, contact info, and even a **fraud detection alert** if a candidate appears to exaggerate their years of experience.
- You can **export the results** as a **PDF report** or **CSV spreadsheet** (compatible with Excel).

### Who is it for?

- HR teams screening applicants
- Hiring managers comparing candidates
- Recruiters processing large volumes of resumes

---

## 2. How It Works — The Big Picture

Here's the step-by-step flow of what happens when you click **"Analyze Candidates"**:

```
┌─────────────────────────────────────────────────────────────┐
│  USER uploads resumes + types job description in browser    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: FILE INGESTION                                     │
│  • Files are read directly in memory (no disk saving)       │
│  • PDF text extracted using PyPDF library                   │
│  • DOCX text extracted using python-docx library            │
│  • Multiple files processed in parallel (using threads)     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: TEXT CLEANING & NORMALIZATION                       │
│  • Convert everything to lowercase                          │
│  • Replace tech terms like "C++" → "cpp", "Node.js" →      │
│    "nodejs" so they survive punctuation removal              │
│  • Remove all punctuation and special characters            │
│  • Remove common filler words ("the", "a", "is", etc.)     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: AI SCORING (Three Independent Algorithms)          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  TF-IDF      │  │  Dense       │  │  Exact Skill     │  │
│  │  Keyword     │  │  Semantic    │  │  Matching        │  │
│  │  Matching    │  │  AI Vectors  │  │                  │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │            │
│         └────────┬────────┴────────────────────┘            │
│                  ▼                                          │
│       HYBRID WEIGHTED BLEND → Final Score (0-100%)          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: CANDIDATE REPORT BUILDING                          │
│  • Extract email & phone from resume header                 │
│  • Identify matched vs missing skills                       │
│  • Run fraud/timeline audit (compare claimed vs proven      │
│    years of experience)                                     │
│  • Sort candidates by final score (highest first)           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: RESULTS DISPLAYED                                  │
│  • Interactive cards with animated score gauges              │
│  • Matched/missing skill badges                             │
│  • Timeline fraud alerts (if detected)                      │
│  • Export as PDF or CSV                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Tech Stack Overview

### Backend (Server-Side — Python)

| Technology | What It Does | Why We Use It |
|---|---|---|
| **Python 3.14** | The main programming language | Easy to write, huge AI/ML library ecosystem |
| **Flask** | Lightweight web framework | Creates the web server, handles routes (`/`, `/analyze`, `/export`) |
| **SQLite** | Embedded database | Stores extracted resume text for history; no separate DB server needed |
| **PyPDF** | PDF text extraction | Reads text content from uploaded PDF files |
| **python-docx** | DOCX text extraction | Reads text content from uploaded Word documents |
| **scikit-learn** | Machine learning library | Provides the TF-IDF vectorizer for keyword matching |
| **sentence-transformers** | AI sentence embedding library | Creates semantic "meaning" vectors using a neural network |
| **PyTorch** | Deep learning engine | Powers the SentenceTransformer neural network behind the scenes |
| **NumPy** | Numerical computing | Fast math operations for vectors, dot products, similarity scores |
| **FAISS** (optional) | Facebook AI Similarity Search | Can accelerate similarity search for large batches |
| **ReportLab** | PDF generation | Creates the professional PDF export report |
| **Pandas** | Data manipulation | Creates the CSV/Excel export file |
| **NLTK** | Natural language toolkit | Listed in requirements (available for extended NLP features) |

### Frontend (Client-Side — Browser)

| Technology | What It Does |
|---|---|
| **HTML5** | Page structure and content |
| **CSS3** | Styling, animations, responsive layout |
| **Vanilla JavaScript** | Interactive behavior — file upload, API calls, result rendering |
| **SVG** | Circular score gauge graphics |

### Key Python Modules & Imports Explained

| Import | What It Is |
|---|---|
| `os` | Interacting with the operating system (file paths, environment variables) |
| `sys` | System-level operations (adding to Python path) |
| `io` | In-memory file streams (BytesIO) — avoids writing temporary files to disk |
| `re` | Regular Expressions — pattern matching for emails, phone numbers, dates |
| `datetime` | Date/time handling for timeline audits |
| `hashlib` | SHA-256 hashing — used to cache AI embeddings by text fingerprint |
| `threading` | Background threads — pre-warms the AI model while server starts |
| `concurrent.futures` | Thread pool — processes multiple resumes in parallel |
| `numpy` | Fast array math — vector operations for similarity scoring |
| `sqlite3` | Built-in Python database interface |
| `flask` | Web framework — routes, request handling, JSON responses |
| `sklearn.feature_extraction.text.TfidfVectorizer` | Converts text to TF-IDF numerical vectors |
| `sentence_transformers.SentenceTransformer` | Converts text to dense semantic AI vectors |
| `reportlab` | Generates professional PDF documents |

---

## 4. Project File Structure

```
Resumetrics/
│
├── app.py                          ← Main Flask web server (handles all routes)
├── resume_parser.py                ← Core AI engine (text extraction, scoring, matching)
├── requirements.txt                ← Python package dependencies
├── resumetrics.db                  ← SQLite database (auto-created)
├── app.js                          ← (Unused placeholder)
│
├── templates/
│   └── index.html                  ← The main webpage (Jinja2 template)
│
├── static/
│   ├── css/
│   │   └── style.css               ← All visual styling
│   └── js/
│       └── main.js                 ← Frontend logic (drag-drop, API calls, rendering)
│
├── sample_resumes/                 ← 10 pre-generated test PDF resumes
│   ├── Aarav_Sharma_FullStack.pdf
│   ├── Priya_Patel_DataScience.pdf
│   ├── Sneha_Reddy_Fraud_Alert_Test.pdf   ← Intentionally has inflated experience
│   └── ... (7 more)
│
├── generate_test_resumes.py        ← Script that generates the sample PDFs
├── generate_project_summary_pdf.py ← Script that generates a project summary PDF
├── venv/                           ← Python virtual environment (packages)
└── uploads/                        ← (No longer used — files processed in-memory)
```

---

## 5. Detailed Code Walkthrough

### 5.1 `resume_parser.py` — The AI Brain

This is the most important file. It contains **all the intelligence** of the application. Here's what each section does:

---

#### Section 1: Imports & Setup (Lines 1–30)

```python
import os, io, re, datetime, hashlib, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
```

- Imports all the libraries the file needs.
- The `TfidfVectorizer` from scikit-learn is imported at the **top level** (not inside a function) so it's ready instantly when a request comes in. This avoids a ~5 second delay on the first request.

---

#### Section 2: Stop Words & Technical Aliases (Lines 32–70)

```python
STOP_WORDS = {'a', 'about', 'above', ...}     # ~80 common English filler words
ALIAS_MAP = {'c++': 'cpp', 'node.js': 'nodejs', ...}  # Tech term normalization
```

**What are Stop Words?**  
Words like "the", "a", "is", "and" etc. appear in every document and carry no meaning for comparison. We remove them to focus only on meaningful terms.

**What are Technical Aliases?**  
Programming terms like `C++`, `Node.js`, `CI/CD` contain special characters (`+`, `.`, `/`) that would be destroyed when we strip punctuation. So we first replace them with safe equivalents (`cpp`, `nodejs`, `cicd`).

**Optimization**: Instead of running 11 separate regex passes (one per alias), we use a **single combined regex** that matches all aliases at once and looks up the replacement from a dictionary. This is ~10x faster.

---

#### Section 3: AI Model Lazy Loading (Lines 72–100)

```python
def get_semantic_model():
    """Loads the SentenceTransformer AI model."""
    global _semantic_model
    ...
    _semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
```

**What is SentenceTransformer?**  
It's a neural network (a type of AI) that converts any sentence or paragraph into a list of 384 numbers (called a "vector" or "embedding"). These numbers capture the **meaning** of the text. Two sentences with similar meanings will have similar numbers, even if they use completely different words.

**Model: `all-MiniLM-L6-v2`**  
This is a specific pre-trained model from Microsoft. "MiniLM" means it's a small, fast version. It's been trained on millions of sentence pairs to understand semantic similarity.

**Lazy Loading**: The model is NOT loaded when the server starts. It's loaded the **first time** someone makes a request. This means the server boots instantly.

**Background Pre-Warming**: A background thread calls `warmup_semantic_model()` right after the server starts, so the model is typically ready before the first user request arrives.

---

#### Section 4: Text Extraction (Lines 105–130)

```python
def extract_text(file_source, file_type):
```

This function reads a PDF or DOCX file and pulls out all the readable text. It works with:
- **File paths** (string like `"uploads/resume.pdf"`)
- **Raw bytes** (the file content directly from memory)
- **File streams** (like a file object)

For PDFs, it uses **PyPDF** which reads each page and extracts text. For DOCX, it uses **python-docx** which reads each paragraph.

**Key Optimization**: The optimized version reads file **bytes directly from memory** (no need to save to disk first), which eliminates disk I/O overhead.

---

#### Section 5: Text Cleaning (Lines 135–148)

```python
def clean_text(text):
```

Takes raw messy text and produces clean, normalized text ready for comparison:
1. Converts everything to **lowercase** ("Python" → "python")
2. Replaces technical aliases ("C++" → "cpp")
3. Removes all **punctuation and special characters**
4. Removes **stop words** (filler words)
5. Returns a clean string of meaningful words

**Example**:
```
Input:  "Senior Python Developer with 5+ years of experience in Flask and React.js"
Output: "senior python developer flask reactjs"
```

---

#### Section 6: TF-IDF Scoring (Lines 153–170)

```python
def calculate_tfidf_scores(cleaned_resumes, cleaned_job):
```

**What is TF-IDF?**

TF-IDF stands for **Term Frequency – Inverse Document Frequency**. It's a way to measure how important a word is in a document compared to a collection of documents.

- **Term Frequency (TF)**: How often does a word appear in THIS document?
- **Inverse Document Frequency (IDF)**: How rare is this word across ALL documents?

Words that appear frequently in one resume but rarely across all resumes get a **higher score** (they're more distinctive/important).

**How it works here**:
1. We combine the job description + all resumes into one collection (called a "corpus").
2. The `TfidfVectorizer` converts each document into a vector of numbers (one number per word/bigram).
3. We compute the **cosine similarity** between the job vector and each resume vector.
4. Cosine similarity ranges from 0 (completely different) to 1 (identical). We multiply by 100 to get a percentage.

**N-Grams**: We use `ngram_range=(1, 2)` which means we look at both individual words AND two-word phrases. So "machine learning" is matched as a complete phrase, not just "machine" and "learning" separately.

**Sublinear TF**: We use `sublinear_tf=True` which applies a logarithmic scale so that a word appearing 100 times isn't scored 100x higher than one appearing once — it's only scored slightly higher. This prevents common words from dominating.

---

#### Section 7: Dense Semantic Scoring (Lines 175–210)

```python
def calculate_dense_scores(resume_texts, job_text):
```

**What is Dense Semantic Matching?**

While TF-IDF matches **exact words**, dense semantic matching understands **meaning**. For example:
- TF-IDF would NOT match "Python developer" with "software engineer using Python" very well.
- Dense semantic matching WOULD recognize these are very similar in meaning.

**How it works**:
1. The SentenceTransformer AI converts each resume and the job description into a 384-dimensional vector (a list of 384 numbers).
2. We compute the **dot product** between the job vector and each resume vector (since vectors are normalized, this equals cosine similarity).
3. Higher dot product = more similar meaning = higher score.

**SHA-256 Caching**: We hash each text with SHA-256 and store its embedding. If the same text is seen again, we skip the expensive AI computation and use the cached result. This makes repeated analyses instant.

**Text Truncation**: We only encode the first 1500 characters of each resume. This is because:
- The most important info (name, skills, summary) is always at the top.
- The transformer model has a limited input window anyway.
- It makes encoding ~3-5x faster.

---

#### Section 8: Hybrid Score Blending (Lines 215–260)

```python
def compute_rrf_scores(tfidf_scores, dense_scores, ...):
```

This function combines the three individual scores into one final score:

```
Final Score = (w_tfidf × TF-IDF Score) + (w_skill × Skill Match Score) + (w_dense × Dense Score)
```

The default weights are:
- **TF-IDF**: 40% — keyword matching importance
- **Skill Match**: 35% — exact skill phrase overlap importance
- **Dense Semantic**: 25% — meaning-based matching importance

Users can adjust these weights using the sliders on the web interface.

If the dense model isn't available (e.g., no internet, or SentenceTransformer isn't installed), the weights automatically rebalance between TF-IDF and skill matching only.

---

#### Section 9: Contact Extraction (Lines 280–305)

```python
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
PHONE_PATTERN = re.compile(r'...')
```

Uses **regular expressions** (regex) to find email addresses and phone numbers in the resume text. The patterns are pre-compiled at module load time for speed.

**Optimization**: Only searches the first 1500 characters (the resume header area) since contact info is always at the top.

---

#### Section 10: Timeline Fraud Detection (Lines 307–345)

```python
def audit_experience_timeline(resume_text):
```

This is a clever fraud detection feature:

1. **Find claimed experience**: Looks for phrases like "7+ years of experience" using regex.
2. **Find actual job dates**: Finds date ranges like "Jan 2022 - Present", "Jun 2020 - Feb 2022".
3. **Calculate provable years**: Adds up all the months from the date ranges.
4. **Compare**: If the claimed years exceed the provable years by more than 1.5 years, it flags a **Timeline Alert**.

**Example**: If someone says "7+ years experience" but their job history only covers 2 years of employment, the system flags it as suspicious.

---

#### Section 11: Skill Matching (Lines 260–290)

```python
def extract_keyword_insights(cleaned_resume, job_skills):
```

Compares each required skill against the resume text:
- **Single-word skills** (like "python", "sql"): Uses a **set lookup** — O(1) constant time per skill.
- **Multi-word skills** (like "machine learning"): Uses **substring search** in the cleaned text.

Returns two lists: **matched skills** and **missing skills**.

---

### 5.2 `app.py` — The Web Server

This file creates the Flask web application with all the URL routes.

---

#### Database Setup (Lines 1–55)

```python
app = Flask(__name__)
DB_NAME = 'resumetrics.db'
```

- Creates a Flask application instance.
- Initializes an SQLite database with **WAL mode** (Write-Ahead Logging) for faster writes.
- Launches a **background thread** to pre-load the AI model while the server boots up.

---

#### Route: `GET /` — Home Page (Line 60)

Simply renders the `index.html` template. This is the main page users see.

---

#### Route: `POST /analyze` — The Main Analysis Endpoint (Lines 63–165)

This is the heart of the application. When the user clicks "Analyze Candidates":

1. **Receives** the uploaded files and job description from the browser.
2. **Parallel Extraction**: Uses `ThreadPoolExecutor` to process multiple files simultaneously in separate threads. Each file is read directly from memory (no disk writes).
3. **Text Cleaning**: Each extracted text is cleaned and normalized.
4. **Database Insert**: Saves filenames and extracted text to SQLite in a single batch transaction.
5. **Scoring Pipeline**:
   - Computes TF-IDF scores for all resumes at once.
   - Computes Dense semantic scores for all resumes at once.
   - Pre-calculates skill matches for all resumes.
   - Blends all three scores into a final hybrid score.
6. **Report Building**: For each candidate, extracts contact info, skill insights, and timeline audit.
7. **Returns** sorted JSON results to the browser.

---

#### Route: `GET /export-csv` — CSV Download (Lines 167–200)

Generates a CSV spreadsheet file containing the candidate leaderboard. Uses Pandas to create a clean DataFrame and writes it to an in-memory buffer.

---

#### Route: `GET /export-report` — PDF Download (Lines 203–265)

Generates a professional PDF report using ReportLab. Includes:
- A summary table with all candidates ranked
- Detailed skill gap analysis per candidate
- Fraud/timeline alerts

---

### 5.3 Frontend (HTML, CSS, JS)

#### `templates/index.html` — Page Structure

The HTML page is divided into two main panels:

1. **Input Panel (Left Side)**:
   - Text area for job description/skills
   - Three weight control sliders (TF-IDF, Skill Match, Dense Semantic)
   - Drag-and-drop file upload zone
   - "Analyze Candidates" button

2. **Results Panel (Right Side)**:
   - Candidate ranking cards with animated circular score gauges
   - Matched/missing skill badges
   - Timeline fraud alert badges
   - Export buttons (PDF and CSV)

Uses a `<template>` element for the candidate card, which is cloned and populated dynamically by JavaScript.

---

#### `static/css/style.css` — Visual Design

- Uses CSS custom properties (variables) for a consistent color theme.
- Responsive grid layout that stacks on mobile screens.
- Animated circular SVG gauges for score visualization.
- Card-based design with subtle shadows and rounded corners.
- Drag-and-drop hover effects on the file upload zone.
- Badge styling for matched (green) and missing (red) skills.

---

#### `static/js/main.js` — Interactive Behavior

Written as a self-executing function (IIFE) for encapsulation:

- **File Management**: Handles drag-and-drop, file selection, duplicate prevention, and file removal.
- **Form Validation**: Enables the analyze button only when files AND skills are provided.
- **Weight Sliders**: Updates the displayed percentage as sliders move.
- **API Communication**: Sends a `POST /analyze` request with `FormData` (multipart/form-data) containing files and settings.
- **Result Rendering**: Creates candidate cards from the template, populates data, and animates the circular gauges.
- **Export Handling**: Triggers file downloads for CSV and PDF.

---

### 5.4 Supporting Scripts

#### `generate_test_resumes.py`

Creates 10 sample PDF resumes using ReportLab. Each represents a different CS/engineering specialization:
- Full-Stack, Data Science, Backend Java, Frontend, DevOps, AI/ML, Cybersecurity, Mobile Dev, Data Engineering, QA Automation.
- **Sneha Reddy's resume** intentionally claims "7+ years" but only has ~2 years of job history — used to test the fraud detection.

#### `generate_project_summary_pdf.py`

Generates a PDF summarizing the project features and architecture.

---

## 6. Advanced NLP Capabilities

ResuMetrics goes beyond simple keyword matching by employing advanced Natural Language Processing (NLP) techniques to build a holistic profile of each candidate:

### Named Entity Recognition (NER)
- **Degree & Education Extraction**: Automatically identifies and categorizes degrees (e.g., BSc, PhD, Master of Science) and prestigious universities.
- **Job Role Identification**: Detects previous job titles and roles held by the candidate to ensure they have relevant industry experience.
- **Professional Certifications**: Identifies major industry certifications (e.g., *AWS Certified, PMP, CISSP, Scrum Master*) to highlight certified expertise.
- **Languages Spoken**: Extracts language proficiencies (e.g., *Spanish, French, Mandarin*) for bilingual role requirements.

### Advanced Behavioral & Domain Classification
- **Industry Domain Classification**: Dynamically calculates keyword density across hundreds of niche terms to classify the candidate's core industry expertise (e.g., *Finance & FinTech, Healthcare, E-Commerce, AI & Data Science*).
- **Soft Skills Extraction**: Scans the text to identify core behavioral competencies like *Leadership, Agile, Empathy, Adaptability, and Problem Solving*.
- **Impact-Driven Action Verbs**: Extracts powerful action verbs (e.g., *Orchestrated, Spearheaded, Architected, Optimized*) to gauge whether the candidate uses impact-driven language rather than passive descriptions.
- **Quantifiable Metrics Extraction**: Scans the resume for scale and impact data (e.g., *%, $10M, 500K*) because the best candidates quantify their achievements. These metrics are extracted and prominently highlighted in green.

These extracted data points are beautifully rendered directly onto the candidate's dashboard card, giving recruiters instant insight into the candidate's background and behavioral profile without having to read the resume.

---

## 7. The Scoring Algorithm Explained

### The Three Pillars

| Algorithm | What It Measures | Strengths | Default Weight |
|---|---|---|---|
| **TF-IDF** | Keyword overlap with frequency weighting | Great at finding exact technical terms | 40% |
| **Skill Match** | Direct phrase-level skill overlap | Precise, binary skill presence check | 35% |
| **Dense Semantic** | Meaning-level similarity via AI | Understands synonyms and context | 25% |

### Why Three Algorithms?

No single algorithm is perfect:

- **TF-IDF alone** would miss candidates who describe skills differently ("built web apps" vs "web development").
- **Semantic AI alone** might rank a broadly similar resume higher than one with exact matching keywords.
- **Skill matching alone** is too binary — it doesn't consider depth or context.

By blending all three, ResuMetrics gets the **best of all worlds**.

### Score Calculation Formula

```
Final Score = (w₁ × TF-IDF%) + (w₂ × Skill%) + (w₃ × Dense%)
```

Where `w₁ + w₂ + w₃ = 1.0` (weights are normalized automatically).

---

## 8. Performance Optimizations

The project has been heavily optimized. Here's a before/after comparison:

| Component | Before | After | Speedup |
|---|---|---|---|
| TF-IDF Scoring | 5.18s | 0.045s | **~115x faster** |
| Dense AI Embeddings | 3.64s | 0.56s | **~6.5x faster** |
| Text Cleaning | 0.004s | 0.002s | **~2x faster** |
| End-to-end (warm) | 38+s | 0.15s | **~250x faster** |

### Key Optimization Techniques Used:

1. **Top-level imports** — Heavy modules loaded once at startup, not on every request.
2. **Single-pass regex** — Combined 11 alias patterns into one regex with dictionary lookup.
3. **In-memory processing** — Files processed from bytes, never written to disk.
4. **Concurrent extraction** — Multiple PDFs read in parallel using ThreadPoolExecutor.
5. **Sparse matrix dot product** — Replaced `cosine_similarity()` with direct sparse `.dot()`.
6. **SHA-256 embedding cache** — AI embeddings cached by text hash, reused on repeat analysis.
7. **`torch.inference_mode()`** — Disables gradient tracking for faster inference.
8. **SQLite WAL mode** — Write-Ahead Logging for non-blocking writes.
9. **Background model pre-warming** — AI model loads in a daemon thread during startup.
10. **Contact search scoping** — Only searches the top 1500 chars for email/phone.

---

## 8. How to Run the Project

### Prerequisites
- Python 3.10 or higher installed
- pip (Python package manager)

### Setup

```bash
# 1. Navigate to the project folder
cd Resumetrics

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt
pip install sentence-transformers faiss-cpu torch pandas

# 4. Generate sample test resumes (optional)
python generate_test_resumes.py

# 5. Start the server
python app.py
```

### Usage

1. Open your browser to **http://127.0.0.1:5000**
2. Paste a job description or list of required skills
3. Adjust the weight sliders (optional)
4. Drag-and-drop or browse for resume files (PDF/DOCX)
5. Click **"Analyze Candidates"**
6. View the ranked results with scores and skill analysis
7. Export as **PDF** or **CSV** if needed

---

*This documentation was generated for the ResuMetrics project. Last updated: August 2026.*
