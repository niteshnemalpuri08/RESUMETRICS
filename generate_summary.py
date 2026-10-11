import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem

def generate_project_summary_pdf(output_path="ResuMetrics_Project_Summary.pdf"):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0ea5e9'),
        spaceAfter=15,
        alignment=1 # Center
    )

    h2_style = ParagraphStyle(
        'Heading2Style',
        parent=styles['Heading2'],
        fontSize=15,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=14,
        spaceAfter=8
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=10.5,
        textColor=colors.HexColor('#334155'),
        spaceAfter=8,
        leading=15
    )

    bullet_style = ParagraphStyle(
        'BulletStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#334155'),
        leading=15
    )

    elements = []

    # Title
    elements.append(Paragraph("ResuMetrics", title_style))
    elements.append(Paragraph("Enterprise AI Resume Screening & Multi-Role ATS Platform", ParagraphStyle(
        'SubTitle', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#64748b'), alignment=1, spaceAfter=20
    )))

    # 1. Executive Summary & Purpose
    elements.append(Paragraph("1. Executive Summary & Purpose", h2_style))
    intro_text = (
        "ResuMetrics is an enterprise-grade AI resume screening, talent analytics, and Applicant Tracking System (ATS). "
        "Built to streamline hiring workflows for recruiters, hiring managers, and candidates alike, ResuMetrics evaluates "
        "unstructured resumes (PDF and DOCX) against job requirements with sub-second latency. It delivers multi-dimensional "
        "hybrid AI scoring, timeline fraud auditing, role-specific portals, and cloud-ready hybrid persistence."
    )
    elements.append(Paragraph(intro_text, body_style))

    # 2. Multi-Role User Workflows
    elements.append(Paragraph("2. Dual-Role Experience & Core Workflows", h2_style))
    workflow = [
        "<b>Recruiter Workspace:</b> Batch drag-and-drop resume parsing, algorithmic weight tuning, interactive candidate leaderboard, radar comparison charts, automated shortlisting emails, and drag-and-drop Kanban ATS stages (Applied, Shortlisted, Interviewing, Rejected).",
        "<b>Applicant Portal:</b> Self-service ATS compatibility checker, single-resume gap analysis against targeted job descriptions, tailored missing skill roadmaps, and optimization tips.",
        "<b>1-Click Demo & Authentication:</b> Frictionless access via 1-click instant demo logins for both recruiter and applicant roles, supported by secure salted password hashing (pbkdf2:sha256) and session management.",
        "<b>Export & Reporting:</b> Instant generation of executive candidate summary PDFs via ReportLab and CSV spreadsheets compatible with Microsoft Excel and Google Sheets."
    ]
    workflow_items = [ListItem(Paragraph(w, bullet_style)) for w in workflow]
    elements.append(ListFlowable(workflow_items, bulletType='bullet', start='circle'))
    elements.append(Spacer(1, 6))

    # 3. Hybrid AI Engine & Scoring Pipeline
    elements.append(Paragraph("3. Hybrid AI Scoring Engine", h2_style))
    algo_text = "The core scoring architecture blends three distinct, complementary ranking algorithms to eliminate keyword stuffing while preserving semantic comprehension:"
    elements.append(Paragraph(algo_text, body_style))
    algos = [
        "<b>TF-IDF Vectorization & Cosine Similarity (40% default):</b> Measures keyword frequency-inverse document frequency, highlighting rare domain-specific competencies over common vocabulary.",
        "<b>Exact Skill & N-Gram Extraction (35% default):</b> High-precision parser evaluating hard skills, specialized tools, and multi-word tech competencies extracted directly from job descriptions.",
        "<b>Dense Semantic Embeddings (25% default):</b> Neural sentence representations (SentenceTransformers / MiniLM) capturing conceptual similarity, recognizing equivalent roles and technologies without exact keyword matches.",
        "<b>Reciprocal Rank Fusion (RRF):</b> Mathematically fuses independent candidate rankings to ensure fair, unbiased, and normalized final scoring."
    ]
    algo_items = [ListItem(Paragraph(a, bullet_style)) for a in algos]
    elements.append(ListFlowable(algo_items, bulletType='bullet', start='circle'))
    elements.append(Spacer(1, 6))

    # 4. Advanced NLP & Intelligence Features
    elements.append(Paragraph("4. Advanced NLP & Integrity Auditing", h2_style))
    nlp = [
        "<b>Timeline Fraud Detection:</b> Audits claimed years of experience against detected employment date spans in job histories, flagging discrepancies and gaps.",
        "<b>Career Growth & Trajectory Tracking:</b> Detects rapid promotions, lateral leadership growth, and progressive job responsibility indicators.",
        "<b>Information Extraction (NER & Regex):</b> High-accuracy extraction of contact emails, phone numbers, academic degrees, certifications, and quantifiable metrics ($ saved, % growth).",
        "<b>Conversational RAG Chatbot:</b> Natural language query assistant allowing recruiters to ask questions across the parsed candidate pool in real time."
    ]
    nlp_items = [ListItem(Paragraph(n, bullet_style)) for n in nlp]
    elements.append(ListFlowable(nlp_items, bulletType='bullet', start='circle'))
    elements.append(Spacer(1, 6))

    # 5. Database & Cloud Architecture
    elements.append(Paragraph("5. Infrastructure, Database & Cloud Deployment", h2_style))
    tech = [
        "<b>Primary Database (MySQL / TiDB):</b> Persistent relational storage configured with account credentials (`root:nitesh123@localhost:3306/resumetrics`) storing candidate corpora, authentication tables, and screening history.",
        "<b>Self-Healing Storage Proxy:</b> Intelligent SQLite fallback proxy providing continuous zero-downtime execution in serverless cloud environments where local MySQL sockets are unreachable.",
        "<b>Serverless Vercel Routing:</b> WSGI ProxyFix and custom VercelRoutingMiddleware resolving clean URLs, rewrites, and serverless function entry points seamlessly.",
        "<b>Backend & Frontend Stack:</b> Python 3.12, Flask, Werkzeug, PyPDF, python-docx, ReportLab, Vanilla HTML5/CSS3, and Chart.js."
    ]
    tech_items = [ListItem(Paragraph(t, bullet_style)) for t in tech]
    elements.append(ListFlowable(tech_items, bulletType='bullet', start='circle'))

    # Build PDF
    doc.build(elements)
    print(f"Successfully generated {output_path}")

if __name__ == '__main__':
    generate_project_summary_pdf()
